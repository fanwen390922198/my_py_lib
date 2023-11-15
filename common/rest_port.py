# 此类为RestApi 注册类， 使用者需要自己实现 _register_rest_api
from flask_restful import Resource
# from ees_manager.common.decoration import ees_api_exception, ees_api_request_params

__all__ = ["RestPort", "EesRestApi"]


class RestPort:
    def __init__(self, log, flask_api):
        self.log = log
        self.api = flask_api
        # self._register_rest_api()

    def _register_rest_api(self):
        """
            register your own api
        @return:
        """
        # API 类实现
        class TestApi(Resource):
            def __init__(self, log=None):
                super(TestApi, self).__init__()
                self.log = log

            def get(self):
                self.log.debug("test api...")
                return {"ret_code": 0, "message": "", "data": "hello test!"}, 200

        # api 类参数
        kwargs = {"log": self.log}

        # 向flask 框架添加api
        self.api.add_resource(TestApi, '/api/testapi', resource_class_kwargs=kwargs)


class EesRestApi(Resource):
    """
    EES 工程 rest api 基类
    """
    # method_decorators = [ees_api_request_params, ees_api_exception]

    def __init__(self, **kwargs):
        super(EesRestApi, self).__init__()
        self.log = kwargs.get("log")
        self.conf = kwargs.get("conf")
        self.db = kwargs.get("db_service") or kwargs.get("db")

