"""
arcconf 命令封装
PMC Raid卡的运维命令
"""
from common.shell import ShellExec

ARCCONF = "/usr/Arcconf/arcconf "

# "Channel #|Device #|Reported Channel,Device(T:L)|Reported Location|Array|Vendor|Model|Serial number|World-wide name
# |SSD|Rotational Speed"


class ArcconfCliTool(object):
    def __init__(self):
        self.controllers = []    # 所有阵列
        self.all_physical_devices = []  # 所有的物理设备
        self.all_logical_drivers = []   # 所有的逻辑驱动器
        self.controller_enclosure_device_id = {}

    def get_controllers(self):
        """
        获取系统的阵列卡
        :return:
        """
        cmd = f"{ARCCONF} LIST||egrep \"Controller\""
        ret = ShellExec.call(cmd, timeout=180)
        for line in ret.stdout.split("\n"):
            if "Adaptec" in line or "RAID" in line:
                self.controllers.append(int(line[:line.find(":")].replace("Controller", "").strip()))

    def get_physical_devices(self):
        """
        获取所有物理设备
        :return:
        """
        self.all_physical_devices = []
        _new_device = {}
        current_channel = None
        _current_device_id = None

        fields = ["Channel #", "Device #", "Reported Channel,Device(T:L)", "Reported Location", "Array", "Vendor",
                  "Model", "Serial number", "World-wide name", "SSD", "Rotational Speed", "Total Size"]

        for ctl_id in self.controllers:
            cmd = f"{ARCCONF} GETCONFIG {ctl_id} PD"
            filter_str = "|egrep \"{}\"".format("|".join(fields))
            cmd += filter_str
            ret = ShellExec.call(cmd, timeout=180)
            for line in ret.stdout.split("\n"):
                if "Channel #" in line:
                    current_channel = line.split(":")[0].split("#")[1]

                elif "Device #" in line:
                    if _current_device_id is not None:
                        self.all_physical_devices.append(_new_device)
                        _new_device = {}

                    _current_device_id = int(line.split("#")[1].strip())
                    _new_device["device_id"] = _current_device_id
                    _new_device["channel"] = current_channel
                    _new_device["ctl_id"] = ctl_id

                elif "Array" in line:
                    _new_device["array"] = line[line.find(":") + 1:].strip()

                elif "Reported Location" in line:
                    eid = line[line.find("Enclosure") + len("Enclosure"): line.find(",", line.find("Enclosure"))].strip()
                    slt = line[line.find("Slot") + len("Slot"): line.find("(", line.find("Slot"))].strip()
                    _new_device["slot_id"] = f"{eid}:{slt}"

                elif "Vendor" in line:
                    _new_device["vendor"] = line[line.find(":") + 1:].strip()

                elif "Model" in line:
                    _new_device["model"] = line[line.find(":") + 1:].strip()

                elif "World-wide name" in line:
                    _new_device["wwn"] = line[line.find(":") + 1:].strip()

                elif "Serial number" in line:
                    _new_device["serial_number"] = line[line.find(":") + 1:].strip()

                elif "Total Size" in line:
                    _new_device["size"] = int(line[line.find(":") + 1:].replace("MB", "").strip()) * (1024 ** 2)
                    _new_device['capacity'] = "{} bytes []".format(_new_device["size"])

                elif "SSD" in line:
                    is_ssd = "No"
                    if line.split(":")[0].strip() == "SSD":
                        is_ssd = line[line.find(":") + 1:].strip()

                    _new_device['type'] = "SSD" if is_ssd == "Yes" else "HDD"

        self.all_physical_devices.append(_new_device)

    def get_virtual_drivers(self):
        _new_driver = {}
        current_driver = None
        device_id_2_device_info = {device["device_id"]: device for device in self.all_physical_devices}

        for ctl_id in self.controllers:
            cmd = f"{ARCCONF} GETCONFIG {ctl_id} LD"
            ret = ShellExec.call(cmd, timeout=180)
            for line in ret.stdout.split("\n"):
                # 虚拟设备名
                if "Disk Name" in line:
                    if current_driver is not None:
                        # 将前一个设备添加到集合，并将_new_driver 置空
                        self.all_logical_drivers.append(_new_driver)
                        _new_driver = {}

                    current_driver = line[line.find(":") + 1:].split("/")[-1].strip()
                    _new_driver["dev_name"] = current_driver
                    _new_driver["devices"] = []
                    _new_driver["ctl_id"] = ctl_id

                elif "Array" in line:
                    key = line[: line.find(":")].strip()
                    if key == "Array":
                        _new_driver["array"] = line[line.find(":") + 1:].strip()

                elif "RAID level" in line:
                    _new_driver["raid_type"] = "RAID{}".format(line[line.find(":") + 1:].strip())

                elif "Device" in line:
                    if "Enclosure" in line and "Slot" in line:  # raid 设备
                        device_id = int(line[: line.find(":")].replace("Device", "").strip())
                        _new_driver["devices"].append(device_id_2_device_info.get(device_id, {}))

        self.all_logical_drivers.append(_new_driver)


def get_pmc_raid_devs_info_by_arcconf():
    tool = ArcconfCliTool()
    tool.get_controllers()
    tool.get_physical_devices()
    tool.get_virtual_drivers()

    return {ld["dev_name"]: ld for ld in tool.all_logical_drivers}


def disk_light_up_by_arcconf(ctl_id, device_id):
    # 对特定的物理硬盘持续点灯，按任意键会停止点灯。
    # arcconf identify controller_id device physical_id time time
    cmd = f"{ARCCONF} IDENTIFY {ctl_id} DEVICE {device_id} TIME 3600"
    ret = ShellExec.call(cmd, timeout=180)
    return "Start Driver Locate Succeeded"


def disk_light_off_by_arcconf(ctl_id, device_id):
    # 对所有的物理硬盘停止点灯
    cmd = f"{ARCCONF} IDENTIFY {ctl_id} DEVICE {device_id}"
    ret = ShellExec.call(cmd, timeout=180)
    return "Stop Driver Locate Succeeded"


if __name__ == "__main__":
    # print(get_lsi_raid_devs_info_by_storcli())
    print(get_pmc_raid_devs_info_by_arcconf())
