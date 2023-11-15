"""
storcli 命令封装
"""
from common.base_type import get_dev_info_by_smartctl
from common.shell import shell_with_no_exception, ShellExec, exist_command


def megacli():
    devices_info = {}
    seq_devid_to_dev = {}
    try:
        # 1. 查看pci 映射关系
        sub_ret = ShellExec.call("ls -l /dev/disk/by-path/pci*|grep -v part")
        if sub_ret.ret_code == 0 and len(sub_ret.stdout) > 0:
            for line in sub_ret.stdout.split('\n'):
                if 'scsi-' in line:
                    line = line[line.find('scsi-') + 6:]
                    dev = line[line.rfind('/') + 1:]
                    seq_num = line.split(':')[1]
                    device_id = line.split(':')[2]
                    seq_devid_to_dev["{}:{}".format(seq_num, device_id)] = dev
                    # print("{}:{}".format(seq_num, device_id), dev)

        # 2. 通过megacli 获取设备信息
        sub_ret = ShellExec.call('megacli -ldpdinfo -aall | egrep "(Virtual Drive|Enclosure Device ID|Slot Number|'
                                 'Device Id|WWN|Sequence Number|RAID Level|Firmware state)"')
        for line in sub_ret.stdout.strip().split('\n'):
            if len(line) == 0:
                continue
            if line.find("Virtual Drive") != -1:
                continue
            elif line.find("Device Id") != -1:
                device_id = line[line.find(":") + 1:].strip()
            elif line.find("RAID Level") != -1:
                raidllevel = int(line.strip().split(':')[1].split(',')[0].split('-')[1].strip())
                raid_info = "RAID{}".format(raidllevel)
            elif line.find("Sequence Number") != -1:
                seq_num = line[line.find(":") + 1:].strip()
            elif line.find("Firmware state") != -1:
                status = line[line.find(":") + 1:].strip()

                key = "{}:{}".format(seq_num, device_id)
                if key in seq_devid_to_dev:  # 多个设备做raid, 指向同一个逻辑设备
                    dev = seq_devid_to_dev[key]
                    if dev not in devices_info:
                        devices_info[dev] = dict(
                            dev_name=dev,
                            raid_type=raid_info,
                            devices=[]
                        )

                    this_device = dict(
                        solt_id=device_id,
                        status=status
                    )

                    # 再次获取smartctl 信息
                    disk_info = get_dev_info_by_smartctl(dev, int(device_id))
                    this_device.update(disk_info)
                    devices_info[dev]['devices'].append(this_device)

    except Exception as e:
        raise e

    return devices_info


def get_wwn():
    device_id_to_wwn = {}
    cmd_out = shell_with_no_exception("megacli -ldpdinfo -aall | egrep \"(Device Id|WWN)\"")
    cur_device_id = None
    cur_wwn = None
    if cmd_out is not None:
        for line in cmd_out.split("\n"):
            if "Device Id:" in line:
                if cur_device_id is not None: # 前一次获取的数据
                    device_id_to_wwn[cur_device_id] = cur_wwn
                cur_device_id = line[line.find(":") + 1:].strip()

            elif "WWN:" in line:
                cur_wwn = line[line.find(":") + 1:].strip()

        device_id_to_wwn[int(cur_device_id)] = cur_wwn

    return device_id_to_wwn


def megaclisas_status():
    """
    megaclisas-status, 无法直接获取到磁盘的序列号，必须再从smart里面获取一次
    """
    all_devices = {}
    device_id_to_wwn = get_wwn()
    cmd_out = shell_with_no_exception("megaclisas-status")
    if cmd_out is not None:
        array_title = "-- Array information --"
        disk_title = "-- Disk information --"
        unconfig_title = "-- Unconfigured Disk information --"
        array_info_pos = cmd_out.find(array_title)
        disk_info_pos = cmd_out.find(disk_title)
        unconfig_pos = cmd_out.find(unconfig_title)

        array_info = cmd_out[array_info_pos + len(array_title): disk_info_pos].strip()
        if unconfig_pos != -1:
            disk_info = cmd_out[disk_info_pos + len(disk_title):unconfig_pos].strip()
        else:
            disk_info = cmd_out[disk_info_pos + len(disk_title):].strip()

        for line in array_info.split('\n'):
            fileds = line.split('|')
            if fileds[0].find('ID') != -1:
                continue
            all_devices[fileds[0].strip()] = dict(
                id=fileds[0].strip(),
                raid_type=fileds[1].replace("-", "").strip(),
                size=fileds[2].strip(),
                os_path=fileds[7].strip(),
                devices=[]
            )

        for line in disk_info.split('\n'):
            fileds = line.split('|')
            if fileds[0].find('ID') != -1:
                continue

            id = fileds[0].strip()[:-2]
            if id in all_devices:
                # 这里为什么是append，因为可能多个设备做raid，形成一个虚拟设备
                this_device = dict(
                    type=fileds[1].strip(),
                    model=fileds[2].strip(),
                    size=fileds[3].strip(),
                    status=fileds[4].strip(),
                    slot_id=fileds[7].strip().replace("[", "").replace("]", ""),
                    device_id=int(fileds[8].strip()),
                    ctl_id=id[1]
                )

                # 再次获取smartctl 信息
                dev = all_devices[id]['os_path'].split('/')[-1]
                disk_info = get_dev_info_by_smartctl(dev, this_device['device_id'])
                this_device.update(disk_info)
                if "wwn" not in this_device and this_device['device_id'] in device_id_to_wwn:
                    this_device["wwn"] = device_id_to_wwn.get(this_device['device_id'])

                all_devices[id]['devices'].append(this_device)

    return list(all_devices.values())


def get_lsi_raid_devs_info_by_megacli():
    sata_dev_info = {}
    try:
        for item in megaclisas_status():
            sata_dev_info[item['os_path'].split('/')[-1]] = item

    except Exception as e:
        raise e

    return sata_dev_info


# megacli -PdLocate -start -physdrv[32:1] -a0 开灯
# megacli -PdLocate -stop -physdrv[32:1] -a0 关灯


def disk_light_up_by_megacli(ctl_id, eid_slt):
    sub_ret = ShellExec.call(f"megacli -PdLocate -start -physdrv[{eid_slt}] -a{ctl_id}")
    if sub_ret.stdout.find("successfully") != -1:
        return "Start Drive Locate Succeeded."
    else:
        return "Start Drive Locate Failed."


def disk_light_off_by_megacli(ctl_id, eid_slt):
    sub_ret = ShellExec.call(f"megacli -PdLocate -stop -physdrv[{eid_slt}] -a{ctl_id}")
    if sub_ret.stdout.find("successfully") != -1:
        return "Stop Drive Locate Succeeded."
    else:
        return "Stop Drive Locate Failed."


if __name__ == "__main__":
    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    # pp.pprint(get_lsi_raid_devs_info_by_storcli())
    pp.pprint(get_lsi_raid_devs_info_by_megacli())

