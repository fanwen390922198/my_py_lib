"""
storcli 命令封装
"""
from common.base_type import get_dev_info_by_smartctl
from common.shell import shell_with_no_exception, ShellExec
import json


# Ctl=Controller Index --> raid控制器编号
# EID=Enclosure Device ID --> （外壳）raid卡ID
# Slots --> 槽数
# Slt=Slot No  --> 槽号
# PD=Physical drive count  --> 物理驱动器数量
# DGs=Drive groups --> 驱动器组数
# DG=DriveGroup --> 驱动器组 (比如做raid1， 多个Slt同属一个DG)
# VDs=Virtual drives --> 虚拟驱动器数
# PDs=Physical drives --> 物理驱动器数量
# DID=Device ID --> 设备ID (对应megaraid)
# Model --> 物理设备型号

# storcli show
# [root@cmp-28-2 fanw1]# storcli show
# CLI Version = 007.1613.0000.0000 Oct 29, 2020
# Operating system = Linux 4.19.90-25.24.v2101.ky10.aarch64
# Status Code = 0
# Status = Success
# Description = None
#
# Number of Controllers = 1  # 控制器数量
# Host Name = cmp-28-2
# Operating System  = Linux 4.19.90-25.24.v2101.ky10.aarch64
#
# System Overview :
# ===============
#
# --------------------------------------------------------------------
# Ctl Model   Ports PDs DGs DNOpt VDs VNOpt BBU sPR DS  EHS ASOs Hlth
# --------------------------------------------------------------------
#   0 SAS3416    16  13  13     0  13     0 N/A On  1&2 Y      1 Opt
# --------------------------------------------------------------------

# [root@cmp-28-2 fanw1]# storcli /c0 show

# Virtual Drives = 13
#
# VD LIST :
# =======
#
# ---------------------------------------------------------------
# DG/VD TYPE  State Access Consist Cache Cac sCC       Size Name
# ---------------------------------------------------------------
# 0/0   RAID0 Optl  RW     Yes     NRWTD -   ON  446.102 GB
# 1/1   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 2/2   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 3/3   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 4/4   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 5/5   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 6/6   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 7/7   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 8/8   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 9/9   RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 10/10 RAID0 Optl  RW     Yes     NRWTD -   ON    3.637 TB
# 11/11 RAID0 Optl  RW     Yes     NRWTD -   ON  893.137 GB
# 12/12 RAID0 Optl  RW     Yes     NRWTD -   ON  930.390 GB
# ---------------------------------------------------------------
# VD=Virtual Drive| DG=Drive Group|Rec=Recovery
# Cac=CacheCade|OfLn=OffLine|Pdgd=Partially Degraded|Dgrd=Degraded
# Optl=Optimal|dflt=Default|RO=Read Only|RW=Read Write|HD=Hidden|TRANS=TransportReady
# B=Blocked|Consist=Consistent|R=Read Ahead Always|NR=No Read Ahead|WB=WriteBack
# AWB=Always WriteBack|WT=WriteThrough|C=Cached IO|D=Direct IO|sCC=Scheduled
# Check Consistency
#
#
# Physical Drives = 13
#
# PD LIST :
# =======
#
# -----------------------------------------------------------------------------------------------------
# EID:Slt DID State DG       Size Intf Med SED PI SeSz Model                                   Sp Type
# -----------------------------------------------------------------------------------------------------
# 64:0     17 Onln   0 446.102 GB SATA SSD N   N  512B DSS200-B 480GB                          U  -
# 64:1     19 Onln   1   3.637 TB SATA HDD N   N  512B HGST HDN724040ALE640                    U  -
# 64:3     25 Onln   2   3.637 TB SATA HDD N   N  512B ST4000NM0035-1V4107                     U  -
# 64:4     20 Onln   3   3.637 TB SATA HDD N   N  512B ST4000NM0033-9ZM170                     U  -
# 64:5     24 Onln   4   3.637 TB SATA HDD N   N  512B ST4000NM0033-9ZM170                     U  -
# 64:6     30 Onln   5   3.637 TB SATA HDD N   N  512B HGST HUS726040ALE610                    U  -
# 64:7     29 Onln   6   3.637 TB SATA HDD N   N  512B HGST HUS726040ALE610                    U  -
# 64:8     27 Onln   7   3.637 TB SATA HDD N   N  512B HGST HUS726040ALE610                    U  -
# 64:9     22 Onln   8   3.637 TB SATA HDD N   N  512B HGST HUS726040ALE610                    U  -
# 64:10    28 Onln   9   3.637 TB SATA HDD N   N  512B HGST HUS726040ALE610                    U  -
# 64:11    26 Onln  10   3.637 TB SATA HDD N   N  512B ST4000NM0035-1V4107                     U  -
# 64:12    23 Onln  11 893.137 GB SATA SSD N   N  512B MZ7LH960HAJR-000V3   01PE096D7A09573LEN U  -
# 64:13    31 Onln  12 930.390 GB SATA HDD N   N  512B ST91000640NS                            U  -
# -----------------------------------------------------------------------------------------------------
# EID=Enclosure Device ID|Slt=Slot No|DID=Device ID|DG=DriveGroup
# DHS=Dedicated Hot Spare|UGood=Unconfigured Good|GHS=Global Hotspare
# UBad=Unconfigured Bad|Sntze=Sanitize|Onln=Online|Offln=Offline|Intf=Interface
# Med=Media Type|SED=Self Encryptive Drive|PI=Protection Info
# SeSz=Sector Size|Sp=Spun|U=Up|D=Down|T=Transition|F=Foreign
# UGUnsp=UGood Unsupported|UGShld=UGood shielded|HSPShld=Hotspare shielded
# CFShld=Configured shielded|Cpybck=CopyBack|CBShld=Copyback Shielded
# UBUnsp=UBad Unsupported|Rbld=Rebuild

# Enclosures = 2
#
# Enclosure LIST :
# ==============
#
# ---------------------------------------------------------------------------------------
# EID State Slots PD PS Fans TSs Alms SIM Port#          ProdID           VendorSpecific
# ---------------------------------------------------------------------------------------
#  64 OK       16 13  0    0   0    0   0 C0   & C1   x8 Expander 12G16T0
#  69 OK       16  0  0    0   0    0   0 -              VirtualSES
# ---------------------------------------------------------------------------------------
#
# EID=Enclosure Device ID | PD=Physical drive count | PS=Power Supply count
# TSs=Temperature sensor count | Alms=Alarm count | SIM=SIM Count | ProdID=Product ID


# 查看虚拟磁盘列表
# storcli /c0/vall show all
# storcli /c0/v[x] show all

# 查看物理磁盘信息
# storcli /c0/eall show |more

# 注意
# 03:00.0 RAID bus controller: LSI Logic / Symbios Logic MegaRAID SAS 2208 [Thunderbolt] (rev 01)
# 此卡只支持megacli, 不支持strocli


def run_stor_cli(cmd):
    try:
        ret = shell_with_no_exception(cmd + " nolog", timeout=180)
        if ret is not None:
            ret = json.loads(ret)
            if "Controllers" in ret and len(ret.get("Controllers")) > 0:
                if "Response Data" in ret.get("Controllers")[0]:
                    response_data = ret.get("Controllers")[0].get("Response Data")
                elif "Command Status" in ret.get("Controllers")[0]:
                    response_data = ret.get("Controllers")[0].get("Command Status")
                return response_data

    except Exception as e:
        raise e


def _get_physical_dev_info(all_es_devs, ctl_id, eid_slt):
    eid, slt = eid_slt.split(":")
    ctl_eid_slt = f"/c{ctl_id}/e{eid}/s{slt}"
    key = f"Drive {ctl_eid_slt} - Detailed Information"
    drive_attributes = all_es_devs.get(key).get(f"Drive {ctl_eid_slt} Device attributes")
    return dict(
        serial_number=drive_attributes.get("SN").strip(),
        model=drive_attributes.get("Model Number").strip(),
        wwn=drive_attributes.get("WWN").strip()
    )


class StorCliTool(object):
    def __init__(self):
        self.dev_list = {}
        self.slot_ids = []
        self.controllers = []
        self.controller_enclosure_device_id = {}

    def get_controllers(self):
        """
        获取系统的阵列卡
        :return:
        """
        response_data = run_stor_cli("storcli show J")
        controllers = response_data.get("Number of Controllers")
        if controllers == 0:
            return

        for item in response_data.get("System Overview", []) + response_data.get("IT System Overview", []):
            self.controllers.append(item["Ctl"])

    def get_enclosure_device_id(self):
        """
        获取阵列信息
        :return:
        """
        for ctl_id in self.controllers:
            self.controller_enclosure_device_id[ctl_id] = []
            response_data = run_stor_cli(f"storcli /c{ctl_id}/eall show J")
            for item in response_data.get("Properties"):
                if item.get("PD") > 0:
                    self.controller_enclosure_device_id[ctl_id].append(dict(
                        eid=item.get("EID"),
                        slots=item.get("Slots"),
                        pds=item.get("PD")
                    ))

    def get_virtual_drivers(self, ctl_id):
        all_es_devs = run_stor_cli(f"storcli /c{ctl_id}/eall/sall show all J")
        virtual_drivers = run_stor_cli(f"storcli /c{ctl_id}/vall show all J")
        for k, v in virtual_drivers.items():
            if "/" in k:
                _vd = {"raid_type": v[0]["TYPE"], "dg_vd": v[0]["DG/VD"]}
                virtual_driver = _vd["dg_vd"].split("/")[-1]

                # 虚拟设备名
                _vd["dev_name"] = virtual_drivers.get(f"VD{virtual_driver} Properties").get("OS Drive Name")
                _vd["dev_name"] = _vd["dev_name"].split("/")[-1]

                # 获取该虚拟设备对应的物理设备数量
                physical_drives = []
                for _pd in virtual_drivers.get(f"PDs for VD {virtual_driver}"):
                    _dev_attr = _get_physical_dev_info(all_es_devs, ctl_id, _pd.get("EID:Slt"))
                    _dev_attr["ctl_id"] = str(ctl_id)
                    _dev_attr["slot_id"] = _pd.get("EID:Slt")
                    _dev_attr["device_id"] = str(_pd.get("DID"))  # device id
                    _dev_attr["driver_group"] = _pd.get("DG")
                    _dev_attr["status"] = _pd.get("State")
                    _dev_attr["size"] = _pd.get("Size")
                    _dev_attr["type"] = _pd.get('Med')
                    # 通过smartctl 获取基本信息
                    other_attr = get_dev_info_by_smartctl(dev=_vd["dev_name"], device_id=_dev_attr["device_id"])
                    _dev_attr.update(other_attr)
                    physical_drives.append(_dev_attr)

                _vd["devices"] = physical_drives

                self.dev_list[_vd["dev_name"]] = _vd

    def get_scsi_dev(self):
        all_physical_dev = []
        self.get_controllers()
        for ctl_id in self.controllers:
            all_es_devs = run_stor_cli(f"storcli /c{ctl_id} show all J")
            physical_device_information = all_es_devs.get("Physical Device Information", {})
            for k, v in physical_device_information.items():
                if not k.endswith("Detailed Information"):
                    _dev = {"slot_id": v[0].get("EID:Slt"), "device_id": v[0].get("DID", ""), "ctl_id": ctl_id}

                    # detail info
                    _dev_attrs = physical_device_information.get(f"{k} - Detailed Information", {}). \
                        get(f"{k} Device attributes", {})
                    vendor = _dev_attrs.get("Manufacturer Id", "").strip()
                    product = _dev_attrs.get("Model Number", "").strip()
                    _dev["model"] = f"{vendor} {product}"
                    _dev["serial_number"] = _dev_attrs.get("SN", "").strip()
                    _dev["wwn"] = _dev_attrs.get("WWN", "").strip()

                    all_physical_dev.append(_dev)

        return all_physical_dev

    def get_dev_info(self):
        self.get_controllers()
        for ctl_id in self.controllers:
            self.get_virtual_drivers(ctl_id)

        return self.dev_list


def get_lsi_scsi_devs_info_by_storcli():
    tool = StorCliTool()
    return tool.get_scsi_dev()


def get_lsi_raid_devs_info_by_storcli():
    tool = StorCliTool()
    return tool.get_dev_info()


def disk_light_up_by_storcli(ctl_id, eid_slt):
    eid, slt = eid_slt.split(":")
    ret = run_stor_cli(f"storcli /c{ctl_id}/e{eid}/s{slt} start locate J")
    return ret.get("Description", "")


def disk_light_off_by_storcli(ctl_id, eid_slt):
    eid, slt = eid_slt.split(":")
    ret = run_stor_cli(f"storcli /c{ctl_id}/e{eid}/s{slt} stop locate J")
    return ret.get("Description", "")


if __name__ == "__main__":
    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    # pp.pprint(get_lsi_raid_devs_info_by_storcli())
    pp.pprint(get_lsi_scsi_devs_info_by_storcli())
