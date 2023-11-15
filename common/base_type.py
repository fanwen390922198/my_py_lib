import os
import json
from threading import Lock, Event
import threading
from datetime import date, datetime, timedelta
import time
import socket
import telnetlib
import uuid
import random
import re
import queue
import platform
from flask import request

from .shell import shell_with_no_exception, ShellExec
from sqlalchemy.engine.row import Row
from time import monotonic
# from ees_manager.common.decoration import run_cost_for_test

DEFAULT_TELNET_TIMEOUT = 2

# 当前节点名称
THIS_NODE_NAME = platform.node()


# uuid
def UUID():
    return UniqueIdGenerator.uuid()


# 当前时间
def date_time_now():
    return datetime.now()


# 共享变量，用于多线程通信
class ShareVariable(object):
    def __init__(self, flag=True):
        self._flag = flag
        self.lock = Lock()

    @property
    def value(self):
        return self._flag

    @value.setter
    def value(self, value):
        self.lock.acquire()
        self._flag = value
        self.lock.release()


# 线程等待， 防止线程长时间sleep，影响stop
def time_sleep(cond, interval):
    """

    :param cond: condition variable
    :type cond: ShareVariable
    :param interval: wait time
    :type cond: int
    :return:
    """
    _t = interval
    while _t > 0:
        if not cond.value:
            time.sleep(0.5)
            _t -= 0.5
        else:
            break


# 唯一值、随机值生成器
class UniqueIdGenerator:
    @staticmethod
    def uuid():
        return str(uuid.uuid4())

    @staticmethod
    def uuid_hex():
        return uuid.uuid4().hex

    @staticmethod
    def random_string(nums=13):
        if nums <= 9:
            return ''.join(str(i) for i in random.sample(range(0, 9), nums))
        else:
            s_ret = ""
            while nums > 9:
                s_ret += ''.join(str(i) for i in random.sample(range(0, 9), 9))
                nums -= 9

            if nums > 0:
                s_ret += ''.join(str(i) for i in random.sample(range(0, 9), nums))

            return s_ret


# json decode 增加对datetime的支持
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


def get_file_dir(file_path):
    """
    获取文件所在的目录
    :param file_path:
    :return:
    """
    return os.path.dirname(file_path)


def make_dirs(dir_name):
    """
    生成多级目录
    :param dir_name:
    :return:
    """
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)


def path_exists(path):
    """
    路径是否存在
    :param path:
    :return:
    """
    return os.path.exists(path)


def path_split(path):
    """
    分离文件目录和文件名
    print(os.path.split("/etc/ceph/ceph.conf"))
    ('/etc/ceph', 'ceph.conf')
    :param path:
    :return:
    """
    return os.path.split(path)


def write_pid_file(pid_file):
    try:
        dir_name = os.path.dirname(pid_file)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        fd = open(pid_file, 'w')
        fd.write("%d" % os.getpid())
        fd.close()
    except (OSError, IOError) as error:
        raise error


def delete_pid_file(pid_file):
    if os.path.exists(pid_file):
        try:
            os.unlink(pid_file)
        except OSError as error:
            raise error


#  transfer sqlalchemy query result --> dict
def format_result_to_dict(result):
    if result is None or (isinstance(result, list) and len(result) == 0):
        return []

    if isinstance(result, Row): # row type --> e.g. select node.id, node.hostname from node where node.id = 2;
        return [dict(result)]

    elif isinstance(result, list):
        _result = []
        if not isinstance(result[0], Row):
            # if no field is specified --> e.g. select * from node;
            for row in result:
                _result.append({k: v for k, v in row.__dict__.items() if k != "_sa_instance_state"})
        else:
            # field is specified --> e.g. select node.id, node.hostname from node;
            for row in result:
                _result.append(dict(row))

        return _result

    else:
        if "__tablename__" in dir(result):  # table type --> e.g. select * from node where node.id = 2;
            return [{k: v for k, v in result.__dict__.items() if k != "_sa_instance_state"}]


# 时间序列化
def get_time(in_type):
    if in_type is 0:
        return time.strftime('%Y%m%d', time.localtime(time.time()))
    elif in_type is 1:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elif in_type is 2:  # 包含毫秒
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    elif in_type is 3:
        return datetime.now().strftime('%Y-%m-%d')
    elif in_type is 4:
        return datetime.now().strftime('%Y%m%d%H%M%S')


# 将本地时间转成utc时间
def local2utc(str_datetime):
    dt = str_to_datetime(str_datetime)
    dt_stamp = time.mktime(dt.timetuple())
    return str(datetime.utcfromtimestamp(dt_stamp))


# 将本地时间转成utc时间
def utc2local(str_datetime):
    pass


# 时间反序列化
def str_to_datetime(sdatetime):
    return datetime.strptime(sdatetime, '%Y-%m-%d %H:%M:%S')


# 时间戳转时间
def timestamp_to_datetime(timestamp):
    return datetime.fromtimestamp(int(timestamp))


# 从文件中加载json
def load_json_file(path):
    try:
        with open(path, "r+") as f:
            content = json.load(f)
        return content
    except Exception as e:
        raise e


# 覆盖写
def overwrite_to_file(file, scontent):
    try:
        fp = open(file, "w")
        fp.write(scontent)
        fp.close()
    except IOError as e:
        raise e


# telnet port，
def telnet_port(host, port, timeout=DEFAULT_TELNET_TIMEOUT):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        if result == 0:
            return True
        else:
            return False
    except Exception as e:
        # print(str(e))
        return False


def telnet_port2(host, port, timeout=DEFAULT_TELNET_TIMEOUT):
    try:
        telnetlib.Telnet(host, port, timeout=timeout)
    except Exception as e:
        return False

    return True


# 延时
def timer_delay_run(timer, func, func_args=[], delay_secs=10):
    """
    延时运行
    @param timer: 定时服务， type: TimerCall
    @param func: 待执行的函数
    @param func_args: 函数的入参
    @param delay_secs: 延时秒数
    @return:
    """
    dt = datetime.now()
    dt2 = dt + timedelta(seconds=delay_secs)
    try:
        timer.add_job_run_once(func, func_args, dt2)
    except Exception as e:
        raise e


# ping
def ping_node(node_ip):
    cmd = "ping {} -c 2".format(node_ip)
    ret = shell_with_no_exception(cmd, timeout=3)
    if ret is not None and len(ret) > 0:
        p = re.compile(r', (\d+)% packet loss,')
        lost = p.findall(ret)
        if len(lost) > 0:
            if int(lost[0]) > 0:
                return False
            else:
                return True
    return False



# 通用的工作线程
class CWorker(object):
    def __init__(self, name=None, log=None, quit=None, msg_queue=None, msg_deal_func=None):
        if name is None or (type(name) == str and len(name) == 0):
            self.name = "worker-{}".format(UniqueIdGenerator.random_string(6))
        else:
            self.name = name
        self.log = log
        self.is_quit = quit
        self.queue = msg_queue
        self.thread = None
        self.msg_deal_func = msg_deal_func
        self.get = 0

    def _start_work(self):
        while not self.is_quit.value or self.queue.qsize() > 0:
            try:
                if self.queue.qsize() > 0:
                    msg = self.queue.get(block=False)  # Remove and return an item from the queue.
                    self.get += 1
                    # 处理消息(子类需要实现该功能)
                    if self.msg_deal_func is not None:
                        self.msg_deal_func(msg)
                    else:
                        self._deal_msg(msg)
                else:
                    time_sleep(self.is_quit, 1)
            except queue.Empty:
                time_sleep(self.is_quit, 1)

            except Exception as e:
                self.log.error("CWorker [] run error".format(self.name))
                self.log.exception(e)

        # self.log.debug("CWorker [{}] run over, has processed {} msgs".format(self.name, self.get))
        # self.log.debug("工作线程-{} 退出！已经处理了 {} 消息!".format(self.name, self.get))

    def start(self):
        self.thread = threading.Thread(target=self._start_work, name="Consumer")
        self.thread.start()

    def join(self):
        self.thread.join()

    def stop(self):
        self.is_quit.value = True
        self.join()

    def _deal_msg(self, msg):
        """
        具体处理业务处理
        @param msg:
        @return:
        """
        self.log.info("deal: {}".format(msg))


def transfer_size_byte(size):
    if size == 0:
        return "0"
    elif (size > 0) and (size < 1024):
        return "{} B".format(size)
    elif (size >= 1024) and (size < 1024 ** 2):
        return "{} KB".format(int(size / 1024))
    elif (size >= 1024 ** 2) and (size < 1024 ** 3):
        return "{} MB".format(int(size / 1024 ** 2))
    elif (size >= 1024 ** 3) and (size < 1024 ** 4):
        return "{:.2f} GB".format(size / 1024 ** 3)
    elif (size >= 1024 ** 4) and (size < 1024 ** 5):
        return "{:.2f} TB".format(size / 1024 ** 4)
    elif size >= 1024 ** 5:
        return "{:.2f} PB".format(size / 1024 ** 5)


def run_ceph_command(cmd):
    ret = shell_with_no_exception(cmd)
    if ret is not None and len(ret) > 0:
        return json.loads(ret.strip())

    return None


def get_dev_name(part):
    """
    获取分区对应的设备名称
    """
    if "nvme" in part:
        return part.split("p")[0]
    else:
        dev = ""
        for i in part:
            if i.isdigit():
                break
            else:
                dev += i
        return dev


def get_dev_info_by_smartctl(dev, device_id=-1, cciss=-1):
    """
    通过smartctl 获取磁盘设备信息
    :param dev: 设备名称
    :param device_id:  设备ID LSI 卡
    :param cciss:  HP卡

    :return:
    """
    disk_info = {}
    cmd = f'smartctl -i /dev/{dev}'
    if int(device_id) >= 0:
        cmd += f' -d megaraid,{device_id}'
    elif int(cciss) >= 0:
        cmd += f' -d cciss,{cciss}'

    filter_fields = '|egrep "(Model Number|Device Model|Serial|Logical Unit id|WWN|User Capacity|Size/Capacity|' \
                    'Rotation Rate|Product|Vendor)"'
    cmd += filter_fields

    try:
        sub_ret = ShellExec.call(cmd)
        all_lines = sub_ret.stdout.split("\n")
        for line in all_lines:
            if line.find("Device Model") != -1:
                # Device Model:     INTEL SSDSC2BB160G4
                disk_info['model'] = line[line.find(":") + 1:].strip()
            elif line.find("Model Number") != -1:
                # Model Number:                       HWE32P43032M000N
                disk_info['model'] = line[line.find(":") + 1:].strip()

            elif line.find("Vendor") != -1:
                # Vendor: LENOVO
                if line.split(":")[0].strip() == "Vendor":
                    disk_info['model'] = line[line.find(':') + 1:].strip()  # 厂商
            elif line.find("Product") != -1:
                # Product: MZILS1T6HCHPV3
                disk_info['model'] += " "
                disk_info['model'] += line[line.find(':') + 1:].strip()  # 产品
                if "QEMU HARDDISK" in disk_info['model']:
                    disk_info['type'] = "VD"  # 虚拟磁盘

            elif line.find("Serial") != -1:  # 序列号
                # Serial number:        A1Y630730J200234
                disk_info['serial_number'] = line[line.find(":") + 1:].replace(" ", "").strip()

            elif line.find("WWN") != -1:    # wwn
                # LU WWN Device Id: 5 5cd2e4 04c7bbf28
                disk_info['wwn'] = line[line.find(":") + 1:].replace(" ", "").strip()
            # elif line.find("Logical Unit id") != -1:  # LENOVO 设备wwn
            #     # Logical Unit id:      0x5002538a0720f060
            #     disk_info['wwn'] = line[line.find(":") + 1:].replace(" ", "").replace("0x", "").strip()

            elif line.find("User Capacity") != -1:  # 容量
                # User Capacity:        1,600,321,314,816 bytes [1.60 TB]
                disk_info['capacity'] = line[line.find(":") + 1:].strip()
            elif line.find("Capacity") != -1:
                # Total NVM Capacity:                 3,200,631,791,616 [3.20 TB]
                disk_info['capacity'] = line[line.find(":") + 1:].strip()

            elif line.find('Rotation Rate') != -1:
                # Rotation Rate:        Solid State Device
                # Rotation Rate:    7200 rpm
                if line.find("rpm") != -1:
                    disk_info['type'] = "HDD"
                elif line.find("Solid") != -1:
                    disk_info['type'] = "SSD"

    except Exception:
        raise

    return disk_info


class CEesQueue(queue.Queue):
    """
    扩展系统Queue， 增加从左边put的功能；
    在原生的Queue中，默认是使用collections.deque
    """

    def append(self, item):
        return self.put(item)

    def appendleft(self, item):
        return self.put_left(item)

    def put_left(self, item, block=True, timeout=None):
        '''Put an item into the queue head.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until a free slot is available. If 'timeout' is
        a non-negative number, it blocks at most 'timeout' seconds and raises
        the Full exception if no free slot was available within that time.
        Otherwise ('block' is false), put an item on the queue if a free slot
        is immediately available, else raise the Full exception ('timeout'
        is ignored in that case).
        '''
        with self.not_full:
            if self.maxsize > 0:
                if not block:
                    if self._qsize() >= self.maxsize:
                        raise queue.Full
                elif timeout is None:
                    while self._qsize() >= self.maxsize:
                        self.not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' must be a non-negative number")
                else:
                    endtime = monotonic() + timeout
                    while self._qsize() >= self.maxsize:
                        remaining = endtime - monotonic()
                        if remaining <= 0.0:
                            raise queue.Full
                        self.not_full.wait(remaining)
            self._put_left(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def put_left_nowait(self, item):
        return self.put_left(item, block=False)

    def _put_left(self, item):
        self.queue.appendleft(item)

