#!/usr/bin/python
import datetime
import random
import requests
from enum import Enum, unique

from ees_manager.common.services.iservice import EsAGwServices
from ees_manager.common.base_type import get_time, str_to_datetime, ping_node
from ees_manager.common.const_var import ServerRole, ServerStatus, ServicePlayRole
from ees_manager.common.redis_connect import RedisConnect


TRYS = 3


# ees 服务
class EesService(object):
    def __init__(self, role, name, comm_url):
        self.name = name    # 服务名称
        self.role = role    # 服务角色
        self.run_as = ServicePlayRole.FOLLOWER.value
        self.comm_url = comm_url
        self._service_status = ServerStatus.ON.value

    def service_name(self):
        return "{}:{}".format(self.role, self.name)

    @property
    def status(self):
        return self._service_status

    @status.setter
    def status(self, status):
        self._service_status = status

    def __str__(self):
        return str(dict(
            name=self.name,
            role=self.role,
            run_as=self.run_as,
            comm_url=self.comm_url,
            status=self.status,
            update_time=get_time(1)
        ))


# @unique
# class ClusterMapMsg(Enum):
#

# cluster map service
class ClusterMapService(EsAGwServices, RedisConnect):
    def __init__(self, conf, log, timer, server_role="", server_name=""):
        EsAGwServices.__init__(self, conf, log)
        RedisConnect.__init__(self, conf, log)

        comm_ip = self.conf.get('flask', 'ip') if self.conf.has_option('flask', 'ip') else "127.0.0.1"
        comm_port = self.conf.get_int('flask', 'port') if self.conf.has_option('flask', 'port') else 5001
        self.timer = timer

        # 初始化本地服务
        self.service_me = EesService(server_role, server_name, comm_url="http://{}:{}".format(comm_ip, comm_port))

        self.cluster_map = {}
        self.upload_service_interval = self.conf.get_int('timer', 'upload_service_interval') \
            if self.conf.has_option('timer', 'upload_service_interval') else 30
        self.update_cluster_map = self.conf.get_int('timer', 'update_cluster_map') \
            if self.conf.has_option('timer', 'update_cluster_map') else 30
        self.timer_job = []
        self.last_on_line_nodes = []
        self.start_at = None
        self.master_node = None   # 当前master 节点
        self.last_master_node = None

    def me_is_master(self):
        return self.service_me.run_as == ServicePlayRole.LEADER.value

    def get_master(self):
        # {'name': 'node2', 'role': 'es_agw', 'comm_url': 'http://10.3.193.112:5002', 'status': 0, 'update_time':
        # '2022-02-16 14:59:30'}
        return self.cluster_map[ServerRole.ES_AGW.value][self.master_node]

    def init_service(self):
        # 创建到redis的链接
        self._connect_redis()

        # 上报服务状态
        # 启动时上报一次
        self._update_me_to_redis()

        # 后续定时上报
        job_id = self.timer.add_job_run_interval(self._update_me_to_redis, [], secs=self.upload_service_interval)
        self.timer_job.append(job_id)

        # 集群拓扑
        # 启动时更新一次集群拓扑
        self.start_at = datetime.datetime.now()
        self._get_cluster_map_from_redis()

        job_id = self.timer.add_job_run_interval(self._get_cluster_map_from_redis, [], secs=self.update_cluster_map)
        self.timer_job.append(job_id)

    def _update_me_to_redis(self):
        try:
            # self.log.debug("update me to redis")
            # 1. 将本机信息缓存到redis, 定时
            # self.redis_conn.set(self.service_me.me(), str(self.service_me))
            # self.redis_conn.expire(self.service_me.me(), self.upload_service_interval + 1)
            # self.redis_conn.set(self.service_me.me(), str(self.service_me))

            # 2. 将本机信息添加到集群拓扑
            self.redis_conn.hset(self.service_me.role, self.service_me.name, str(self.service_me))
        except Exception as e:
            self.log.exception(e)

    def _check_service_is_online(self, role, now, node, node_info):
        # self.log.debug(f"{role}, {now}, {node}, {node_info}")
        if role not in self.cluster_map:
            self.cluster_map[role] = {}

        last_update_time = node_info["update_time"]
        if (now - str_to_datetime(last_update_time)).seconds > self.upload_service_interval:  # 超时未上报状态
            comm_url = node_info['comm_url']
            try:
                ret = requests.head(comm_url + "/", timeout=2)
                if ret.status_code == 200:
                    node_info["status"] = ServerStatus.ON.value
            except Exception as e:
                self.log.error(f"{role} on {node} is down!")
                node_info["status"] = ServerStatus.DOWN.value

                # 删除此服务
                self.redis_conn.hdel(role, node)
        else:
            node_info["status"] = ServerStatus.ON.value

        self.cluster_map[role][node] = node_info

    def _who_is_master(self, on_line_es):
        if len(on_line_es) == 0:
            return
        # 默认集群拓扑的第一个就master （leader）
        if on_line_es[-1] == self.service_me.name:   # 排第一位的是我， 那么我就是master
            self.log.warning(f'Me {self.service_me.name} is master')
            if self.service_me.run_as != ServicePlayRole.LEADER.value:
                self.service_me.run_as = ServicePlayRole.LEADER.value
        else:
            self.log.warning(f'Me {self.service_me.name} is follower')
            if self.service_me.run_as != ServicePlayRole.FOLLOWER.value:
                self.service_me.run_as = ServicePlayRole.FOLLOWER.value

        # 更新master 节点
        self.master_node = on_line_es[-1]

        # 更新节点信息到clustermap
        self._update_me_to_redis()

        # 保存上一次online 拓扑
        self.last_on_line_nodes = on_line_es

    def _get_cluster_map_from_redis(self):
        try:
            # self.log.debug("get cluster map from redis...")
            # 1. # 从redis 上获取集群拓扑
            # self.log.debug("get all es_agw from redis...")
            all_es_agw = self.redis_conn.hgetall(ServerRole.ES_AGW.value)
            # self.log.debug(all_es_agw)
            # self.log.debug("get all nd_agent from redis...")
            all_nd_agent = self.redis_conn.hgetall(ServerRole.ND_AGENT.value)
            # self.log.debug(all_nd_agent)
            on_line_nodes = []
            now = datetime.datetime.now()
            for (node, str_node) in all_es_agw.items():
                node_info = eval(str_node)
                # update_time = node_info["update_time"]
                self._check_service_is_online(ServerRole.ES_AGW.value, now, node, node_info)
                if node_info["status"] == ServerStatus.ON.value:
                    on_line_nodes.append(node)

            # es_agw 会发生选举
            if self.service_me.role == ServerRole.ES_AGW.value:
                # self.log.debug("Check Master!")
                now = datetime.datetime.now()
                # 集群拓扑发生变化 + 等待超过一个周期
                # self.log.debug(f'last_on_line_nodes: {self.last_on_line_nodes}')
                # self.log.debug(f'on_line_nodes: {on_line_nodes}')
                on_line_nodes = sorted(on_line_nodes)
                if self.last_on_line_nodes != on_line_nodes and \
                        (len(on_line_nodes) > 1 or
                         (now - self.start_at).seconds >= self.update_cluster_map):
                    # 满足条件，就会开始计算谁是master
                    self._who_is_master(on_line_nodes)
                    self.log.debug(f'Master Node: {self.master_node}')

            for (node, str_node) in all_nd_agent.items():
                node_info = eval(str_node)
                self._check_service_is_online(ServerRole.ND_AGENT.value, now, node, node_info)

            # self.log.debug("Clustermap: {}".format(self.cluster_map))
        except Exception as e:
            self.log.error("Redis service is error")
            self.log.exception(e)

    def get_availe_service(self, role=ServerRole.ES_AGW.value, node=None):
        # 获取指定角色的服务
        available_nodes = []
        for _ in range(0, TRYS):
            if role in self.cluster_map:
                available_nodes = [v for (k, v) in self.cluster_map[role].items() if v["status"] == ServerStatus.ON.value]

            if len(available_nodes) == 0:
                self._get_cluster_map_from_redis()
            else:
                break

        if len(available_nodes) == 0:
            return None

        if node is None or (type(node) is str and len(node) == 0):
            return available_nodes[random.randint(0, len(available_nodes)-1)]
        else:
            return self.cluster_map[role][node] if node in self.cluster_map[role] else None

    def node_is_on_line(self, role=ServerRole.ES_AGW.value, node=None):
        if node not in self.cluster_map[role]:
            return False

        return self.cluster_map[role][node]["status"] == ServerStatus.ON.value

    def start(self):
        return True

    def stop(self):
        # 关闭定时任务
        # for job in self.timer_job:
        #     self.timer.del_job(job)
        return True


