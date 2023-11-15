# redis service
import uuid
import requests
import json

from ees_manager.common.services.iservice import EsAGwServices
from ees_manager.common.decoration import retry
from ees_manager.common.const_var import *
from ees_manager.common.base_type import DateEncoder
from ees_manager.common.exception import *


# 组件通信
class EesCommService(EsAGwServices):
    def __init__(self, conf, log, server_role="es_agw", server_name="", clustermap_service=None):
        super(EesCommService, self).__init__(conf, log)

        # 服务器角色
        self.server_role = server_role
        if self.server_role == ServerRole.ES_AGW.value:
            self.def_msg_send_to_server_role = ServerRole.ND_AGENT.value
        else:
            self.def_msg_send_to_server_role = ServerRole.ES_AGW.value

        # 服务器名称
        self.server_name = server_name

        # clustermap 服务
        self.clustermap = clustermap_service

    def init_service(self):
        """
        初始化本服务
        """
        pass

    def _try_send_msg(self, url, msg):
        try:
            ret = requests.post(url, data=json.dumps(msg, ensure_ascii=False, cls=DateEncoder).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
            if ret.status_code != 200:
                self.log.error("send msg failed！{}".format(ret.text))
                raise SystemError(ret.text)
            return ret
        except Exception as e:
            raise e

    def inner_request(self, method="PUT", role=ServerRole.ES_AGW.value, node=None, url="", msg={}, headers={}):
        try:
            if len(role) == 0 or role is None:
                role = self.def_msg_send_to_server_role

            node_info = self.clustermap.get_availe_service(role=role, node=node)
            self.log.info("send msg to: {}".format(node_info['name']))
            # return self._try_send_msg(, msg)

            if method == "GET":
                call = requests.get
            elif method == "PUT":
                call = requests.put
            elif method == "POST":
                call = requests.post
            elif method == "DELETE":
                call = requests.delete
            headers["Content-Type"] = "application/json"

            return call(f"{node_info['comm_url']}{url}", data=json.dumps(msg), headers=headers)

        except Exception as e:
            self.log.exception(e)
            raise e

    @retry(Exception, total_tries=2, initial_wait=3)
    def send_msg(self, role=ServerRole.ES_AGW.value, node=None, api_port="_report", msg=None):
        try:
            if len(role) == 0 or role is None:
                role = self.def_msg_send_to_server_role

            node_info = self.clustermap.get_availe_service(role=role, node=node)
            if node_info is None:
                if role == ServerRole.ES_AGW.value:
                    raise EsAgwException()
                if role == ServerRole.ND_AGENT.value:
                    raise NdAgentException()

            # self.log.info("send msg to: {}".format(node_info['name']))
            return self._try_send_msg("{}/api/{}".format(node_info["comm_url"], api_port), msg)

        except Exception as e:
            self.log.error("send msg failed! {}".format(str(e)))
            raise e

    def start(self):
        return True

    def stop(self):
        return True
