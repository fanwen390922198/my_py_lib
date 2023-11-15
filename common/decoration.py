import time
from functools import wraps
from .error_def import *
from .base_type import request_return
from flask import request

# from ees_manager.common.log import get_logger

__all__ = ["retry", "ees_api_exception", "config_to_attribute", "ees_api_request_params"]


def run_cost_for_test(func):
    def wrapper(*args, **kwargs):
        # try:
        # start_time = time.time()
        ret = func(*args, **kwargs)
        # over_time = time.time()  # 程序结束时间
        # print("{} run {:.3f} s".format(func.__name__, over_time-start_time))
        return ret
    return wrapper


def log(msg, logger=None):
    if logger:
        logger.warning(msg)
    else:
        print(msg)


def retry(exceptions, total_tries=4, initial_wait=0.5, backoff_factor=2, logger=None):
    """
    calling the decorated function applying an exponential backoff.
    Args:
        exceptions: Exeption(s) that trigger a retry, can be a tuble
        total_tries: Total tries
        initial_wait; Time to first retry
        backoff_factor: Backoff multiplier (e.g. value of 2 will double the delay each retry).
        logger: logger to be used, if none specified print

    """
    def retry_decorator(f):
        @wraps(f)
        def func_with_retries(*args, **kwargs):
            _tries, _delay = total_tries + 1, initial_wait
            while _tries > 1:
                try:
                    log(f'{total_tries + 2 - _tries}. try:', logger)
                    return f(*args, **kwargs)
                except exceptions as e:
                    _tries -= 1
                    print_args = args if args else 'no args'
                    if _tries ==1:
                        msg = str(f'Function: {f.__name__}\n'
                                  f'Failed despite best efforts after {total_tries} tries.\n' 
                                  f'args: {print_args}, kwargs: {kwargs}')
                        log(msg, logger)
                        raise
                    msg = str(f'Function: {f.__name__}\n'
                              f'Exception: {e}\n'
                              f'Retrying in {_delay} seconds!, args: {print_args}, kwargs: {kwargs}\n')
                    log(msg, logger)
                    time.sleep(_delay)
                    _delay *= backoff_factor
        return func_with_retries
    return retry_decorator


SYSTEM_EXCEPTIONS = ["ValueError"]


def ees_api_exception(func):
    def wrapper(*args, **kwargs):
        api_err_code = POST_REQUEST_FAILED
        try:
            _log = args[0].log
            return func(*args, **kwargs)
        except Exception as e:
            _log.exception(e)
            language = request.headers.get("X-Request-Language", "en_GB")

            # get exception type
            e_type_name = type(e).__name__
            if e_type_name in dir(ees_manager_exception) or e_type_name in SYSTEM_EXCEPTIONS:
                if isinstance(e, ees_manager_exception.EesI18lException):
                    api_err_msg = e.translate(languages=language)
                else:
                    api_err_msg = str(e)
            else:
                api_err_msg = "System Internal Error!"

            if func.__name__.find("get") != -1:
                api_err_code = GET_REQUEST_FAILED
            elif func.__name__.find("delete") != -1:
                api_err_code = DELETE_REQUEST_FAILED
            if func.__name__.find("put") != -1:
                api_err_code = PUT_REQUEST_FAILED

            return request_return(http_code=500, api_err_code=api_err_code, api_err_msg=api_err_msg, language=language)

    return wrapper


def config_to_attribute(section="", keys=[]):
    def wrapper(func):
        def auto_set_attribute(*args, **kwargs):
            try:
                _self = args[0]
                # _log = _self.log
                _conf = _self.conf
                for key in keys:
                    (_key_name, _type, _default_value) = key.split(":")
                    _value = _conf.get(section, _key_name) if _conf.has_option(section, _key_name) \
                        else _default_value

                    if _type == "int":
                        _value = int(_value)

                    elif _type == "bool":
                        _value = bool(_value)

                    setattr(_self, _key_name, _value)

                return func(*args, **kwargs)
            except Exception as e:
                raise e

        return auto_set_attribute
    return wrapper


class AttrContainer(object):
    """
    属性容器
    """
    def __init__(self):
        pass


def get_func_used_conf_args(_self, config_args):
    try:
        _conf = _self.conf
        _self.config_args = AttrContainer()
        for item in config_args:
            if "section" not in item or "keys" not in item:
                continue
            section = item.get("section")
            for key in item.get("keys"):
                (_key_name, _type, _default_value) = key.split(":")
                _value = _conf.get(section, _key_name) if _conf.has_option(section, _key_name) \
                    else _default_value
                if _type == "int":
                    _value = int(_value)
                elif _type == "bool":
                    _value = bool(_value)

                setattr(_self.config_args, _key_name, _value)
    except Exception as e:
        raise e


# 值区间判断
def verify_value_len(p_name, value_len: int, len_range: list):
    if len(len_range) == 0:
        pass
    elif len(len_range) == 1:
        if value_len < len_range[0]:
            raise ValueError(f"Parameters ‘{p_name}’ length must less than {len_range[0]} "
                             f"characters!")
    elif len(len_range) == 2:
        if not len_range[0] <= value_len <= len_range[1]:
            raise ValueError(f"Parameters ‘{p_name}’ length must between [{len_range[0]}, "
                             f"{len_range[1]}] characters!")


# 指定值样本判断
def verify_value_in(p_name, p_value, value_samples: list):
    if p_value not in value_samples:
        s_sample = ",".join(value_samples)
        raise ValueError(f"Parameters ‘{p_name}’ must in '{s_sample}'!")


def verify_v_range(p_name, p_value, v_range: list):
    if len(v_range) == 0:
        pass
    elif len(v_range) == 1:
        if p_value < v_range[0]:
            raise ValueError(f"Parameters ‘{p_name}’ must less than {v_range[0]}!")
    elif len(v_range) == 2:
        if not v_range[0] <= p_value <= v_range[1]:
            raise ValueError(f"Parameters ‘{p_name}’ must between [{v_range[0]},"
                             f"{v_range[1]}]!")


def ees_api_request_params(func):
    def wrapper(*args, **kwargs):
        try:
            _self = args[0]
            method = request.method.lower()
            if method == "get":
                request_data = request.args
            elif method in ["put", "post"]:
                request_data = request.get_json()

            class_name = type(_self).__name__
            global_request_param = ees_api_params.global_request_param
            if class_name in global_request_param and method in global_request_param.get(class_name):
                # 如果配置了请求参数
                if "request_args" in global_request_param[class_name][method]:
                    # 创建一个对象来储存请求参数
                    _self.request_args = AttrContainer()
                    # 获取请求参数配置
                    request_params = global_request_param.get(class_name).get(method).get("request_args")
                    for param in request_params:
                        p_name = param["name"]  # 请求参数名称
                        # 判断值是否存在
                        if p_name not in request_data:
                            if param["need"]:
                                raise ValueError(f"Missing parameters {p_name}")
                            else:
                                # 非必须, 又没有设置，则使用default值
                                setattr(_self.request_args, p_name, param.get("default", None))
                                continue
                        else:
                            p_value = request_data.get(p_name)

                        # 值类型判断
                        if type(p_value) != param["type"]:
                            raise ValueError(f"Parameters {p_name} type must be {param['type'].__name__}")

                        # 值区间判断
                        if "len_range" in param:
                            verify_value_len(p_name, len(p_value), param["len_range"])

                        # 指定值
                        elif "v_in" in param:
                            verify_value_in(p_name, p_value, value_samples=param["v_in"])

                        elif "v_range" in param:
                            verify_v_range(p_name, p_value, v_range=param["v_range"])

                        #  设置值为请求参数
                        setattr(_self.request_args, p_name, p_value)

                # # 如果配置了使用的配置参数
                # if "config_args" in global_request_param[class_name][method]:
                #     # 获取配置参数
                #     config_args = global_request_param.get(class_name).get(method).get("config_args")
                #     get_func_used_conf_args(_self, config_args)

            return func(*args, **kwargs)
        except Exception as e:
            raise e

    return wrapper


# @retry(Exception, total_tries=4, initial_wait=1)
# def test_func(*args, **kwargs):
#     rnd = random.random()
#     if rnd < .2:
#         raise ConnectionAbortedError('Connection was aborted: (')
#     elif rnd < .4:
#         raise ConnectionRefusedError('Connection was refused: /')
#     elif rnd < .6:
#         raise ConnectionResetError('Guess the Connection was reset')
#     elif rnd < .8:
#         raise TimeoutError('This took too long')
#     else:
#         return "Yay!!"
#
#
# print(test_func("hi", "bye", hi='ciao'))
#
