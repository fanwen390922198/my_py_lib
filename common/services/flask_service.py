#!/usr/bin/env python
import logging
from werkzeug.serving import make_server
from flask import Flask
from flask_restful import Api
import threading
from datetime import datetime, date
from flask.json import JSONEncoder
from flask_restful import Resource
from flask import request
from ees_manager.common.services.iservice import EsAGwServices
from ees_manager.common.services.log import thread_local

# 全局的app
# flask_app = None


class Pong(Resource):
    def __init__(self):
        super(Pong, self).__init__()

    def head(self):
        return 200

    def get(self):
        return 200


class CustomJsonEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H-%M:%S")
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        else:
            return JSONEncoder.default(self, obj)


class ServerThread(threading.Thread):
    def __init__(self, app, log, flask_bind_ip='127.0.0.1', flask_bind_port=5000):
        threading.Thread.__init__(self)
        self.ip = flask_bind_ip
        self.port = flask_bind_port
        self.app = app
        self.log = log

        # processes=10, 经测试多进程性能不如多线程
        _logger = logging.getLogger("werkzeug")
        _logger.setLevel(logging.ERROR)
        self.srv = make_server(flask_bind_ip, flask_bind_port, self.app, threaded=True)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def run(self):
        self.log.info('Restful api service will bind on [ ip {}: port {}]'.format(self.ip, self.port))
        # self.app.run(debug=True)
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()
        self.log.info('Restful api service stopped')


class EesFlask(Flask):
    def __init__(self, app_name, log):
        Flask.__init__(self, app_name)
        self.log = log

    @property
    def logger(self):
        return self.log


class RestfulApiService(EsAGwServices):
    """
        restful api service
    """
    def __init__(self, conf, log, app_name=None, decorators=[]):
        super(RestfulApiService, self).__init__(conf, log)
        # global flask_app
        self.service_thread = None
        self.app_name = app_name if app_name is not None else __name__
        self.app = Flask(self.app_name)
        # flask_app = self.app
        self.app.json_encoder = CustomJsonEncoder
        self.app.debug = False
        # self.app.thread_local = threading.local()
        self.app.thread_local = thread_local
        self.api = Api(self.app, decorators=decorators)
        self.license_manager = None
        self._request_preprocess()

    def _request_preprocess(self):
        """
        rest 请求预处理
        """

        @self.app.before_request
        def before_request():   # 定义一个钩子函数, 所有的请求，都会预处理
            self.app.thread_local.request_id = request.headers.get("X-Global-Request-Id", "-")

    def start(self):
        self.log.info("Restful api service starting...")
        bind_ip = self.conf.get('flask', 'ip')
        bind_port = self.conf.get_int('flask', 'port')

        self.service_thread = ServerThread(self.app, self.log, flask_bind_ip=bind_ip, flask_bind_port=bind_port)
        self.service_thread.start()

        # 处理ha 检查
        self.api.add_resource(Pong, '/', resource_class_kwargs={})
        return True

    def stop(self):
        self.service_thread.shutdown()
        return True

    def wait_exit(self, timeout=None):
        self.service_thread.join(timeout)

    def is_alive(self):
        return self.service_thread.isAlive()
