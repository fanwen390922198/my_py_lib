from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager


from ees_manager.common.services.iservice import EsAGwServices


class DbService(EsAGwServices):
    def __init__(self, conf, log):
        super(DbService, self).__init__(conf, log)
        self.db_engine = None
        self.Base = None
        self._session = None

    def init_service(self, init_db=True):
        try:
            connection = self.conf.get("mysql", "connection") if self.conf.has_option("mysql", "connection") else ""
            if connection is None or len(connection) == 0:
                raise ValueError("Mysql connection is need, please check your config file!")
            debug_sql = self.conf.get_bool("mysql", "debug_sql") if self.conf.has_option("mysql", "debug_sql") else False

            # 创建引擎
            self.db_engine = create_engine(connection, pool_size=30, max_overflow=5, pool_pre_ping=True,
                                           pool_use_lifo=True, pool_recycle=1200, echo=debug_sql)

        except Exception as e:
            args = getattr(e, "args", ())
            if str(args).find("1050") != -1:
                self.log.warning(e.args[0])
            else:
                raise e

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session_class = sessionmaker(bind=self.db_engine)
        session = session_class()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
