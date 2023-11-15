from abc import ABC
from taskflow import formatters
from taskflow.listeners import base
from taskflow.listeners import logging as logging_listener
from taskflow import task


def _make_taks_name(cls, addons=None):
    """Makes a Pretty name for a task class"""
    base_name = ".".join([cls.__module__, cls.__name__])
    extra = ''
    if addons:
        extra = ';{}'.format(", ".join([str(a) for a in addons]))

    return base_name + extra


class EesManagerTask(task.Task, ABC):
    """The root task class for ees_manager tasks.

    It automatically names the given task using the module and class that implement
    the given task as the task name.
    """

    def __init__(self, addons=None, **kwargs):
        super(EesManagerTask, self).__init__(_make_taks_name(self.__class__, addons), **kwargs)


class SpecialFormatter(formatters.FailureFormatter):

    #: Exception is an excepted case, don't include traceback in log if fails.
    _NO_TRACE_EXCEPTIONS = (ValueError)

    def __init__(self, engine):
        super(SpecialFormatter, self).__init__(engine)

    def format(self, fail, atom_matcher):
        # if fail.check(*self._NO_TRACE_EXCEPTIONS) is not None:
        # exc_info = None
        # exc_details = '%s%s' % (os.linesep, fail.pformat(traceback=False))
        # return (exc_info, exc_details)
        # else:
        return super(SpecialFormatter, self).format(fail, atom_matcher)


class DynamicLogListener(logging_listener.DynamicLoggingListener):
    """This is used to attach to taskflow engines while they are running.

    It provides a bunch of useful features that expose the actions happening
    inside a taskflow engine, which can be useful for developers for debugging,
    for operations folks for monitoring and tracking of the resource actions
    and more...
    """

    def __init__(self, engine,
                 task_listen_for=base.DEFAULT_LISTEN_FOR,
                 flow_listen_for=base.DEFAULT_LISTEN_FOR,
                 retry_listen_for=base.DEFAULT_LISTEN_FOR,
                 logger=None):
        super(DynamicLogListener, self).__init__(
            engine,
            task_listen_for=task_listen_for,
            flow_listen_for=flow_listen_for,
            retry_listen_for=retry_listen_for,
            log=logger, fail_formatter=SpecialFormatter(engine))
