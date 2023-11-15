import json
import errno
import threading
import time
from threading import Event
from enum import Enum

try:
    import rados
    from ceph_argparse import json_command
except ImportError:
    raise ImportError("couldn't import rados, ceph_argparese from python3 library")

from ees_manager.common.services.iservice import EsAGwServices
from ees_manager.common.base_type import ShareVariable, time_sleep

# API 请求超时时间
TIMEOUT = 5

# Rados 层抛出的异常
# errno.EPERM     : PermissionError,
# errno.ENOENT    : ObjectNotFound,
# errno.EIO       : IOError,
# errno.ENOSPC    : NoSpace,
# errno.EEXIST    : ObjectExists,
# errno.EBUSY     : ObjectBusy,
# errno.ENODATA   : NoData,
# errno.EINTR     : InterruptedOrTimeoutError,
# errno.ETIMEDOUT : TimedOut,
# errno.EACCES    : PermissionDeniedError,
# errno.EINPROGRESS : InProgress,
# errno.EISCONN   : IsConnected,
# errno.EINVAL    : InvalidArgumentError,
# errno.ENOTCONN  : NotConnected,


class ConnectStatus(Enum):
    UNCONNECTED = 0   # 未连接
    CONNECTING = 1   # 连接中
    CONNECTED = 2   # 已连接


# 此服务还有一个问题未解决，就是当rados失去链接的时候，如何重新联系，这对服务的可用性很重要 (已解决，待审核)
class MonitorThread(threading.Thread):
    def __init__(self, ceph_service):
        super(MonitorThread, self).__init__()
        self.ceph_serv = ceph_service
        self.log = self.ceph_serv.log

    def run(self):
        while not self.ceph_serv.b_quit.value:
            try:
                # 等待开始信号
                if self.ceph_serv.e_timeout.wait(timeout=1):
                    if self.ceph_serv.connect_status == ConnectStatus.CONNECTING.value:
                        return

                    self.log.info("Reconnect to rados cluster")
                    self.ceph_serv.reconnect()

                    # 清除信号
                    self.ceph_serv.e_timeout.clear()
                else:
                    time_sleep(self.ceph_serv.b_quit, 5)

            except TimeoutError:
                self.log.debug("wait work event timeout!")
                time_sleep(self.ceph_serv.b_quit, 3)

            except rados.InProgress:
                self.log.debug("in progress")
                time_sleep(self.ceph_serv.b_quit, 3)

            except rados.RadosStateError:
                self.ceph_serv.renew_rados()

            except rados.IsConnected:
                self.ceph_serv.renew_rados()

            except Exception as e:
                self.log.exception(e)
                self.log.error("Reconnect to rados cluster failed!")
                time_sleep(self.ceph_serv.b_quit, 3)


class CephCommandService(EsAGwServices):
    def __init__(self, conf, log, **kwargs):
        super(CephCommandService, self).__init__(conf, log)
        # 连接存储集群的用户
        self.client_name = self.conf.get('storage', 'client') if self.conf.has_option('storage', 'client') \
            else "client.admin"
        # 存储结群的配置文件
        self.conffile = self.conf.get('storage', 'conffile') if self.conf.has_option('storage', 'conffile') \
            else "/etc/ceph/ceph.conf"
        # 集群名称
        self.cluster_name = self.conf.get('storage', 'cluster_name') if self.conf.has_option('storage', 'cluster_name') \
            else "ceph"

        self.format = "json"  # 需要后端返回json 数据
        self.module = "mon"
        self.perm = "r"
        self.cmdtarget = ('mon', '')
        self.cluster = None
        self.is_connect = False  # 是否已连接
        self.connect_status = ShareVariable(ConnectStatus.UNCONNECTED.value)

        self.b_quit = kwargs.get("quit_signal")    # 从顶层传过来的信号
        self.e_timeout = Event()  # timeout 事件
        self.monitor_thread = None  # 监控线程

    def init_service(self):
        # 创建监控线程
        self.monitor_thread = MonitorThread(self)
        # 初始化到rados的连接
        self.init_rados()
        return True

    def start(self):
        # 启动一个线程负责重连
        self.monitor_thread.start()

    def _connect_to_rados(self):
        try:
            # self.log.info(f"cluster state: {self.cluster.state}")
            self.cluster.connect(timeout=TIMEOUT)
        except rados.TimedOut as e:
            self.log.error("Connect to rados cluster timeout!")
            self.connect_status = ConnectStatus.UNCONNECTED.value
            raise e

        except rados.PermissionDeniedError as e:
            self.log.error("user {} is permission denied!".format(self.client_name))
            self.connect_status = ConnectStatus.UNCONNECTED.value
            raise e

        except rados.InProgress as e:
            self.connect_status = ConnectStatus.CONNECTING.value
            raise e

        except Exception as e:
            self.connect_status = ConnectStatus.UNCONNECTED.value
            raise e
        else:
            self.is_connect = True
            self.connect_status = ConnectStatus.CONNECTED.value
            self.log.info("Connect to rados cluster successful!")

    def reconnect(self):
        # 建立链接
        self.log.info("Reconnect to rados cluster...")
        self.connect_status = ConnectStatus.CONNECTING.value
        self._connect_to_rados()

    def renew_rados(self):
        # 建立链接
        self.log.info("Reconnect to rados cluster...")
        if self.cluster.state == "connected":
            self.cluster.shutdown()

        self.cluster = rados.Rados(name=self.client_name, clustername=self.cluster_name, conffile=self.conffile)

    def init_rados(self):
        # 建立链接
        self.log.info("Init and connect to rados cluster...")
        self.connect_status = ConnectStatus.CONNECTING.value
        self.cluster = rados.Rados(name=self.client_name, clustername=self.cluster_name, conffile=self.conffile)
        self._connect_to_rados()

    def send_command(self, prefix, **kwargs):
        # self.log.info(f"send_command: {self.connect_status}")
        if self.connect_status != ConnectStatus.CONNECTED.value:
            raise SystemError("Rados cluster not connected")

        args_dict = {'format': 'json', 'module': self.module if 'module' not in kwargs else kwargs['module'],
                     'perm': "r"}
        args_dict.update(kwargs)
        native_output = []
        try:
            # for _ in range(3):
            ret, outbuf, outs = json_command(self.cluster, prefix=prefix,
                                             target=self.cmdtarget,
                                             argdict=args_dict,
                                             timeout=TIMEOUT)
            if len(outbuf) == 0:
                return {}

            if args_dict['format'] == 'json':
                native_output = json.loads(outbuf)
            else:
                native_output = outbuf
            if ret != -errno.EINTR and ret != 0:
                self.log.error("ret: {}, msg: {}".format(ret, outs))

        except RuntimeError as e:
            # 如果运行超时， 怎认为后端rados是断开连接了， 则需要重连
            self.log.error("Rados request is timeout!")
            self.is_connect = False
            if self.connect_status != ConnectStatus.CONNECTING.value:
                self.connect_status = ConnectStatus.UNCONNECTED.value
                self.e_timeout.set()
            raise e
        except Exception as e:
            self.log.exception(e)
            raise e

        return native_output

    def stop(self):
        if self.cluster is not None:
            self.cluster.shutdown()

        # 使监控线程退出
        if not self.b_quit.value:
            self.b_quit.value = True

        self.monitor_thread.join()

    def is_running(self):
        return self.monitor_thread.is_alive()
