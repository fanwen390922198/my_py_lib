#!/usr/bin/env python -u
# -*- coding: utf-8 -*-

# System
import sys
import signal
import time

# Data:
import json

# Processes/Threads
import pexpect
import threading

# Types
import collections
import arrow

from enum import Enum, unique
# Logging


# rclone 运行状态
class RcloneProcessStatusEnum(Enum):
    NOT_UP = 0    # no up
    UP = 1        # up
    DOWN_WITH_ERROR = 2      # down
    DOWN_WITH_INTERUAPT = 3  # down
    DOWN_WITH_OVER = 4      # down


# rclone 消息类型
class RcloneMsgType(Enum):
    COPY = 0   # copy 消息
    TRANSFER = 1    # transfer 消息
    ERROR = 2  # error 消息
    SKIP = 3  # skip 消息


# rclone check 结果类型
class RcloneCheckType(Enum):
    DATA_NOT_EXISTS = 0   # 数据不存在
    DATA_NOT_CONSISTENCE = 1    # 数据不一致
    DATA_CONSISTENCE = 2  # 数据一致


RETURN_MAX_MSGS = 300
MAX_ERROR = 20


class PyClone(object):
    """
    Parameters
    ----------

    binPath : :obj:`str`, optional
        Path to rclone binary at either the host level (e.g. ``/usr/bin/env rclone``) or
        container level (e.g. ``docker-compose --no-ansi --file /path/to/docker-compose.yaml run rclone``)

    messageBufferSize : :obj:`int`, optional
        Maximum number of messages to hold in buffer for pulling out with :any:`PyClone.readline()`.
    .. seealso::
        :any:`PyClone.binPath()` for updating the binary path to rclone after the class has been instantiated.
    """

    def rclone_status(self):
        if self.rclone_proc is None:
            return RcloneProcessStatusEnum.NOT_UP.value

        if self.rclone_proc:
            # 获取proc 状态
            try:
                if self.rclone_proc.terminated:
                    if self.rclone_proc.signalstatus is not None and self.rclone_proc.exitstatus is None:
                        return RcloneProcessStatusEnum.DOWN_WITH_INTERUAPT.value    # 被中断了

                    elif self.rclone_proc.exitstatus is not None and self.rclone_proc.exitstatus != 0:
                        # 此处是针对local 文件系统中出现的异常情况
                        last_error = self.get_last_error()
                        self.error_queue.append(last_error)
                        if last_error is not None and last_error.find("source file is being updated") != -1:
                            return RcloneProcessStatusEnum.DOWN_WITH_OVER.value  # 执行完毕退出
                        else:
                            return RcloneProcessStatusEnum.DOWN_WITH_ERROR.value   # 异常退出

                    elif self.rclone_proc.exitstatus is not None and self.rclone_proc.exitstatus == 0:
                        return RcloneProcessStatusEnum.DOWN_WITH_OVER.value   # 执行完毕退出
                else:
                    return RcloneProcessStatusEnum.UP.value  # rclone 运行中
            except Exception as e:
                self.logger.error("rclone is down with {}".format(str(e)))
                return RcloneProcessStatusEnum.NOT_UP.value

    def __init__(self, *, binPath="/usr/bin/rclone", binSuffix='', messageBufferSize=10000, log=None, timeout=30,
                 read_log_threads=2, rclone_log_level=2):
        """
        Constructor used for initializing an instance of PyClone.
        @param binPath:
        @param binSuffix:
        @param messageBufferSize:
        @param log:
        """

        self.logger = log
        self.timeout = timeout
        self.read_log_threads = read_log_threads
        self.rclone_log_level = rclone_log_level

        # Rclone
        # Specified path or fallback to $PATH
        # self.logger.debug('__init__() : setting binary path')
        # self.logger.debug(f'binPath() : {binPath}')
        if binPath:
            self.binPath = binPath

        # Set binary suffix
        # self.logger.debug(f'__init__() : setting binary suffix : {binSuffix}')
        self.binSuffix = binSuffix
        self.flags = {}  # clear flags

        # Processes
        self.rclone_proc = None  #: `rclone` process spawned with `pexpect`.
        self.start_rclone_thread = None  #: Thread that starts rclone process and writes to message buffer.

        # Internal
        # Short buffer for Rclone output to dump to, and for Python to pull from.
        # self.logger.debug(f'__init__() : setting self.message_queue with a maximum length of {messageBufferSize}')
        self.message_queue = collections.deque(maxlen=messageBufferSize)

        __lock = threading.Lock()  #: Used to avoid simultaneous runs of rclone within a PyClone instance.
        self.error_queue = collections.deque(maxlen=MAX_ERROR)

        # self.mutex = threading.Lock()

        # 注册信号
        tempSignals = [
            'SIGHUP',  # Usually, a reload request.
            'SIGINT',  # ^C
            'SIGQUIT',  # ^\
            'SIGCONT',  # Usually, a resumed process.
            'SIGTERM',  # `kill procID` or `pkill myApp.py` and systemd's default kill signal.
            'SIGTSTP',  # ^Z
        ]

        # self.logger.debug(f'__init__() : binding signals to sigTrap() : {", ".join(tempSignals)}')
        self.signals(self.sigTrap, *tempSignals)

    def add_error(self, exception):
        self.log.error(exception)
        if len(self.error_queue) == MAX_ERROR:
            self.error_queue.clear()

        self.error_queue.append(exception)

    def get_last_error(self):
        if len(self.error_queue) > 0:
            return self.error_queue.pop()
        else:
            return None

    def get_pid(self):
        return self.rclone_proc.pid

    def queue_len(self):
        return len(self.message_queue)

    def signalsDict(self, k=None):
        """
        Used for looking up a signal by its integer or string value, or a dictionary listing of all available signals.
        @param k: :obj:`int` or :obj:`str`, optional
        @return: obj:`int`, :obj:`str`, or :obj:`dict`
        Returns a dictionary by default, or the desired signal lookup (`string` if an `integer` is given,
        or `integer` if a `string` is given).
        """

        d = {str(v): int(k) for v, k in signal.__dict__.items() if v.startswith('SIG') and not v.startswith('SIG_')}

        if isinstance(k, str) and k.upper() in d.keys():
            return d[k]

        elif isinstance(k, int) and k in d.values():
            return {v: k for k, v in d.items()}[k]

        elif k is None:
            return d

        else:
            return None

    def sigTrap(self, sigNum, currFrame):
        self.logger.debug(f'sigTrap() : sigNum={sigNum}, currFrame={currFrame}')
        self.stop()
        sys.exit()

    def signals(self, cb, *keys):
        """
        Bind a callback to an arbitrary number of signals.
        @param cb: :obj:`Function` or :obj:`Method`
            Callback that's executed when a signal occurs that it's been bound to.
        @param keys: :obj:`str`
            Variable length list of signals to bind callback to.
        @return: bool `True` if successful, `False` if an error occurs.

        ---------
        An example for registering a callback to multiple signals:
        .. code-block:: python
            def myCallback( self, sigNum, currFrame ):
                print( f'My callback received sigNum={ sigNum } and currFrame={ currFrame }' )
                pass # END METHOD : My callback

            def __init__( self ):
                self.signals(
                    self.myCallback,
                    'SIGINT',   # ^C
                    'SIGTERM',  # `kill procID` or `pkill myApp.py` and systemd's default kill signal.
                )
        .. seealso::

            * :any:`PyClone.sigTrap()`

        """
        r = None
        try:
            for currKey in keys:
                currKey = currKey.upper()
                if currKey.startswith('SIG') and not currKey.startswith('SIG_') and hasattr(signal, currKey):
                    sigNum = getattr(signal, currKey)
                    signal.signal(sigNum, cb)
                    # self.logger.debug(f"Signal : bind '{currKey}' to {cb.__name__}().")
                    r = True
        except Exception as e:
            self.logger.critical(f"{self.name} : {e}")
            r = False
        finally:
            return r

    def addFlag(self, key, value=None):
        self.logger.info(f"Add flag : '{key}'" + (f" = '{value}'" if value else "") + ".")
        if key not in self.flags:
            self.flags.update({key: value})
            return True
        else:
            return False

    def removeFlag(self, key):
        self.logger.debug(f'removeFlag() : key={key}')

        if key in self.flags:
            self.logger.info(f"Remove flag : '{key}'.")
            del self.flags[key]
            return True
        else:
            self.logger.warning(f'removeFlag() : key not found : {key}')
            return False

    def updateFlag(self, key, value=None):
        self.logger.debug(f'updateFlag() : key={key}, value={value}')
        return self.removeFlag(key) and self.addFlag(key, value)

    def flagsToString(self):
        """
        Iterates all flags (and if applicable, values) stored in :any:`PyClone.flags` with :any:`PyClone.addFlag()`
        and converts them to command line arguments that are used when spawning the `rclone` process.
        @return: str
            Combination of flags (and where applicable, reciprocal values).
        """
        r = ''
        for k, v in self.flags.items():
            # Add key
            r += f'--{k} '
            # Add value
            if v is not None:
                r += f'{v} '

        self.logger.debug(f'flagsToString() : return : {r}')
        return r

    def stop(self):
        # Attempt to close the process before trying to terminate it.
        if hasattr(self.rclone_proc, 'close'):
            self.logger.debug('stop() : process : close( force=True )')
            self.rclone_proc.close(force=True)

        # Terminate process
        if hasattr(self.rclone_proc, 'terminate'):
            self.logger.debug('stop() : process : terminate()')
            if not self.rclone_proc.terminate():
                self.logger.debug('stop() : process : terminate( force=True )')
                self.rclone_proc.terminate(force=True)

        self.logger.warning("is_alive: {}".format(self.rclone_proc.isalive()))

        # Join thread back to main
        if hasattr(self.start_rclone_thread, 'join') and self.start_rclone_thread.is_alive():
            self.logger.debug('stop() : thread : join() : start')
            # self.self.start_rclone_thread.join()
            self.logger.debug('stop() : thread : join() : finish')

        if hasattr(self.rclone_proc, 'exitstatus'):
            self.logger.debug(f'stop() : process : exit status={self.rclone_proc.exitstatus}, '
                              f'signal status={self.rclone_proc.signalstatus}')
            return self.rclone_proc.exitstatus, self.rclone_proc.signalstatus

    def tailing(self):
        """
        Used by your program for determining if a loop should continue checking for output from `rclone`,
        based upon multiple conditions.
        An example for continuously printing out data from `rclone`:
        .. code-block:: python
            while rclone.tailing():
                if rclone.readline():
                    print( rclone.line, flush=True )
                time.sleep( 0.5 )
        .. seealso::
            :any:`PyClone.readline()`
        @return: :obj:`bool`
            Returns `True` if a process is still running and there's the potential for messages to be added to
            the buffer, else this returns `False`.
        """

        # Message queue
        if self.message_queue:
            self.logger.debug('tailing() : return : True')
            return True

        # No message queue to process
        elif not isinstance(self.message_queue, collections.deque):
            self.logger.debug('tailing() : return : False')
            return False

        # Spawned process has finished
        elif hasattr(self.rclone_proc, 'isalive') and not self.rclone_proc.isalive():
            self.logger.debug('tailing() : return : False')
            return False

        # Process closed and removed
        elif self.rclone_proc is None:
            self.logger.debug('tailing() : return : False')
            return False

        # Process still running
        else:
            self.logger.debug('tailing() : return : True')
            return True

    def readline(self):
        """
        Mostly used in conjunction with :any:`PyClone.tailing()`, this retrieves the oldest line from
        :any:`the message buffer <PyClone.self.message_queue>` that's filled by rclone,
        with a buffer size set when :any:`initializing the class <PyClone.__init__>`.
        .. seealso::
            :any:`PyClone.tailing()`

        @return: :obj:`bool`
            Returns `True` if a line was removed from the message buffer and stored in :any:`PyClone.line`,
            otherwise returns `False`.
        """
        if self.message_queue:
            try:
                line = self.message_queue.popleft()
                if line:
                    return line
            except IndexError as e:
                self.logger.warning("message queue is empty!")
                return None

        return None

    def readlines(self, max_line=RETURN_MAX_MSGS):
        msgs = []
        msg_nums = len(self.message_queue)
        if msg_nums > max_line:
            msg_nums = max_line

        while msg_nums > 0:
            try:
                line = self.message_queue.popleft()
                msg_nums -= 1
                if line:
                    msgs.append(line)
            except IndexError as e:
                self.logger.warning("message queue is empty!")
                break
        return msgs

    def clearBuffer(self):
        """
        Clear all messages in the buffer that were added by an `rclone` action.
        @return:
        """
        self.logger.debug('Clearing message buffer')
        self.message_queue.clear()

    def _get_msg(self):
        n = 0
        skips = 0
        while not self.rclone_proc.eof():
            msg = {}
            rlone_out = self.rclone_proc.readline().strip()
            # self.logger.debug(f"Get Msg: {rlone_out}")

            try:
                line = json.loads(rlone_out.decode().strip())
                if line["msg"].find("Copied") != -1:
                    msg_type = RcloneMsgType.COPY.value
                    msg_data = {
                        "object": line["object"],
                        "time": arrow.get(line["time"]).datetime
                    }

                elif line["msg"].find("Transferred") != -1:
                    msg_type = RcloneMsgType.TRANSFER.value
                    msg_data = {}
                    if "stats" in line:
                        msg_data["elapsedTime"] = line["stats"]["elapsedTime"]
                        msg_data["errors"] = line["stats"]["errors"]
                        msg_data["speed"] = line["stats"]["speed"]
                        msg_data["totalBytes"] = line["stats"]["totalBytes"]
                        msg_data["totalTransfers"] = line["stats"]["totalTransfers"]
                        msg_data["bytes"] = line["stats"]["bytes"]
                        msg_data["transfers"] = line["stats"]["transfers"]

                    if line["stats"]["errors"] > 0:
                        self.error_queue.append(line["stats"]["lastError"])

                elif line["msg"].find("Unchanged skipping") != -1:
                    skips += 1
                    msg_type = RcloneMsgType.SKIP.value
                    msg_data = {"object": line["object"]}

                else:
                    continue

                # elif line["level"] == "error":
                #     if line["msg"].find("File not in") != -1:
                #         msg_type = RcloneMsgType.CHECK_FILE_MISSING.value
                #         msg_data = {"object": line["object"]}
                #
                #     elif line["msg"].find("Sizes differ") != -1:
                #         msg_type = RcloneMsgType.CHECK_FILE_DIFF.value
                #         msg_data = {"object": line["object"]}
                #     else:
                #         msg_type = RcloneMsgType.ERROR.value
                #         msg_data = {"object": line["object"], "msg": line["msg"]}

                msg["msg_type"] = msg_type
                msg["msg_data"] = msg_data

            # Probably noise from Docker Compose
            except json.JSONDecodeError as e:
                self.logger.error(rlone_out)
                if isinstance(rlone_out, bytes):
                    rlone_out = rlone_out.decode('utf-8')

                self.logger.error(rlone_out)
                if len(rlone_out) > 0:
                    for error_key in ["Failed", "failed", "error", "Error"]:
                        if error_key in rlone_out:
                            self.error_queue.append(rlone_out)
                            break
                # self.logger.debug(f'self.start_rclone_threadedProcess() : exception (JSON decoding error) : {e}')
                msg = {}
            except Exception as e:
                self.logger.error(rlone_out)
                # self.logger.error(f'self.start_rclone_threadedProcess() : {e}')
            finally:
                if msg:
                    # self.logger.debug(f'self.start_rclone_threadedProcess() : append message to buffer : {msg}')
                    self.message_queue.append(msg)
                    n += 1
                # else:
                #     time.sleep(1)

        self.logger.debug(f'{threading.current_thread().name}: rclone proc eof!')

        # self.logger.debug(f'{threading.current_thread().name}: get {n} copy msgs')
        # self.logger.debug(f'{threading.current_thread().name} : get {skips} skip msgs')

    def start_rclone_Process(self, *, action, source, remote, path):
        """
        The rclone process runs under this method as a separate thread, which is launched by :any:`PyClone.__launchThread()`.
        All available output from `rclone` is placed into :any:`the message buffer <PyClone.self.message_queue>` from this method.

        @param action: :obj:`str`
            Provided by a wrapper method such as :any:`PyClone.copy()` and passed to `rclone`.
        @param source: :obj:`str`
            Files to transfer.
        @param remote: :obj:`str`
            Configured service name.
        @param path: :obj:`str`
            Destination to save to.：
        @return:
        """
        self.logger.debug(f'self.start_rclone_threadedProcess() : action={action}, source={source}, remote={remote}, path={path}')
        self.logger.debug('touch() : acquire lock')
        # self.__lock.acquire()

        # It takes a moment for the process to spawn
        # self.self.rclone_proc = True
        if len(remote) > 0:
            cmdLine = f'bash -c "{self.binPath} {self.flagsToString()} --use-json-log --stats=5s ' \
                      f'--verbose={self.rclone_log_level} {action} {(source if source else "")} {remote}:{path} ' \
                      f'{self.binSuffix}"'
        else:
            cmdLine = f'bash -c "{self.binPath} {self.flagsToString()} --use-json-log --stats=5s ' \
                      f'--verbose={self.rclone_log_level} {action} {(source if source else "")} {path} ' \
                      f'{self.binSuffix}"'

        self.logger.debug(f'self.start_rclone_threadedProcess() : spawn process : {cmdLine}')
        self.rclone_proc = pexpect.spawn(
            cmdLine,
            echo=False,
            timeout=self.timeout   # 超时，防止无法退出
        )

        # 创建多个线程
        threads = []
        for i in range(self.read_log_threads):
            th = threading.Thread(target=self._get_msg, name=f"GetSubProcessLogThread{i}")
            threads.append(th)
            th.start()

        for th in threads:
            th.join()

        self.logger.debug('self.start_rclone_threadedProcess() : close process')
        self.rclone_proc.close(force=True)

        # self.logger.debug('self.start_rclone_threadedProcess() : release lock')
        # self.__lock.release()

    def __launchThread(self, *, action, source, remote, path):
        """
        This sets up and starts a thread with :any:`PyClone.self.start_rclone_threadedProcess()` used as the target,
        and is used by convenience/wrapper methods such as:
        * :any:`PyClone.copy()`
        * :any:`PyClone.sync()`
        * :any:`PyClone.delete()`
        * :any:`PyClone.purge()`

        @param action: :obj:`str`
            Provided by a wrapper method such as :any:`PyClone.copy()` and passed to `rclone`.
        @param source: :obj:`str`
            Files to transfer.
        @param remote: :obj:`str`
            Configured service name.
        @param path: :obj:`str`
            Destination to save to.

        @return:
        """
        self.logger.debug(f'__launchThread() : action={action}, source={source}, remote={remote}, path={path}')
        self.start_rclone_thread = threading.Thread(
        target=self.start_rclone_Process,
        kwargs={
            'action': action,
            'source': source,
            'remote': remote,
            'path'	:	path,
            })
        self.logger.debug(f'__launchThread() : start thread')
        self.start_rclone_thread.start()

    def copy(self, *, source, remote, path):
        # self.logger.debug(f'copy() wrapping __launchThread() : source={source}, remote={remote}, path={path}')
        self.__launchThread(action='copy', source=source, remote=remote, path=path)

    def sync(self, *, source, remote, path):
        # self.logger.debug(f'sync() wrapping __launchThread() : source={source}, remote={remote}, path={path}')
        self.__launchThread(action='sync', source=source, remote=remote, path=path)

    def delete(self, *, remote, path, rmdirs=False):
        # self.logger.debug(f'delete() wrapping __launchThread() : remote={remote}, path={path}, rmdirs={rmdirs}')
        self.__launchThread(action='delete' + (' --rmdirs' if rmdirs else ''), source=None, remote=remote, path=path)

    def purge(self, *, remote, path):
        # self.logger.debug(f'purge() wrapping __launchThread() : remote={remote}, path={path}')
        self.__launchThread(action='purge', source=None, remote=remote, path=path)

    def check_file(self, source_path, remote, path):
        ret = True
        try:
            # self.__lock.acquire()
            self.rclone_proc = None
            if len(remote) > 0:
                cmdLine = f'bash -c "{self.binPath} {self.flagsToString()} --verbose=1 check ' \
                          f'{source_path} {remote}:{path} ' \
                          f'{self.binSuffix}"'
            else:
                cmdLine = f'bash -c "{self.binPath} {self.flagsToString()} --verbose=1 check ' \
                          f'{source_path} {path} ' \
                          f'{self.binSuffix}"'

            self.logger.debug(f'check() : spawn process : {cmdLine}')
            self.rclone_proc = pexpect.spawn(
                cmdLine,
                echo=False,
                timeout=self.timeout  # 超时，防止无法退出
            )

            # output = self.self.rclone_proc.read(size=-1).decode()
            self.rclone_proc.expect(pexpect.EOF)
            self.rclone_proc.close(force=True)
        except Exception as e:
            self.logger.error(str(e))
            ret = False
        finally:
            self.logger.debug('check() : release lock')
            # self.__lock.release()
            return ret

    def size(self, remote, path):
        try:
            self.rclone_proc = None
            cmd = f'bash -c "{self.binPath} size {remote}:{path} --json"'
            self.logger.debug(f'rclone size : spawn process : {cmd}')
            self.rclone_proc = pexpect.spawn(
                cmd,
                echo=False,
                timeout=self.timeout  # 超时，防止无法退出
            )
            output = self.rclone_proc.read(size=-1).decode()
            self.rclone_proc.expect(pexpect.EOF)
            self.rclone_proc.close(force=True)

            return json.loads(output.strip())
        except Exception as e:
            self.logger.exception(e)

