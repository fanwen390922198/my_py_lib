from ees_manager.common.const_var.business_status_type import DiskTypeEnum
from ees_manager.common.shell import ShellExec
from .arcconf import get_pmc_raid_devs_info_by_arcconf, disk_light_up_by_arcconf, disk_light_off_by_arcconf
from .storcli import get_lsi_raid_devs_info_by_storcli, disk_light_up_by_storcli, disk_light_off_by_storcli
from .megacli import get_lsi_raid_devs_info_by_megacli, disk_light_up_by_megacli, disk_light_off_by_megacli
from .hp_raid import get_hp_raid_devs_info_by_hpacucli
from enum import Enum, unique


@unique
class RaidType(Enum):
    NO_RAID = 0   # 无raid
    LSI_RAID_STORCLI = 1   # LSI RAID 卡, 支持storcli命令， 如3108
    LSI_RAID_MEGACLI = 2   # LSI RAID 卡, 支持megacli命令， 如2208
    LSI_SCSI = 3   # LSI SCSI 卡, 支持storcli命令， 如3008
    PMC_RAID = 4   # PMC RADI 卡, 支持arcconf命令， 如8204，8222
    HP_RAID = 5   # HP RADI 卡, 验收环境才有


# 获取阵列卡类型
def get_raid_type():
    try:
        # 查看机器上是否有 lsi raid卡
        sub_ret = ShellExec.call("lspci|egrep \"LSI Logic / Symbios Logic MegaRAID SAS|"
                                 "LSI Logic / Symbios Logic Device 0017|Broadcom / LSI MegaRAID SAS\"")
        if sub_ret.ret_code == 0 and len(sub_ret.stdout) > 0:
            if sub_ret.stdout.find("3108") != -1:
                return RaidType.LSI_RAID_STORCLI.value
            elif sub_ret.stdout.find("2208") != -1:
                return RaidType.LSI_RAID_MEGACLI.value
            else:
                return RaidType.LSI_RAID_MEGACLI.value

        sub_ret = ShellExec.call("lspci|egrep \"Broadcom / LSI SAS3008\"")
        if sub_ret.ret_code == 0 and len(sub_ret.stdout) > 0:
            return RaidType.LSI_SCSI.value

        sub_ret = ShellExec.call("lspci|egrep 'Adaptec|8222|8204'")
        if sub_ret.ret_code == 0 and len(sub_ret.stdout) > 0:
            return RaidType.PMC_RAID.value

        sub_ret = ShellExec.call("lspci|egrep 'Hewlett-Packard Company Smart Array'")
        if sub_ret.ret_code == 0 and len(sub_ret.stdout) > 0:
            return RaidType.HP_RAID.value

        return RaidType.NO_RAID.value
    except Exception as e:
        raise e


def get_lsi_raid_dev_info(raid_type=RaidType.LSI_RAID_STORCLI.value):
    """
    获取机器上所有的raid设备信息
    """
    if raid_type == RaidType.LSI_RAID_STORCLI.value:
        # perccli适用于dell机器，storccli适用于华为、浪潮等。
        # 融媒云H3C服务器Intel Corporation C600/X79 series chipset SATA RAID 常用
        raid_devs = get_lsi_raid_devs_info_by_storcli()

    elif raid_type == RaidType.LSI_RAID_MEGACLI.value:
        # 线上MegaRaid和ServerRaid类型（支持Megacli命令）的阵列卡（LSI MegaRAID SAS 9265-8i，LSI MegaRAID SAS 9240-8i等）
        # 支持使用Megacli工具操作硬盘阵列。
        raid_devs = get_lsi_raid_devs_info_by_megacli()

    else:
        return {}

    return raid_devs


# 获取所有raid卡物理磁盘设备
def get_raid_dev_info(raid_type=None, all_disks={}):
    if raid_type is None:
        raid_type = get_raid_type()

    if raid_type in [RaidType.LSI_SCSI.value, RaidType.NO_RAID.value]:    # 没有raid卡，直接返回
        return

    elif raid_type in [RaidType.LSI_RAID_STORCLI.value, RaidType.LSI_RAID_MEGACLI.value]:  # LSI 设备
        raid_devs = get_lsi_raid_dev_info(raid_type)

    elif raid_type in [RaidType.HP_RAID.value]:  # 惠普raid
        raid_devs = get_hp_raid_devs_info_by_hpacucli()

    elif raid_type in [RaidType.PMC_RAID.value]:  # PMC
        raid_devs = get_pmc_raid_devs_info_by_arcconf()

    for dev, dev_info in raid_devs.items():
        if dev in all_disks:
            if dev not in all_disks:
                continue

            _old_dev_info = all_disks[dev]
            _old_dev_info["raid_type"] = dev_info["raid_type"]

            for _phy_dev in dev_info["devices"]:   # 可能包含多盘做raid
                _phy_dev["type"] = DiskTypeEnum.SATA_SSD.value if _phy_dev["type"] == "SSD" \
                    else DiskTypeEnum.SATA_HDD.value
                eid, slt = _phy_dev["slot_id"].split(":")
                if len(eid) == 0 or len(slt) == 0:
                    _phy_dev["slot_id"] = ""

            _old_dev_info["devices"] = dev_info["devices"]


def disk_light_up(ctl_id, eid_slt, channel_id, device_id):
    raid_type = get_raid_type()
    if raid_type in [RaidType.LSI_RAID_STORCLI.value, RaidType.LSI_SCSI.value]:
        return disk_light_up_by_storcli(ctl_id, eid_slt)

    if raid_type in [RaidType.LSI_RAID_MEGACLI.value]:
        return disk_light_up_by_megacli(ctl_id, eid_slt)

    elif raid_type in [RaidType.PMC_RAID.value]:
        return disk_light_up_by_arcconf(ctl_id, device_id)


def disk_light_off(ctl_id, eid_slt, channel_id, device_id):
    raid_type = get_raid_type()
    if raid_type in [RaidType.LSI_RAID_STORCLI.value, RaidType.LSI_SCSI.value]:
        return disk_light_off_by_storcli(ctl_id, eid_slt)

    if raid_type in [RaidType.LSI_RAID_MEGACLI.value]:
        return disk_light_off_by_megacli(ctl_id, eid_slt)

    elif raid_type in [RaidType.PMC_RAID.value]:
        return disk_light_off_by_arcconf(ctl_id, device_id)

