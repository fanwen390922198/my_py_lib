from common.shell import ShellExec, exist_command
from common.base_type import get_dev_info_by_smartctl

if exist_command("ssacli"):
    HP_CLI = "ssacli"
elif exist_command("hpssacli"):
    HP_CLI = "hpssacli"
elif exist_command("hpacucli"):
    HP_CLI = "hpacucli"

# 查看raid卡信息(包括控制器状态、Cache状态、电池状态)
# ssacli ctrl all show status

# 查看raid详细信息，包括array, pd, ld
# ssacli ctrl slot=0 show config detail

# 查看raid状态
# ssacli ctrl slot=0 ld all show

# 查看slot 0 阵列A 所有逻辑驱动器信息
# ssacli ctrl slot=0 array A ld all show

# 查看slot 0 阵列A 所有物理驱动器信息
# ssacli ctrl slot=0 array A pd all show

# 查看硬盘
# ssacli ctrl slot=0 pd all show status  //查看物理硬盘状态
# ssacli ctrl slot=0 pd all show  //查看物理硬盘

# 创建raid10
# ssacli ctrl slot=0 create type=ld drives=1I:1:3,1I:1:4,2I:1:5,2I:1:6 raid=1+0

# 用3，4，5号盘创建一个raid5阵列
# ssacli ctrl slot=0 create type=ld drives=1I:1:3,1I:1:4,2I:1:5 raid=5

# 创建raid1
# ssacli ctrl slot=1 create type=ld drives=1I:1:1-1I:1:2 raid=1

# 删除raid
# ssacli ctrl slot=1 array B delete forced


# 缓存：
# 查看cache信息：
# ssacli ctrl all show config detail | grep -i cache

# 关闭物理磁盘cache
# ssacli ctrl slot=0 modify drivewritecache=disable

# 打开逻辑磁盘缓存
# ssacli ctrl slot=0 logicaldrive 2 modify caching=enable

# 在没有电池的情况下开启raid写缓存
# ssacli ctrl slot=0 modify nobatterywritecache=enable

# 设置读写百分比
# ssacli ctrl slot=0 modify cacheratio=10/90


# 指示灯：
# 打开array B磁盘的led灯
# ssacli ctrl slot=0 array B modify led=on

# 打开3号磁盘的led灯
# ssacli ctrl slot=0 pd 1I:1:3 modify led=on


class HpAcuCliTool(object):
    def __init__(self):
        self.slot_ids = []    # 所有阵列
        self.all_physical_devices = []  # 所有的物理设备
        self.all_logical_drivers = []   # 所有的逻辑驱动器

    def get_slot_info(self):
        cmd = f"{HP_CLI} ctrl all show"
        ret = ShellExec.call(cmd)
        for line in ret.stdout.split("\n"):
            if "Slot" in line:
                start = line.find("Slot") + len("Slot") + 1
                slot_id = line[start: start+2].strip()
                self.slot_ids.append(slot_id)

    def get_physical_devices(self):
        """
        获取所有物理设备
        :return:
        """
        self.all_physical_devices = []
        _new_device = {}
        _current_physicaldrive = None
        _current_array = None

        fields = ["array", "physicaldrive", "Serial Number", "Model"]
        for slot_id in self.slot_ids:
            cmd = f"{HP_CLI} controller slot={slot_id} pd all show detail"
            filter_str = "|egrep \"{}\"".format("|".join(fields))
            cmd += filter_str
            ret = ShellExec.call(cmd)
            for line in ret.stdout.split("\n"):
                if "physicaldrive" in line:
                    if _current_physicaldrive is not None:
                        self.all_physical_devices.append(_new_device)
                        _new_device = {}

                    _current_physicaldrive = line.strip().split()[1]
                    _new_device["slot_id"] = _current_physicaldrive     # physicaldrive 2I:1:5
                    _new_device["ctl_id"] = slot_id
                    _new_device["array"] = _current_array

                elif "array" in line:
                    _fields = line.strip().split()
                    if _fields[0] == "array":
                        _current_array = _fields[1]

                elif "Model" in line:
                    _new_device["model"] = line[line.find(":") + 1:].strip()

                elif "Serial Number" in line:
                    _new_device["serial_number"] = line[line.find(":") + 1:].strip()

        self.all_physical_devices.append(_new_device)

        # 获取磁盘的smart 信息
        smart_devs = {}
        physical_devs = len(self.all_physical_devices)
        for i in range(0, physical_devs):
            smart_dev_info = get_dev_info_by_smartctl(f"sg{i}", cciss=i)
            smart_dev_info["device_id"] = i  # cciss 在此命令为device_id
            if "serial_number" in smart_dev_info:
                smart_devs[smart_dev_info["serial_number"]] = smart_dev_info

        # 更新物理设备信息
        for _dev in self.all_physical_devices:
            if _dev["serial_number"] in smart_devs:
                _dev.update(smart_devs.get(_dev["serial_number"]))

    def get_logical_drivers(self):
        _new_driver = {}
        current_raid_type = None
        _current_array = None

        for slot_id in self.slot_ids:
            cmd = f"hpacucli controller slot={slot_id} ld all show detail"
            ret = ShellExec.call(cmd)
            for line in ret.stdout.split("\n"):
                if "array" in line:
                    _fields = line.strip().split()
                    if _fields[0] == "array":
                        _current_array = _fields[1]

                elif "Fault Tolerance" in line:
                    current_raid_type = "RAID{}".format(line[line.find(":") + 1:].strip())

                # 虚拟设备名
                elif "Disk Name" in line:
                    _new_driver["dev_name"] = line[line.find(":") + 1:].split("/")[-1].strip()
                    _new_driver["ctl_id"] = slot_id
                    _new_driver["array"] = _current_array
                    _new_driver["devices"] = [dev for dev in self.all_physical_devices if dev["array"] == _current_array]
                    _new_driver["raid_type"] = current_raid_type
                    self.all_logical_drivers.append(_new_driver)
                    _new_driver = {}


def get_hp_raid_devs_info_by_hpacucli():
    """
    获取hp raid信息
    """
    tool = HpAcuCliTool()
    tool.get_slot_info()
    tool.get_physical_devices()
    tool.get_logical_drivers()

    return {ld["dev_name"]: ld for ld in tool.all_logical_drivers}

# 闪烁物理磁盘 LED
# 要使逻辑驱动器 2 的物理驱动器上的 LED 闪烁，请执行以下操作。这将使属于逻辑驱动器 2 的所有物理驱动器上的 LED 闪烁。
#
# => ctrl slot=0 ld 2 modify led=on
# 一旦您知道哪个驱动器属于逻辑驱动器 2，请关闭闪烁的 LED，如下所示。
#
# => ctrl slot=0 ld 2 modify led=off


def disk_light_up_by_hpacucli(ctl_id, device_id):
    # 对特定的物理硬盘持续点灯，按任意键会停止点灯。
    # ssacli ctrl slot=0 pd 2I:1:6 modify led=on
    cmd = f"{HP_CLI} ctrl slot={ctl_id} pd {device_id} modify led=on"
    ret = ShellExec.call(cmd)
    return "Start Driver Locate Succeeded"


def disk_light_off_by_hpacucli(ctl_id, device_id):
    # 对所有的物理硬盘停止点灯
    cmd = f"{HP_CLI} ctrl slot={ctl_id} pd {device_id} modify led=off"
    ret = ShellExec.call(cmd)
    return "Stop Driver Locate Succeeded"


if __name__ == "__main__":
    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(get_hp_raid_devs_info_by_hpacucli())
