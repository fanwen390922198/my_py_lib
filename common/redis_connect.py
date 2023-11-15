import redis
from rediscluster import StrictRedisCluster


class RedisConnect(object):
    def __init__(self, conf, log):
        self.conf = conf
        self.log = log
        # redis 连接句柄
        self.redis_conn = None
        # 发布订阅句柄
        self.pubsub = None

    def _connect_redis(self):
        """
        连接到redis server
        """
        try:
            redis_connection = self.conf.get('redis', 'redis_connection') \
                if self.conf.has_option('redis', 'redis_connection') else "127.0.0.1:6379"
            all_hosts = []
            for host_port in redis_connection.split(","):
                (host, port) = host_port.split(":")
                all_hosts.append(dict(
                    host=host,
                    port=port
                ))
            if len(all_hosts) > 1:  # 集群模式
                # self.log.debug("redis cluster: {}".format(all_hosts))
                kwargs = {"startup_nodes": all_hosts, "decode_responses": True, "socket_connect_timeout": 3}
                if self.conf.has_option('redis', 'password'):
                    kwargs["password"] = self.conf.get('redis', 'password')

                self.redis_conn = StrictRedisCluster(**kwargs)
            elif len(all_hosts) == 1:  # 单节点模式
                self.redis_conn = redis.Redis(host=all_hosts[0]['host'], port=all_hosts[0]['port'],
                                              decode_responses=True)

            # 生成一个订阅对象
            self.pubsub = self.redis_conn.pubsub()
        except Exception as e:
            self.log.error("connect to redis failed : {}".format(str(e)))
            raise e
