import os
import subprocess
import re
import json
import time
from common.shell import ShellExec


class BcacheCtl:
    VIRTUAL_BASE = "/sys/devices/virtual/block/"
    FS_BCACHE_BASE = "/sys/fs/bcache/"
    SYS_BLOCK_BASE = "/sys/block/"

    def runCommandGetOutput(self, cmd):
        result = 0
        successExec = True
        output = ""
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            print("runing command: " + str(e.cmd) + " fail, return: " + str(e.returncode))
            successExec = False
            output = e.stderr
            result = e.returncode
        return successExec, result, output

    def _getAllDataDev(self):
        dataSet = []
        temp1 = os.listdir(self.SYS_BLOCK_BASE)
        for i in temp1:
            if i.startswith("sd") or i.startswith("hd") or i.startswith("vd") or i.startswith("nvme"):
                temp2 = os.listdir(self.SYS_BLOCK_BASE + i)
                for j in temp2:
                    if j.startswith("bcache"):
                        path1 = self.SYS_BLOCK_BASE + i + "/bcache/dev"
                        if os.path.exists(path1):
                            cacheSetPath = self._getLinkRealLocation(path1)
                            temp3 = cacheSetPath.split("/")
                            dataSet.append({"data_device": i, "bcache_name": temp3[-1]})

                    if j.startswith("sd") or j.startswith("hd") or j.startswith("vd") or j.startswith("nvme"):
                        temp4 = self._getSysRealDev(j)
                        path1 = self.SYS_BLOCK_BASE + temp4 + "/bcache/dev"
                        if os.path.exists(path1):
                            cacheSetPath = self._getLinkRealLocation(path1)
                            temp3 = cacheSetPath.split("/")
                            dataSet.append({"data_device": j, "bcache_name": temp3[-1]})

        return dataSet

    def _writeFile(self, path1, data):
        result = 0
        successExec = True
        output = ""

        if os.path.exists(path1):

            try:
                with open(path1, 'w') as file1:
                    file1.write(data)
            except IOError as e:
                result = e.errno
                successExec = False
                output = e.strerror
        else:
            successExec = False
            result = 1
            output = path1 + " is not existed."

        cmd = [
            "sync"
        ]

        self.runCommandGetOutput(cmd)

        return successExec, result, output

    def _getAllCacheSet(self):
        cacheSet = []
        temp1 = os.listdir(self.SYS_BLOCK_BASE)
        for i in temp1:
            if i.startswith("sd") or i.startswith("nvme"):
                temp2 = os.listdir(self.SYS_BLOCK_BASE + i)
                for j in temp2:
                    if j.startswith("bcache"):
                        path1 = self.SYS_BLOCK_BASE + i + "/bcache/set"
                        if os.path.exists(path1):
                            cacheSetPath = self._getLinkRealLocation(path1)
                            temp3 = cacheSetPath.split("/")
                            cacheSet.append({"cache_device": i, "cset_uuid": temp3[-1]})

                    if j.startswith("sd") or j.startswith("nvme"):
                        temp4 = self._getSysRealDev(j)
                        path1 = self.SYS_BLOCK_BASE + temp4 + "/bcache/set"
                        if os.path.exists(path1):
                            cacheSetPath = self._getLinkRealLocation(path1)
                            temp3 = cacheSetPath.split("/")
                            cacheSet.append({"cache_device": j, "cset_uuid": temp3[-1]})

        return cacheSet

    def _getLinkRealLocation(self, path1):
        cmd = [
            "readlink",
            "-e",
            path1
        ]
        successExec, result, output = self.runCommandGetOutput(cmd)
        if successExec:
            return output.rstrip()
        else:
            return None

    def _getSysRealDev(self, dataDev):
        # bcache0:  /sys/block/bcache0/
        # sdb:  /sys/block/sdb/
        # sdb3:  /sys/block/sdb/sdb3

        regex = re.compile("^bcache[0-9]+$")
        if regex.match(dataDev):
            return (dataDev)

        regex = re.compile("^[v,h,s]d[a-z]+")
        if regex.match(dataDev):
            regex = re.compile("[0-9]+")
            m = regex.search(dataDev)
            if m is not None:
                # is a part
                disk = dataDev[0:m.start()]
                return (disk + "/" + dataDev)
            else:
                return (dataDev)

        regex = re.compile("^nvme[0-9]+n[0-9]+")
        if regex.match(dataDev):
            regex = re.compile("p[0-9]+")
            m = regex.search(dataDev)
            if m is not None:
                # is a part
                disk = dataDev[0:m.start()]
                return (disk + "/" + dataDev)
            else:
                return (dataDev)

        else:
            return None

    def getSequentialCutoff(self, dataDev):
        realDev = self._getSysRealDev(dataDev)
        path1 = "/sys/block/" + realDev + "/bcache/sequential_cutoff"

        if os.path.exists(path1):
            with open(path1, 'r') as file1:
                cutoff = file1.readline()
                return cutoff.rstrip()
        return None

    def getOsdFromBcachDataDev(self, bcacheX):
        cmd = [
            "ceph-volume",
            "lvm",
            "list",
            "--format",
            "json",
            "/dev/" + bcacheX
        ]
        successExec, result, output = self.runCommandGetOutput(cmd)

        if successExec:
            osdSetting = {}
            if len(output) > 0:
                osdList = json.loads(output)
                for (k, v) in osdList.items():
                    # only one
                    osdSetting["osd_id"] = v[0]["tags"]["ceph.osd_id"]
                    osdSetting["osd_fsid"] = v[0]["tags"]["ceph.osd_fsid"]
                    db_uuid_device = v[0]["tags"].get("ceph.db_device","")
                    wal_uuid_device = v[0]["tags"].get("ceph.wal_device","")
                    if db_uuid_device != "":
                        db_device_path = self._getLinkRealLocation(db_uuid_device)
                        db_device = db_device_path.split('/')[-1]
                    else:
                        db_device=""
                    if wal_uuid_device != "":
                        wal_device_path = self._getLinkRealLocation(wal_uuid_device)
                        wal_device = wal_device_path.split('/')[-1]
                    else:
                        wal_device = ""
                    osdSetting["db_device"] = db_device
                    osdSetting["wal_device"] = wal_device
                    return osdSetting
        else:
            return None

    def getCacheBlockPciPath(self, csetUuid):
        if csetUuid.startswith("00000000-0000-0000-0000-000000000000"):
            return None
        path1 = self.FS_BCACHE_BASE + csetUuid + "/cache0"
        cmd = [
            "readlink",
            "-e",
            path1
        ]
        successExec, result, output = self.runCommandGetOutput(cmd)
        if successExec:
            return output.rstrip()
        else:
            return None

    def getDataBlockPciPath(self, bcacheX):
        path1 = self.VIRTUAL_BASE + bcacheX + "/bcache"
        return self._getLinkRealLocation(path1)

    def bcacheSuperShow(self, dev):
        cmd = [
            "bcache-super-show",
            "-f",
            "/dev/" + dev
        ]

        successExec, result, output = self.runCommandGetOutput(cmd)
        if successExec:
            result1 = {}
            for line in output.splitlines():
                pair = line.split("\t")
                if (len(pair[0]) > 0):
                    result1[pair[0]] = pair[-1]
            return result1
        else:
            return None

    def listOsdBcacheDevs(self):

        bcacheDevs = []

        if not os.path.exists(self.VIRTUAL_BASE):
            return bcacheDevs

        temp1 = os.listdir(self.VIRTUAL_BASE)
        temp2 = []
        for i in temp1:
            if i.startswith("bcache"):
                temp2.append(i)

        if (len(temp2) > 0):
            temp2.sort()

        for i in temp2:
            if i.startswith("bcache"):
                dataBlockPciPath = self.getDataBlockPciPath(i)
                bcacheDev = {}
                if dataBlockPciPath is not None:
                    bcacheDev["bcache_name"] = i
                    temp1 = dataBlockPciPath.split("/")
                    dataDev = temp1[-2]
                    bcacheDev["data_device"] = dataDev

                    temp1 = self.getSequentialCutoff(bcacheDev["data_device"])
                    if temp1 is not None:
                        bcacheDev["sequential_cutoff"] = temp1

                    temp1 = self.bcacheSuperShow(dataDev)
                    bcacheDev["cset_uuid"] = temp1["cset.uuid"]
                    bcacheDev["cache_mode"] = temp1["dev.data.cache_mode"]
                    bcacheDev["cache_state"] = temp1["dev.data.cache_state"]

                    cacheBlockPciPath = self.getCacheBlockPciPath(bcacheDev["cset_uuid"])

                    if cacheBlockPciPath is not None:
                        temp1 = cacheBlockPciPath.split("/")
                        cacheDev = temp1[-2]
                    else:
                        cacheDev = None

                    bcacheDev["cache_device"] = cacheDev

                    osdSetting = self.getOsdFromBcachDataDev(bcacheDev["bcache_name"])
                    if osdSetting is not None:
                        bcacheDev["osd_id"] = osdSetting["osd_id"]
                        bcacheDev["osd_fsid"] = osdSetting["osd_fsid"]
                    else:
                        bcacheDev["osd_id"] = None
                        bcacheDev["osd_fsid"] = None

                    bcacheDevs.append(bcacheDev)
        return bcacheDevs

    def listCacheDevs(self):

        cacheSet = self._getAllCacheSet()

        dataSet = self._getAllDataDev()

        tempDataSet = []

        onlyDataSet = []

        resultSet = {"cache_data": [], "only_data": [], "only_cache": []}

        if dataSet is not None:
            for i in dataSet:
                temp1 = self.bcacheSuperShow(i["data_device"])
                i["cset_uuid"] = temp1["cset.uuid"]
                i["cache_mode"] = temp1["dev.data.cache_mode"]
                i["cache_state"] = temp1["dev.data.cache_state"]

                temp2 = self.getSequentialCutoff(i["data_device"])
                if temp2 is not None:
                    i["sequential_cutoff"] = temp2

                if i["cset_uuid"] == "00000000-0000-0000-0000-000000000000":
                    onlyDataSet.append(i)
                else:
                    tempDataSet.append(i)

                for j in range(len(cacheSet)):

                    if cacheSet[j]["cset_uuid"] == i["cset_uuid"]:
                        i["cache_device"] = cacheSet[j]["cache_device"]
                        cacheSet.pop(j)
                        break

            resultSet["cache_data"] = tempDataSet
            resultSet["only_data"] = onlyDataSet

        if cacheSet is not None and len(cacheSet) > 0:
            resultSet["only_cache"] = cacheSet

        return resultSet

    def isUuid(self, uuid1):
        regex = re.compile("[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}")
        return regex.match(uuid1)

    def _detachBcacheX(self, bcacheX):

        result = 0
        output = ""

        path1 = self.SYS_BLOCK_BASE + bcacheX + "/bcache/detach"

        if os.path.exists(path1):
            data = "1"
            self._writeFile(path1, data)
        else:
            result = 1
            output = bcacheX + ": " + path1 + " is not exist"

        return [result, output]

    def detach(self, what1):
        result = 0
        output = ""

        bcacheName = None

        if self.isUuid(what1):
            dataCacheSet = self.listCacheDevs()
            findUuid = False
            for i in dataCacheSet["cache_data"]:
                if i["cset_uuid"] == what1:
                    findUuid = True
                    bcacheName = i["bcache_name"]

            if not findUuid:
                result = 1
                output = "Fail to find cset uuid: " + what1 + "."
                return [result, output]
        else:
            regex = re.compile("^bcache[0-9]+$")
            if regex.match(what1):
                bcacheName = what1
            else:
                reg1 = "(^[s,v,h]d[a-z]+[0-9]*$|^nvme[0-9]+n[0-9]+(p[0-9]+)*)"
                regex = re.compile(reg1)
                if regex.match(what1):
                    dataDev = self._getSysRealDev(what1)
                    path1 = self.SYS_BLOCK_BASE + dataDev + "/bcache/detach"
                    if os.path.exists(path1):
                        self._writeFile(path1, "1")
                    else:
                        result = 1
                        output = "Fail to find path: " + path1 + ". Please check bcache setting."

        if bcacheName is not None:
            [result, output] = self._detachBcacheX(bcacheName)

        return [result, output]

    def attach(self, csetUuid, what1):
        result = 1
        output = "attach fail"
        if not self.isUuid(csetUuid):
            result = 1
            output = "input: " + csetUuid + " is not an uuid"
            return [result, output]

        regex = re.compile("^bcache[0-9]+$")
        if regex.match(what1):
            path1 = self.SYS_BLOCK_BASE + what1 + "/bcache/attach"
            if os.path.exists(path1):
                successExec, result, output = self._writeFile(path1, csetUuid)
            else:
                result = 1
                output = path1 + " do not exist"
        else:
            reg1 = "(^[s,v,h]d[a-z]+[0-9]*$|^nvme[0-9]+n[0-9]+(p[0-9]+)*)"
            regex = re.compile(reg1)
            if regex.match(what1):
                dataDev = self._getSysRealDev(what1)
                path1 = self.SYS_BLOCK_BASE + dataDev + "/bcache/attach"
                if os.path.exists(path1):
                    successExec, result, output = self._writeFile(path1, csetUuid)
                else:
                    result = 1
                    output = path1 + " do not exist"

            else:
                result = 1
                output = "input: " + what1 + " error"

        return [result, output]

    def stop(self, what1):
        result = 0
        output = ""

        if self.isUuid(what1):
            path1 = self.FS_BCACHE_BASE + what1 + "/stop"
            if os.path.exists(path1):
                self._writeFile(path1, "1")
            else:
                result = 1
                output = "Fail to find path: " + path1 + ". Please check bcache setting."
        else:
            dataDev = self._getSysRealDev(what1)

            if dataDev is not None:
                path1 = self.SYS_BLOCK_BASE + dataDev + "/bcache/stop"
                if os.path.exists(path1):
                    self._writeFile(path1, "1")
                else:
                    result = 1
                    output = "Fail to find path: " + path1 + ". Please check bcache setting."
            else:
                result = 1
                output = what1 + " is not legal input."

        return [result, output]

    def wipe(self, what1):
        result = 0
        output = ""

        reg1 = "(^[s,v,h]d[a-z]+[0-9]*$|^nvme[0-9]+n[0-9]+(p[0-9]+)*)"
        regex = re.compile(reg1)
        if regex.match(what1):
            dataDev = self._getSysRealDev(what1)

            if dataDev is not None:
                path1 = self.SYS_BLOCK_BASE + dataDev + "/bcache/"
                if os.path.exists(path1):
                    result = 1
                    output = path1 + " still exist. Please first delete lvm vg, detach cache, stop bcache, then wipe device"
                else:
                    ####carefull: destroy dev superblock!
                    path1 = "/dev/" + what1
                    buffer1 = '\0' * 1048576
                    successExec, result, output = self._writeFile(path1, buffer1)
                    return [result, output]
            else:
                result = 1
                output = what1 + " is illegal input."
        else:
            result = 1
            output = what1 + " is illegal input."

        return [result, output]

    def cutoff(self, what1, cutoffSize):
        result = 0
        output = ""

        reg1 = "^[0-9]+$"
        regex = re.compile(reg1)
        if not regex.match(cutoffSize):
            result = 1
            output = "input sequential_cutoff size: " + cutoffSize + " error"
            return [result, output]

        reg1 = "(^[s,v,h]d[a-z]+[0-9]*$|^nvme[0-9]+n[0-9]+(p[0-9]+)*)"
        regex = re.compile(reg1)
        if regex.match(what1):
            dataDev = self._getSysRealDev(what1)

            if dataDev is not None:
                path1 = self.SYS_BLOCK_BASE + dataDev + "/bcache/sequential_cutoff"
                if os.path.exists(path1):
                    self._writeFile(path1, cutoffSize)
                else:
                    result = 1
                    output = "Fail to find path: " + path1 + ". Please check bcache setting."
        else:
            result = 1
            output = what1 + " is illegal input."

        return [result, output]

    def makeBcache(self, dataDev=None, cacheDev=None, wrirteThroughEnable=False):
        result = 0
        output = ""

        if wrirteThroughEnable:
            cacheMode = "--writethrough"
        else:
            cacheMode = "--writeback"

        cmd = [
            "make-bcache",
            cacheMode
        ]

        if dataDev is not None:
            # assume input is like sdc

            [result1, output1] = self.wipe(dataDev)

            if result1 != 0:
                return [result1, output1]

            dataDev = "/dev/" + dataDev

            cmd.append("-B")
            cmd.append(dataDev)

        if cacheDev is not None:
            # assume input is like nvme0n1p5
            [result1, output1] = self.wipe(cacheDev)

            if result1 != 0:
                return [result1, output1]

            cacheDev = "/dev/" + cacheDev

            cmd.append("-C")
            cmd.append(cacheDev)

        successExec, result, output = self.runCommandGetOutput(cmd)

        return [result, output]

    def isOsdRunning(self, osdId):
        cmd = [
            "ps",
            "-aux",
        ]

        successExec, result, output = self.runCommandGetOutput(cmd)
        if successExec:
            for i in output.split("\n"):
                regex = re.compile(".*ceph-osd\ .*--id\ " + osdId + ".*")
                if regex.match(i):
                    return True
        return False

    def isCephLvmAsChild(self, dev):
        cmd = [
            "lsblk",
            "-n",
            "-o",
            "name",
            "/dev/" + dev
        ]
        # like:
        # lsblk /dev/bcache0  -o name -n
        # bcache0
        # └─ceph--81a74863--ee6f--42bd--8496--d456354661cd-osd--block--4955427c--6597--4727--be7e--f825d5aa8fae

        successExec, result, output = self.runCommandGetOutput(cmd)
        if successExec:
            lines = output.split("\n")
            if len(lines) >= 2:
                vgLv = lines[1]
                regex = re.compile(
                    ".*ceph--[a-fA-F0-9]{8}--[a-fA-F0-9]{4}--[a-fA-F0-9]{4}--[a-fA-F0-9]{4}--[a-fA-F0-9]{12}-osd--block--.*")
                if regex.match(vgLv):
                    vgLv = vgLv.replace("--", "-")
                    vgLv = vgLv.replace("-osd-block", "/osd-block")
                    vgLv = re.sub("^.*ceph", "ceph", vgLv)
                    return True, vgLv
        return False, ""

    def vgRemove(self, vg):

        cmd = [
            "vgremove",
            "-y",
            vg
        ]

        successExec, result, output = self.runCommandGetOutput(cmd)

        if successExec:
            cmd = [
                "sync"
            ]
        self.runCommandGetOutput(cmd)
        return [result, output]

    def pvRemove(self, pv):

        cmd = [
            "pvremove",
            "-y",
            pv
        ]

        successExec, result, output = self.runCommandGetOutput(cmd)

        if successExec:
            cmd = [
                "sync"
            ]
        self.runCommandGetOutput(cmd)
        return [result, output]

    def destroyOsdBcache(self, osdId):
        result = 0
        output = ""

        regex = re.compile("^[0-9]+$")
        if regex.match(osdId):
            if self.isOsdRunning(osdId):
                result = 1
                output = "osd." + osdId + " is still running, please stop it first."
                return [result, output]

            devs = self.listOsdBcacheDevs()
            if devs is None:
                result = 1
                output = "Can not find any bcacheX"
                return [result, output]

            findDev = False

            for dev in devs:
                if dev["osd_id"] is not None and dev["osd_id"] == osdId:
                    bcacheX = dev["bcache_name"]
                    findDev = True
                    [result, output] = self.destroyBcache(bcacheX)

            if not findDev:
                result = 1
                output = "Can not find any bcacheX paired with osd." + osdId

        else:
            result = 1
            output = osdId + " is illegal input."

        return [result, output]

    def destroyBcache(self, bcacheX):
        result = 0
        output = ""

        regex = re.compile("^bcache[0-9]+$")
        if regex.match(bcacheX):
            devs = self.listOsdBcacheDevs()
            if devs is None:
                result = 1
                output = bcacheX + " is not existed."
                return [result, output]
            for dev in devs:
                if dev["bcache_name"] == bcacheX:
                    dataDev = dev["data_device"]
                    cacheDev = dev["cache_device"]
                    csetUuid = dev["cset_uuid"]
                    osdId = dev["osd_id"]
                    if osdId is not None:
                        if self.isOsdRunning(osdId):
                            result = 1
                            output = "osd." + osdId + " is still running, please stop it first."
                            return [result, output]

            devs = self.listOsdBcacheDevs()
            findDev = False
            for dev in devs:
                if dev["bcache_name"] == bcacheX:
                    findDev = True
                    dataDev = dev["data_device"]
                    cacheDev = dev["cache_device"]
                    csetUuid = dev["cset_uuid"]

                    [isLvmChild, vgLv] = self.isCephLvmAsChild(bcacheX)
                    if isLvmChild:
                        vgLvList = vgLv.split("/")
                        [result, output] = self.vgRemove(vgLvList[0])
                        if result != 0:
                            return [result, output]

                        pvDev = "/dev/" + bcacheX
                        [result, output] = self.pvRemove(pvDev)
                        if result != 0:
                            return [result, output]

                        print("removed ceph vg: " + vgLvList[0] + ". removed pv: " + pvDev)

                    [result, output] = self.detach(csetUuid)
                    if result != 0:
                        return [result, output]

                    [result, output] = self.stop(csetUuid)
                    if result != 0:
                        return [result, output]

                    time.sleep(2)  # test on vdx, will need time dellay

                    [result, output] = self.wipe(cacheDev)
                    if result != 0:
                        return [result, output]

                    [result, output] = self.stop(dataDev)
                    if result != 0:
                        return [result, output]

                    time.sleep(2)  # test on vdx, will need time dellay

                    [result, output] = self.wipe(dataDev)
                    if result != 0:
                        return [result, output]

            if not findDev:
                result = 1
                output = bcacheX + " is not existed."
        else:
            result = 1
            output = bcacheX + " is illegal input."

        return [result, output]

    def listOsdDevInfo(self):

        bcacheDevs = []

        if not os.path.exists(self.VIRTUAL_BASE):
            return bcacheDevs

        temp1 = os.listdir(self.VIRTUAL_BASE)
        temp2 = []
        for i in temp1:
            if i.startswith("bcache"):
                temp2.append(i)

        if (len(temp2) > 0):
            temp2.sort()

        for i in temp2:
            if i.startswith("bcache"):
                dataBlockPciPath = self.getDataBlockPciPath(i)
                bcacheDev = {}
                if dataBlockPciPath is not None:
                    bcacheDev["bcache_name"] = i
                    temp1 = dataBlockPciPath.split("/")
                    dataDev = temp1[-2]
                    bcacheDev["data_device"] = dataDev

                    temp1 = self.bcacheSuperShow(dataDev)
                    bcacheDev["cset_uuid"] = temp1["cset.uuid"]

                    cacheBlockPciPath = self.getCacheBlockPciPath(bcacheDev["cset_uuid"])

                    if cacheBlockPciPath is not None:
                        temp1 = cacheBlockPciPath.split("/")
                        cacheDev = temp1[-2]
                    else:
                        cacheDev = ""

                    bcacheDev["cache_device"] = cacheDev

                    osdSetting = self.getOsdFromBcachDataDev(bcacheDev["bcache_name"])
                    if osdSetting is not None:
                        bcacheDev["osd_id"] = osdSetting["osd_id"]
                        bcacheDev["db_device"] = osdSetting["db_device"]
                        bcacheDev["wal_device"] = osdSetting["wal_device"]
                    else:
                        bcacheDev["osd_id"] = ""
                        bcacheDev["db_device"] = ""
                        bcacheDev["wal_device"] = ""

                    bcacheDevs.append(bcacheDev)
        return bcacheDevs


def get_osd_detail_info():
    bcacheDevs = []
    hostname = ShellExec.call("hostname")
    _bcachectl = BcacheCtl()
    response_str = ShellExec.call("ceph-volume lvm list --format json")
    if "bcache" in response_str.stdout:
        bcacheDevs = _bcachectl.listOsdDevInfo()  # osd_id/bcache_name/data_device/db_device/wal_device/cache_device
    # else:

    response = json.loads(response_str.stdout)
    for (k, v) in response.items():
        bcacheDev={}
        bcacheDev["osd_id"] = k
        block = v[0]["devices"][0]
        if "bcache" in block:
            continue

        bcacheDev["data_device"] = block.split("/")[-1]
        db_uuid_device = v[0]["tags"].get("ceph.db_device", "")
        wal_uuid_device = v[0]["tags"].get("ceph.wal_device", "")
        if db_uuid_device != "":
            db_device_path = _bcachectl._getLinkRealLocation(db_uuid_device)
            db_device = db_device_path.split('/')[-1]
        else:
            db_device = ""
        if wal_uuid_device != "":
            wal_device_path = _bcachectl._getLinkRealLocation(wal_uuid_device)
            wal_device = wal_device_path.split('/')[-1]
        else:
            wal_device = ""
        bcacheDev["db_device"] = db_device
        bcacheDev["wal_device"] = wal_device
        bcacheDevs.append(bcacheDev)

    for dev in bcacheDevs:
        dev["osd_host"] = hostname.stdout.strip()

    return bcacheDevs


if __name__ == "__main__":
    print(get_osd_detail_info())
