from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.job import Job
import threading

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# 2021/9/24 把 scheduler 的创建移植到__init__ 中, 防止调用者在schedler还没有初始化之前调用add_job_xxx 接口而异常


class TimerCall:
    def __init__(self, top_manager, log):
        self.top = top_manager
        self.log = log
        self.scheduler = None
        self.job_id = 0
        self.lock = threading.Lock()  # 创建互斥锁
        self.jobs = {}
        self._create_scheduler()

    def _get_unique_jobid(self):
        job_id = 0
        self.lock.acquire()
        self.job_id += 1
        job_id = self.job_id
        self.lock.release()
        return job_id

    def pause_job(self, job_id):
        self.scheduler.pause_job(job_id)

    def resume_job(self, job_id):
        self.scheduler.resume_job(job_id)

    def modify_job(self, job_id, **changes):
        changes_kwargs = {}
        if "next_run_time" in changes:
            changes_kwargs["next_run_time"] = changes.pop("next_run_time")

        changes_kwargs["kwargs"] = changes
        self.scheduler.modify_job(job_id, None, **changes_kwargs)

    def _create_scheduler(self):
        jobstores = {
            'default': MemoryJobStore(),
            'default_test': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(30),
            'processpool': ProcessPoolExecutor(5)
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            # 'misfire_grace_time': 60
        }
        self.scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults,
                                             logger=self.log)

    def start(self):
        try:
            self.scheduler.start()
        except Exception as e:
            self.log.error(str(e))
            return False

        return True

    def stop(self):
        if self.scheduler is not None:
            self.clear()
            self.scheduler.shutdown()

    def add_job_run_interval(self, call_back_func, func_args=[], days=0, hours=0, mins=0, secs=0, **kwargs):
        """
        间隔性的定时任务(运行多次)
        :param call_back_func: 回调函数
        :param func_args: 回调函数入参列表
        :param days: 天数
        :param hours: 小时数 0~23
        :param minutes: 分钟数 0~59
        :param secs: 分钟数 0~59
        :return:
            job_id -1 失败 >0 成功
        """
        # job_id = str(self._get_unique_jobid())
        # func_args.append(job_id)
        job = self.scheduler.add_job(func=call_back_func,
                                     args=func_args,
                                     trigger='interval',
                                     # id=job_id,
                                     days=days,
                                     hours=hours,
                                     minutes=mins,
                                     seconds=secs,
                                    **kwargs)
        return job.id

    def add_job_run_once(self, call_back_func, func_args=[], date_time="2018-11-29 13:23:45"):
        """
        一次性任务
        :param call_back_func: 回调函数
        :param func_args: 回调函数入参列表
        :param date_time: 运行时间 支持str|datetime
        :return:
        """
        # func_args.append(job_id)
        job = self.scheduler.add_job(func=call_back_func,
                                     trigger='date',
                                     args=func_args,
                                     # id=job_id,
                                     run_date=date_time)

        return job.id

    def add_job_as_linux_cron(self, call_back_func, func_args=[], **kwargs):
        """
        linux cron定时器
        :param call_back_func: 回调函数
        :param func_args: 回调函数入参列表
        :param kwargs: 字典参数
        :return:
        参数介绍:
            (int|str) 表示参数既可以是int类型，也可以是str类型
            (datetime | str) 表示参数既可以是datetime类型，也可以是str类型

            year (int|str) – 4-digit year -（表示四位数的年份，如2008年）
            month (int|str) – month (1-12) -（表示取值范围为1-12月）
            day (int|str) – day of the (1-31) -（表示取值范围为1-31日）
            week (int|str) – ISO week (1-53) -（格里历2006年12月31日可以写成2006年-W52-7（扩展形式）或2006W527（紧凑形式））
            day_of_week (int|str) – number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun) - （表示一周中的第几天，既可以用0-6表示也可以用其英语缩写表示）
            hour (int|str) – hour (0-23) - （表示取值范围为0-23时）
            minute (int|str) – minute (0-59) - （表示取值范围为0-59分）
            second (int|str) – second (0-59) - （表示取值范围为0-59秒）
            start_date (datetime|str) – earliest possible date/time to trigger on (inclusive) - （表示开始时间）
            end_date (datetime|str) – latest possible date/time to trigger on (inclusive) - （表示结束时间）
            timezone (datetime.tzinfo|str) – time zone to use for the date/time calculations (defaults to scheduler timezone) -（表示时区取值）
        """
        # func_args.append(job_id)

        job = self.scheduler.add_job(func=call_back_func,
                                     args=func_args,
                                     trigger='cron',
                                     # id=job_id,
                                     **kwargs)

        return job.id

    def del_job(self, job_id):
        self.scheduler.remove_job(job_id)

    def clear(self):
        self.scheduler.remove_all_jobs()

    def is_running(self):
        return self.scheduler.running
