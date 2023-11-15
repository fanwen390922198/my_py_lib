# {project} 介绍
	本工程主要是近年来做python工程开发所积累的一些经验，很多模块在运维开发或者做python后端开发时可拿来即用；
	主要有：
		1. 日志
		2. 配置
		3. 定时器
		4. 基础函数
		5. 数据库访问
		6. redis集群访问
		7. shell通用类
		8. S3访问api
		9. ceph 集群运维api
		10. 工作流
		11. 常量定义
		12. 集群拓扑定义
		13. 通用的raid 卡工具 （兼容市面的主要类型的raid卡）
		14. 通用装饰器的定义
		15. rclone数据同步的python封装
		16. python工程的编译打包配置
		

### 依赖：
    1. 本模块依赖Python3.6 及以上
    2. mysql 数据库
    3. redis 数据库
    4. ceph 15.2.x

### 源码安装：
    python3 setup.py install --install-script=/usr/bin

### 打包编译：
    ./build.sh {版本号}
    注意: {project} 编译依赖setuptools，且必须安装在/usr/lib/python3.X/site-packages/ 下面, 两种方法都可以：
       1. yum install python3-setuptools 安装
       2. python3 -m pip install setuptools-58.1.0-py3-none-any.whl --target=/usr/lib/python3.6/site-packages/ 安装

       若编译打包时找不到setup或者安装之后出现load失败的问题，首先是setuptools包有冲突，在/usr/lib、/usr/local/lib下面都有，那就需要清除相关的记录；
       rpm -e --nodeps python3-setuptools  # 清理残存的/usr/lib 下的记录
       pip3 uninstall setuptools   # 清理/usr/local 下的记录
       
       再按照上面的安装方法重新安装setuptools      

### 工程目录：
    1. {project} 核心实现
    2. etc  配置文件
    3. packages 程序的依赖包

### 数据库版本更新
    1. 确保编译机器上已经卸载了{project} 包，否则会加载到python3 系统库目录 
    2. 进入models 目录
      2.1. 修改alembic.ini 配置文件
        script_location = alembic
      2.2. 确保es_agw 库版本跟models中最新的是一致的
        [root@ees32 models]# alembic heads
        508ea2876e35 (head)

        MariaDB [es_agw]> select * from alembic_version;
        +--------------+
        | version_num  |
        +--------------+
        | 508ea2876e35 |
        +--------------+
        1 row in set (0.001 sec)
      2.3 为了防止和已部署的{project}中的DB文件发生冲突, 可以创建一个python3 虚拟环境：
         1. 创建一个虚拟环境目录
            mkdir {env_path}

         2. 生成一个干净的python3 虚拟环境
            python3 -m venv {env_path}

         3. 激活虚拟环境
             source {env_path}/bin/activate

         4. 安装基本的alembic 和pymysql: 
             pip install -r requirements.txt --no-index --find-links=./packages
         
         5. 使用alembic， 可以看得出alembic指向的是虚拟路径
              (ees_env) [root@ees-0-2 ees_env]# alembic -h
               > /home/fanw1/build_{project}/ees_env/bin/alembic(11)<module>()
               -> sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
              
              (ees_env) [root@ees-0-2 models]# alembic revision --autogenerate -m "v4_1_0_1 data flow tables create"
              ['.', '/home/fanw1/build_{project}/ees_env/bin', '/usr/lib64/python36.zip', '/usr/lib64/python3.6', 
               '/usr/lib64/python3.6/lib-dynload', '/home/fanw1/build_{project}/ees_env/lib64/python3.6/site-packages', 
               '/home/fanw1/build_{project}/ees_env/lib/python3.6/site-packages']
               可以看得出sys.path 中也是虚拟环境的目录

         5.1. 编译数据库db文件，生成新的version
            alembic revision --autogenerate -m "{注释内容}"

         6. 退出虚拟环境
             deactivate

    3. 编译打包{project}, 并安装

    4. 使用{project}_tool 升级到最新版本
      {project}_tool db_upgrade --db_version head


