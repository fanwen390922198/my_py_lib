# try:
#     import sys
#     import os
#     sys_path = sys.path
#     local_lib_path = "/usr/local/lib/python3.6/site-packages"
#     if os.path.exists(local_lib_path) and local_lib_path not in sys_path:
#         sys.path.append(local_lib_path)
# except:
#     pass

import shutil
import setuptools
from setuptools import setup, find_packages
from setuptools.command.install_scripts import install_scripts

from ees_manager import __version__ as ees_version


class InstallScripts(install_scripts):
    def run(self):
        setuptools.command.install_scripts.install_scripts.run(self)
        # Rename some script files
        for script in self.get_outputs():
            if script.endswith(".py") or script.endswith(".sh"):
                dest = script[:-3]
            else:
                continue
            print("moving %s to %s" % (script, dest))
            shutil.move(script, dest)


setup(
    name="ees_manager",
    version=ees_version,
    description="edgeray enterprise storage manager",
    log_description="A program used to offer rest api to manager edgeray enterprise storage",
    license="",
    author="edgeray cloud",
    author_email="",
    python_requires='>=3.6',
    packages=find_packages(),
    include_package_data=True,
    platforms="any",
    install_requires=["APScheduler==3.7.0",
                      "requests==2.14.2",
                      "PyMySQL==1.0.2",
                      "SQLAlchemy==1.4.23",
                      "Flask==2.0.1",
                      "Flask-RESTful==0.3.9",
                      "Flask-SQLAlchemy==2.5.1",
                      "redis==2.10.5",
                      "psutil==5.8.0",
                      "taskflow==4.6.3",
                      "redis-py-cluster==1.3.4",
                      "boto3==1.17.92",
                      "reportlab==3.6.8",
                      "xlwt==1.3.0",
                      "pexpect==4.8.0",
                      "arrow==1.2.2",
                      "alembic==1.7.7"
                      ],
    dependency_links=["./packages"],
    py_modules=[],
    classifiers=[
        'Programming Language :: Python :: 3.6'
    ],
    # 安装过程中，需要安装的静态文件，如配置文件、service文件、图片等
    data_files=[('/etc/ees_manager/', ['etc/es_agw.conf', 'etc/nd_agent.conf', "etc/alembic.ini"]),
                ('/usr/lib/systemd/system/', ['etc/es_agw.service', 'etc/nd_agent.service'])
                ],

    # 用来支持自动生成脚本，安装后会自动生成 /usr/bin/es_agw 的可执行文件
    # 该文件入口指向 enterprise_storage/bin/es_agw.py 的main 函数
    entry_points={
        "console_scripts": [
            "es_agw=ees_manager.bin.es_agw:main",
            "nd_agent=ees_manager.bin.nd_agent:main",
            "ees_manager_tool=ees_manager.bin.ees_manager_tool:main"
        ]
    },

    # 将 bin/es_agw.py 和 bin/nd_agent.py 脚本，生成到系统 PATH中
    # 执行 python setup.py install 后
    # 会生成 如 /usr/bin/es_agw.py 和 如 /usr/bin/nd_agent.py
    scripts=["ees_manager/bin/es_agw.py", "ees_manager/bin/nd_agent.py"],
    cmdclass={
        # "install_scripts": InstallScripts
        "install_scripts": install_scripts
    }
)
