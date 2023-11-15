from enum import Enum, unique


# ---------------------------------------------------------------------------------------------------- #
# 业务状态定义(枚举类型)
# ---------------------------------------------------------------------------------------------------- #
# 服务器执行角色
@unique
class ServicePlayRole(Enum):
    LEADER = "leader"
    CANDIDATE = "candidate"
    FOLLOWER = "follower"


# 服务器状态
@unique
class ServerStatus(Enum):
    DOWN = 0  # 离线
    ON = 1  # 在线


# Metadata 状态
@unique
class MetadataStatusEnum(Enum):
    AVAILABLE = 0  # 已启用
    DISABLED = 1  # 已禁用


# 节点状态
@unique
class NodeStatusEnum(Enum):
    FREE = 0   # 空闲状态
    APP_DEPLOYED = 1  # 已部署应用
    REMOVED = 2     # 已移除
    ERROR = 3     # 异常


# 节点健康状态
@unique
class NodeHealthEnum(Enum):
    HEALTH = 0   # 健康
    ABNORMAL = 1  # 异常


# 节点磁盘健康状态
@unique
class NodeDiskHealthEnum(Enum):
    HEALTH = 0   # 健康
    ABNORMAL = 1  # 异常


# 硬盘用途
@unique
class DiskUsageEnum(Enum):
    OS_BOOT = 0   # 系统盘
    OSD_DATA = 1    # OSD DATA
    OSD_DB = 2      # OSD DB
    OSD_JOURNAL = 3     # OSD JOURNAL
    CACHE = 4  # 缓存(加速)
    UNUSED = 5  # 未使用
    OSD_WAL = 6      # OSD WAL


# 硬盘类型
@unique
class DiskTypeEnum(Enum):
    NVME_SSD = 0   # Nvme ssd
    SATA_SSD = 1   # sata ssd
    SATA_HDD = 2   # sata 机械盘
    MIXED = 3      # 混合型设备
    UNKNOW = 4     # 未知
    VIRTUAL_DISK = 5  # 虚拟设备


# 磁盘状态类型
@unique
class DiskStateEnum(Enum):
    OFF_LINE = 0
    ON_LINE = 1
    REMOVED = 2   # 磁盘已经被移除

    # HEALTH = 0   # 健康
    # ABNORMAL = 1   # 异常
    # PULLED_OUT = 2     # 已被拔出
    # ERROR = 3   # 出现读写错误（例如坏道）
    # WARNING = 4   # 告警
    # HEAVY = 5   # 使用率高


# smart attr status
@unique
class DiskSmartAttrStateEnum(Enum):
    HEALTH = 0   # 健康
    WARNING = 1   # 告警
    ABNORMAL = 2   # 异常


# OSD 状态
class OsdStateEnum(Enum):
    HEALTH = 0      # up + in
    WARNING = 1     # down + in
    OFFLINE = 2     # up + out
    ERROR = 3       # down + out
    DELETED = 4     # deleted

    @staticmethod
    def transfer(osd_state):
        if osd_state == 0:
            return "health"
        elif osd_state == 1:
            return "warning"
        elif osd_state == 2:
            return "offline"
        elif osd_state == 3:
            return "error"
        elif osd_state == 4:
            return "deleted"

    @staticmethod
    def state(_up=1, _in=1):
        if _up == 1 and _in == 1:
            return OsdStateEnum.HEALTH.value
        elif _up == 0 and _in == 0:
            return OsdStateEnum.ERROR.value
        elif _up == 1 and _in == 0:
            return OsdStateEnum.OFFLINE.value
        elif _up == 0 and _in == 1:
            return OsdStateEnum.WARNING.value


# PG 状态
@unique
class OsdPgStateEnum(Enum):
    ACTIVE_CLEAN_HEALTH = 0   # 健康
    DEGRRADE_AVAILABLE = 1    # 有告警但是可用（需要尽快处理）
    ERROR_DISABLE = 2         # 不可用（需要尽快处理）


# OSD 类型
@unique
class OsdClassEnum(Enum):
    SSD = 1
    HDD = 0


# nd_agent 状态
@unique
class NdAgentStatusEnum(Enum):
    HEALTH = 1
    UNHEALTH = 2


@unique
class NicStatusEnum(Enum):
    OFF_LINE = 0
    ON_LINE = 1
    # HEALTH = 0  # 健康
    # ABNORMAL = 1  # 异常
    # PULLED_OUT = 2  # 被拔出


# volume 状态
@unique
class VolumeStatusEnum(Enum):
    Creating = 0
    Available = 1
    InUse = 2
    Deleting = 3
    Deleted = 4
    Expanding = 5
    Errored = 6


# target 状态
@unique
class TargetStatusEnum(Enum):
    Creating = 0
    Available = 1
    InUse = 2
    Deleting = 3
    Deleted = 4
    Errored = 5


# Initiator 状态
@unique
class InitiatorStatusEnum(Enum):
    Available = 1
    InUse = 2
    Deleted = 3
    Errored = 4


# target portals状态
@unique
class TargetPortalStatusEnum(Enum):
    Creating = 0
    InUse = 1
    Deleted = 2
    Errored = 5


# target disk状态
@unique
class TargetDiskStatusEnum(Enum):
    BINDED = 0  # 绑定中
    UNTIED = 1  # 已解绑


# target initiator状态
@unique
class TargetInitiatorStatusEnum(Enum):
    BINDED = 0  # 绑定中
    UNTIED = 1  # 已解绑


# initiator disk状态
@unique
class InitiatorVolumeStatusEnum(Enum):
    BINDED = 0  # 绑定中
    UNTIED = 1  # 已解绑


# chap 状态
@unique
class ChapStatusEnum(Enum):
    unable = 0  # 未开启
    enable = 1  # 已启用
    disbale = 2  # 已禁用
