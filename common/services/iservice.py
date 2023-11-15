# 服务基类
class EsAGwServices(object):
    def __init__(self, conf, log):
        self.conf = conf
        self.log = log

    def init_service(self):
        return True

    def start(self):
        return True

    def stop(self):
        return True

