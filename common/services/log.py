import os
import logging
import threading
from logging import FileHandler
from logging.handlers import TimedRotatingFileHandler

# DEFAULT_FOMAT = '%(asctime)-15s [%(levelname)-5s] [%(pathname)s(line:%(lineno)d)] [-] %(message)s'
DEFAULT_FOMAT = '%(asctime)-15s [%(levelname)-5s] [%(filename)s:%(funcName)s (line:%(lineno)d)] [%(log_id)s] %(' \
                'message)s '
DEFAULT_LOG_LEVEL = 'DEBUG'
DEFAULT_LOG_FILE = '/var/log/ees_manager/es_agw.log'

thread_local = threading.local()


class ContextFilter(logging.Filter):
    """
    logging Filter
    """

    def filter(self, record):
        """
        threading local 获取logid
        :param record:
        :return:
        """
        log_id = thread_local.request_id if hasattr(thread_local, 'request_id') else '-'
        record.log_id = log_id

        return True


def get_logger(log_flag, cfg=None, console=False):
    logger = logging.getLogger(log_flag)
    if len(logger.handlers) == 0:
        fm = logging.Formatter(DEFAULT_FOMAT)
        log_level = DEFAULT_LOG_LEVEL
        log_file = DEFAULT_LOG_FILE
        if cfg is not None:
            log_level = cfg.get('log', 'log_level')
            log_file = cfg.get('log', 'log_file')

        dir_name = os.path.dirname(log_file)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        logger.setLevel(log_level.upper())
        # file_handler = TimedRotatingFileHandler(log_file, when='D', interval=3, backupCount=2)
        file_handler = FileHandler(log_file)
        file_handler.setFormatter(fm)
        logger.addHandler(file_handler)

        log_id_filter = ContextFilter()
        file_handler.addFilter(log_id_filter)

        if console:
            # [2] StreamHandler for debug purpose
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(fm)
            logger.addHandler(console_handler)

    return logger




