import sys
import os
import re
import subprocess
import collections

from threading import Timer

# comment
# 使用subprocess模块的Popen调用外部程序，如果 stdout或 stderr 参数是 pipe，并且程序输出超过操作系统的 pipe size时，
# 如果使用 Popen.wait() 方式等待程序结束获取返回值，会导致死锁，程序卡在 wait() 调用上。
# 那死锁问题如何避免呢？官方文档里推荐使用 Popen.communicate()。这个方法会把输出放在内存，而不是管道里，
# 所以这时候上限就和内存大小有关了，一般不会有问题。而且如果要获得程序返回值，可以在调用 Popen.communicate() 之后取
# Popen.returncode 的值。
# 结论：如果使用 subprocess.Popen，就不使用 Popen.wait()，而使用 Popen.communicate() 来等待外部程序执行结束。


# 异常
# subprocess.TimeoutExpired
# subprocess.CalledProcessError

SHELL_TIME_OUT = 30


def kill_command(process: subprocess.Popen, timeout: int):
    try:
        process.kill()
        process._timeout = True
        # if isinstance(process.args, list):
        #     cmd = " ".join(process.args)
        # elif isinstance(process.args, str):
        #     cmd = process.args
        #
        # raise subprocess.TimeoutExpired(cmd, timeout)
        # raise TimeoutError()
    except (OSError, SystemError):
        pass


class ShellExec:
    subprocess_result = collections.namedtuple("subprocess_result", "stdout stderr ret_code")

    @staticmethod
    def call(cmd, **kwargs):
        # 设置自己的专属异常
        expect = kwargs.pop("expect", [dict(ret_code=[os.EX_OK], stdout=None, stderr=None)])

        # 调用Popen 执行shell 命令
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=True)
        # 设置一个超时标签
        process._timeout = False

        # 设置定时器， 防止命令长时间未完成， 造成主线程被等待
        timeout = kwargs.get('timeout', SHELL_TIME_OUT)
        timer = Timer(timeout, kill_command, [process, timeout])

        def match(ret_code, out, err, expected):
            exit_ok = ret_code in expected["ret_code"]
            stdout_ok = re.search(expected.get("stdout") or "", out)
            stderr_ok = re.search(expected.get("stderr") or "", err)
            return exit_ok and stdout_ok and stderr_ok

        try:
            # 启动定时器
            timer.start()
            # 等待执行完成
            out, err = process.communicate()
            ret_code = process.poll()
            # out 解码
            out = out.decode(sys.stdin.encoding)
            # err 解码
            err = err.decode(sys.stdin.encoding)

            # 超时处理
            if process._timeout:
                raise subprocess.TimeoutExpired(cmd, timeout)

            # 当命令中使用到grep时，如果没有结果，ret_code 将为非0值
            if len(out) == 0 and len(err) == 0:
                ret_code = 0

            # 当stdout中有内容，stderr 为空时，尝试返回
            if len(out) > 0 and len(err) == 0:
                ret_code = 0

            # 执行出错
            if not any(match(ret_code, out, err, exp) for exp in expect):
                e = subprocess.CalledProcessError(ret_code, cmd, output=out)
                e.stdout, e.stderr = out, err
                raise e

            # 返回执行结果
            return ShellExec.subprocess_result(out, err, ret_code)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise e
        finally:
            timer.cancel()
            process.stdout.close()
            process.stderr.close()


# （系统中）是否存在cmd
def exist_command(cmd):
    try:
        ShellExec.call("command -v %s >/dev/null 2>&1 || { echo >&2 \" %s it's not installed.\"; exit 1; }"
                       % (cmd, cmd))
        return True
    except subprocess.CalledProcessError:
        return False


# 执行出错返回None的
def shell_with_no_exception(cmd, **kwargs):
    try:
        sub_ret = ShellExec.call(cmd, **kwargs)
        return sub_ret.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(str(e))


if __name__ == "__main__":
    shell_with_no_exception("lspci|egrep \"LSI Logic / Symbios Logic MegaRAID SAS|LSI Logic / Symbios Logic Device 0017|Broadcom / LSI MegaRAID SAS\"")