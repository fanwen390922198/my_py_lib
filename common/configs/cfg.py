# -*- coding:utf-8 -*-
import configparser
import os

__all__ = ["Config", "set_config_to_object_attr", "AttrContainer", "get_section_options"]


class Config(object):
    def __init__(self, cfg_file):
        """self.cfg holds the ConfigParser
        :param cfg_file: the full path to the config file
        """
        self.cfg_file = cfg_file
        self.cfg = None
        if os.path.exists(cfg_file):
            self.cfg_file = cfg_file
            self.cfg = configparser.ConfigParser(strict=False)
            self.cfg.read(cfg_file)
        else:
            msg = "Config File Not Found - " + cfg_file
            raise IOError(msg)

    def has_option(self, section, option):
        return self.cfg.has_option(section, option)

    def get(self, section, option, default=None):
        """get option value by section and option name"""
        try:
            kwargs = {}
            if default is not None:
                kwargs["fallback"] = default

            return self.cfg.get(section, option, **kwargs)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            raise e

    def get_int(self, section, option, default=None):
        try:
            kwargs = {}
            if default is not None:
                kwargs["fallback"] = default

            return self.cfg.getint(section, option, **kwargs)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            raise e

    def get_float(self, section, option, default=None):
        try:
            kwargs = {}
            if default is not None:
                kwargs["fallback"] = default

            return self.cfg.getfloat(section, option, **kwargs)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            raise e

    def get_bool(self, section, option, default=None):
        try:
            kwargs = {}
            if default is not None:
                kwargs["fallback"] = default

            return self.cfg.getboolean(section, option, **kwargs)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            raise e

    def get_items_of_section(self, section):
        return self.cfg.items(section)


def set_config_to_object_attr(conf, configs=[], object_handle=None):
    """
    将配置转化为对象的属性
    :param conf: Config Object
    :param configs: [["{section}", "{option}", default_value],]
    :param object_handle:
    :return:
    """
    try:
        if not isinstance(conf, Config):
            raise TypeError("conf must be Config class")

        for (section, option, default) in configs:
            if type(default) == int:
                setattr(object_handle, option, conf.get_int(section, option, default))
            elif type(default) == bool:
                setattr(object_handle, option, conf.get_bool(section, option, default))
            elif type(default) == float:
                setattr(object_handle, option, conf.get_float(section, option, default))
            else:
                setattr(object_handle, option, conf.get(section, option, default))

    except AttributeError:
        raise


class AttrContainer(object):
    """
    属性容器
    """
    def __init__(self):
        pass


def get_section_options(conf, section, configs={}, object_handle=None):
    """
    获取域里面的所有配置，并设置成属性
    :param conf:
    :param section:
    :param configs:
    :param object_handle:
    :return:
    """
    try:
        for (option, def_value) in configs.items():
            if def_value is None:
                setattr(object_handle, option, conf.get(section, option))
            else:
                if type(def_value) == int:
                    setattr(object_handle, option, conf.get_int(section, option, def_value))

                elif type(def_value) == bool:
                    setattr(object_handle, option, conf.get_bool(section, option, def_value))

                elif type(def_value) == float:
                    setattr(object_handle, option, conf.get_float(section, option, def_value))

                else:
                    setattr(object_handle, option, conf.get(section, option, def_value))

    except AttributeError:
        raise


