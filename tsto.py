#!/usr/bin/python

"""
TSTO tool.
WARNING: absolutly no warranties. Use this script at own risk.
"""

__author__ = 'jsbot@ya.ru (Oleg Polivets)'

import urllib2
import json
import gzip
import StringIO
import time
import struct
import sys
import traceback
import random
import LandData_pb2

class TSTO:
    def __init__(self):
        self.dataVerison                   = 29
        self.mLogined                      = False
        self.mLandMessage                  = LandData_pb2.LandMessage()
        self.mExtraLandMessage             = None
        self.headers                       = dict()
        self.headers["Accept"]             = "*/*"
        self.headers["Accept-Encoding"]    = "gzip"
        self.headers["client_version"]     = "4.16.3"
        self.headers["server_api_version"] = "4.0.0"
        self.headers["EA-SELL-ID"]         = "857120"
        self.headers["platform"]           = "android"
        self.headers["os_version"]         = "15.0.0"
        self.headers["hw_model_id"]        = "0 0.0"
        self.headers["data_param_1"]       = "2633815347"
        self.mMhClientVersion              = "Android.4.16.3"

### Network ###

    def doRequest(self, method, content_type, host, path, keep_alive=False, body=[], uncomressedLen=-1):
        url = ("https://%s%s" % (host, path)).encode('utf-8')
        print(url)

        # filling headers for this request
        headers = self.headers.copy()
        if uncomressedLen > -1:
            headers["Content-Encoding"]    = "gzip"
            headers["Uncompressed-Length"] = uncomressedLen
            headers["Content-Length"]      = len(body)
        if keep_alive == True:
            headers["Connection"] = "Keep-Alive"
        else:
            headers["Connection"] = "Close"
        headers["Content-Type"] = content_type

        # do request
        request = urllib2.Request(url=url, data=body, headers=headers)
        request.get_method = lambda: method
        response = urllib2.urlopen(request)

        # reading response
        if response.info().get('Content-Encoding') != 'gzip':
            data = response.read()
        else:
            buf = StringIO.StringIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            data = f.read()

        if (len(data) == 0):
            print("no content")
        else:
            if response.info().get("Content-Type") == 'application/x-protobuf':
                print(response.info().get("Content-Type"))
            else:
                print(data)
        return data

    def protobufParse(self, msg, data):
        parsed = True
        try:
            msg.ParseFromString(data)
        except Exception:
            parsed = False
        return parsed

    def checkLogined(self):
        if self.mLogined != True:
            raise TypeError("ERR: need to login before perform this action!!!")

    def doAuth(self, email, password):
        data = self.doRequest("POST", "application/json", "nucleus.tnt-ea.com"
            , "/rest/token/%s/%s/" % (email, password))
        data = json.JSONDecoder().decode(data);
        self.mUserId = data["userId"]
        self.doAuthWithToken(data["token"])

    def doAuthWithToken(self, token):
        self.mToken = token
        self.headers["nucleus_token"] = token
        self.headers["AuthToken"] = token

        data = self.doRequest("GET", "application/json", "auth.tnt-ea.com"
            , "/rest/oauth/origin/%s/Simpsons-Tapped-Out/" % self.mToken)
        data = json.JSONDecoder().decode(data);
        self.mCode  = data["code"]
        self.mTntId = data["tntId"]
        self.headers["mh_auth_method"]    = "tnt"
        self.headers["mh_auth_params"]    = data["code"]
        self.headers["mh_client_version"] = self.mMhClientVersion

        data = self.doRequest("PUT", "application/x-protobuf", "prod.simpsons-ea.com"
            , "/mh/users?appVer=2.2.0&appLang=en&application=tnt&applicationUserId=%s" % self.mTntId, True)
        urm  = LandData_pb2.UsersResponseMessage()
        urm.ParseFromString(data)
        self.mUid     = urm.user.userId;
        self.mSession = urm.token.sessionKey;
        self.headers["mh_uid"]         = self.mUid;
        self.headers["mh_session_key"] = self.mSession;

        data = self.doRequest("GET", "application/x-protobuf", "prod.simpsons-ea.com"
                , "/mh/games/bg_gameserver_plugin/checkToken/%s/protoWholeLandToken/" % (self.mUid), True)
        wltr = LandData_pb2.WholeLandTokenRequest()
        if self.protobufParse(wltr, data) == False:
            wltr = LandData_pb2.WholeLandTokenRequest();
            wltr.requestId = self.mTntId
            data = wltr.SerializeToString()
            data = self.doRequest("POST", "application/x-protobuf", "prod.simpsons-ea.com"
                , "/mh/games/bg_gameserver_plugin/protoWholeLandToken/%s/" % self.mUid, True, data)
            wltr = LandData_pb2.WholeLandTokenRequest()
            wltr.ParseFromString(data)
        self.mUpdateToken = wltr.requestId;
        self.headers["target_land_id"]    = self.mUid
        self.headers["land-update-token"] = self.mUpdateToken
        self.mLogined = True;

    def doLandDownload(self):
        self.checkLogined()
        data = self.doRequest("GET", "application/x-protobuf", "prod.simpsons-ea.com"
                , "/mh/games/bg_gameserver_plugin/protoland/%s/" % self.mUid, True);
        self.mLandMessage = LandData_pb2.LandMessage()
        self.mLandMessage.ParseFromString(data)
        self.doFileSave("%s.%f" % (self.mUid, time.time()))

    def doLandUpload(self):
        self.checkLogined()
        if self.mLandMessage.id == '':
            raise TypeError("ERR: LandMessage.id is empty!!!")
        # send extra message before landMessage if any
        self.doUploadExtraLandMessage()
        # store last played time and send GZipped Land itself
        self.mLandMessage.friendData.lastPlayedTime = int(time.time())
        data = self.mLandMessage.SerializeToString()
        uncomressedLen = len(data)
        out = StringIO.StringIO()
        g=gzip.GzipFile(fileobj=out, mode="w")
        g.write(data)
        g.close()
        data = out.getvalue()
        data = self.doRequest("POST", "application/x-protobuf", "prod.simpsons-ea.com"
            , "/mh/games/bg_gameserver_plugin/protoland/%s/" % self.mUid, True, data, uncomressedLen);

    def doLoadCurrency(self):
        self.checkLogined()
        data = self.doRequest("GET", "application/x-protobuf", "prod.simpsons-ea.com"
                , "/mh/games/bg_gameserver_plugin/protocurrency/%s/" % self.mUid, True);
        currdat = LandData_pb2.CurrencyData()
        currdat.ParseFromString(data)
        print(str(currdat))

    def doDownloadFriendsData(self):
        data = self.doRequest("POST", "application/x-protobuf", "prod.simpsons-ea.com"
            , "/mh/games/bg_gameserver_plugin/friendData?debug_mayhem_id=%s" % self.mUid)
        fdresp = LandData_pb2.GetFriendDataResponse()
        fdresp.ParseFromString(data)
        return fdresp

    def doUploadExtraLandMessage(self):
        msg = self.mExtraLandMessage
        if msg == None:
            return
        data = msg.SerializeToString()
        data = self.doRequest("POST", "application/x-protobuf", "prod.simpsons-ea.com"
            , "/mh/games/bg_gameserver_plugin/extraLandUpdate/%s/protoland/" % self.mUid, True, data)
        self.mExtraLandMessage = None

    def doResetNotifications(self):
        data = self.doRequest("GET", "application/x-protobuf", "prod.simpsons-ea.com"
            , "/mh/games/bg_gameserver_plugin/event/%s/protoland/" % self.mUid, True);
        events = LandData_pb2.EventsMessage()
        events.ParseFromString(data)
        if self.protobufParse(events, data) == False:
            return
        if self.mExtraLandMessage == None:
            self.mExtraLandMessage = LandData_pb2.ExtraLandMessage()
        extra = self.mExtraLandMessage
        alreadyDone = set()
        for ev in events.event:
            if ev.id in alreadyDone:
                continue 
            xev = extra.event.add()
            xev.id = ev.id
            alreadyDone.add(ev.id)
        data = self.doRequest("POST", "application/xaml+xml", "prod.simpsons-ea.com"
            , "/mh/games/bg_gameserver_plugin/usernotificationstatus/?type=reset_count", True)
        data = self.doRequest("POST", "application/xaml+xml", "prod.simpsons-ea.com"
            , "/mh/games/bg_gameserver_plugin/usernotificationstatus/?type=reset_time", True)

    # show sorted friends list

    def showFriends(self):
        self.checkLogined()
        friends = self.doDownloadFriendsData()
        fds = []
        for fd in friends.friendData:
            f = fd.friendData
            fds.append("%s:%s:%d:%s" % (time.strftime("%Y%m%d%H%M", time.localtime(f.lastPlayedTime)), fd.friendId, f.level, f.name))
        fds.sort()
        for f in fds:
            print(f)

    # drop friends that not playing more given days

    def dropFriends(self, days):
        self.checkLogined()
        ts = time.mktime(time.localtime())
        crit = (24 * 60 * 60 * days)
        friends = self.doDownloadFriendsData()

#        for key, value in self.headers.items():
#            print (key, value)

#        self.doRequest("GET", "application/json", "m.friends.dm.origin.com"
#            , "//friends/user/%s/pendingfriends" % (self.mUserId)
#            , True)
#        self.doRequest("GET", "application/json", "m.friends.dm.origin.com"
#            , "//friends/user/%s/globalgroup/friendIds" % (self.mUserId)
#            , True)
        
        # find what don't need to delete
        notDel=[]
        for fd in friends.friendData:
            f = fd.friendData
            if (ts - f.lastPlayedTime) < crit:
                notDel.append(fd.friendId)
                continue
            print("%s:%s:%d:%s" % (time.strftime("%Y%m%d%H%M", time.localtime(f.lastPlayedTime)), fd.friendId, f.level, f.name))
            if raw_input("Drop this friend (y/N) ").lower() == 'y':
                self.doRequest("GET", "application/json", "m.friends.dm.origin.com"
                    , "//friends/deleteFriend?nucleusId=%s&friendId=%s" % (self.mUserId, fd.externalId)
                    , True)
        # get indexes for deletion
        forDel=[]
        for i in range(len(self.mLandMessage.friendListData)):
            f = self.mLandMessage.friendListData[i]
            if f.friendID not in notDel:
                forDel.insert(0, i)
        # delete by indexes
        for i in forDel:
            del self.mLandMessage.friendListData[i]
        self.mLandMessage.innerLandData.numSavedFriends = len(self.mLandMessage.friendListData)

    def showTimes(self):
        tm = time.gmtime(self.mLandMessage.innerLandData.timeSpentPlaying)
        timeSpentPlaying = "%d year(s) %d month(s) %d days %d h %d m" % (1970 - tm.tm_year,
            tm.tm_mon - 1, tm.tm_mday, tm.tm_hour, tm.tm_min)
        print("""friendData.lastPlayedTime: %s
userData.lastBonusCollection: %s
innerLandData.timeSpentPlaying: %s
innerLandData.creationTime: %s""" % (
            time.ctime(self.mLandMessage.friendData.lastPlayedTime),
            time.ctime(self.mLandMessage.userData.lastBonusCollection),
            timeSpentPlaying,
            time.ctime(self.mLandMessage.innerLandData.creationTime)))

### In-game items ###
    def arrSplit(self, arr):
        itms = []
        for it in arr.split(','):
            tt = it.split('-')
            if (len(tt) >= 2 and int(tt[0]) < int(tt[1])):
                for i in range(int(tt[0]), int(tt[1])+1):
                    itms.append(i)
            else:
                itms.append(int(tt[0]))
        return itms

    def inventoryAdd(self, itemsid, itemtype=0, count=1):
        items = self.splitArr(itemsId)
        # check if present
        for it in items:
            for item in self.mLandMessage.inventoryItemData:
                if item.itemID == it and item.itemType == itemtype:
                    raise TypeError("ERR: inventoryItem %d:%d" % (it, itemtype))
        # now add
        for it in items:
            t = self.mLandMessage.inventoryItemData.add()
            t.header.id = self.mLandMessage.innerLandData.nextInstanceID
            t.itemID = it
            t.itemType = itemtype
            t.count  = count
            t.isOwnerList = False
            t.fromLand = 0
            t.sourceLen = 0
            self.mLandMessage.innerLandData.nextInstanceID    = t.header.id + 1
            self.mLandMessage.innerLandData.numInventoryItems = len(self.mLandMessage.inventoryItemData)

    def inventoryCount(self, itemid, itemtype, count):
        it = -1
        for i in range(len(self.mLandMessage.inventoryItemData)):
            item = self.mLandMessage.inventoryItemData[i]
            if item.itemID == itemid and item.itemType == itemtype:
                it = i
                break
        if count <= 0:
            if it != -1:
                del self.mLandMessage.inventoryItemData[it]
                self.mLandMessage.innerLandData.numInventoryItems = len(self.mLandMessage.inventoryItemData)
        else:
            if it != -1:
                self.mLandMessage.inventoryItemData[it].count = count
            else:
                self.inventoryAdd(str(itemid), itemtype, count)

    def donutsAdd(self, amount):
        elm = self.mExtraLandMessage;
        if elm == None:
            elm = LandData_pb2.ExtraLandMessage()
            self.mExtraLandMessage = elm
        nextId = self.mLandMessage.innerLandData.nextCurrencyID
        sum = 0
        while sum < amount:
            cur = random.randint(499, 500)
            if sum + cur > amount:
                cur = amount - sum 
            delta = elm.currencyDelta.add()
            delta.id = nextId
            delta.reason = "JOB"
            delta.amount = cur
            nextId += 1
            sum += cur
        self.mLandMessage.innerLandData.nextCurrencyID = nextId

    def spendableSet(self, type, amount):
        for sp in self.mLandMessage.spendablesData.spendable:
            if sp.type == type:
                sp.amount = amount
                return
        raise ValueError("ERR: can't found spendable with id=%d" % type)

    def spendablesAllSet(self, amount):
        self.set_money(amount)
        for sp in self.mLandMessage.spendablesData.spendable:
            if sp.type != 57: # skip FP
                sp.amount = amount

    def skinsSet(self, data):
        self.mLandMessage.skinUnlocksData.skinUnlock      = data
        self.mLandMessage.skinUnlocksData.skinReceived    = data
        self.mLandMessage.skinUnlocksData.skinUnlockLen   = len(data)
        self.mLandMessage.skinUnlocksData.skinReceivedLen = len(data)

    def buildings_move(self, building, x, y, flip):
        for b in self.mLandMessage.buildingData:
            if b.building == building:
                b.positionX = x
                b.positionY = y
                b.flipState = flip

    def set_money(self, amount):
        self.mLandMessage.userData.money = amount

    def set_level(self, level):
        self.mLandMessage.friendData.level = level
        self.mLandMessage.userData.level = level

    def hurry(self):
        for job in self.mLandMessage.jobData:
            job.state = 2

    def questComplete(self, id):
        qst = None
        for q in self.mLandMessage.questData:
            if q.questID == id:
                qst = q
                break
        if qst == None:
            qst = self.mLandMessage.questData.add()
            qst.questID   = id;
            qst.timesCompleted = 0
            qst.header.id = self.mLandMessage.innerLandData.nextInstanceID
            self.mLandMessage.innerLandData.nextInstanceID = qst.header.id + 1
            self.mLandMessage.innerLandData.numQuests      = len(self.mLandMessage.questData)
        qst.questState = 5
        qst.numObjectives = 0
        qst.questScriptState = 0
        qst.timesCompleted += 1
        for i in range(len(qst.objectiveData)):
            del qst.objectiveData[i]

    def cleanR(self):
        data=''
        for i in range(16 * 13):
            data += '1'
        for i in range(16 *  3):
            data += '0'

        self.mLandMessage.friendData.dataVersion = self.dataVerison
        self.mLandMessage.innerLandData.landBlocks = data
        self.mLandMessage.friendData.boardwalkTileCount = 0
        self.mLandMessage.innerLandData.landBlockWidth  = 16
        self.mLandMessage.innerLandData.landBlockHeight = 16

        data=''
        for i in range(14 * 13 * 16):
            data += 'G'

        self.mLandMessage.roadsData.mapDataSize = len(data)
        self.mLandMessage.roadsData.mapData = data
        self.mLandMessage.riversData.mapDataSize = len(data)
        self.mLandMessage.riversData.mapData = data

        data=''
        for i in range(2 * 13 * 16):
            data += 'G'

        self.mLandMessage.oceanData.mapDataSize = len(data)
        self.mLandMessage.oceanData.mapData = data

    def cleanDebris(self):
        idx2del = []
        for idx, b in enumerate(self.mLandMessage.buildingData):
            if b.building in (1026, 1034, 1035, 1036, 1037, 3115, 3118, 3126, 3128, 3131):
                idx2del.insert(0, idx)
        for idx in idx2del:
            del self.mLandMessage.buildingData[idx]

    def varChange(self, vars, value):
        for name in vars.split(','):
            found = False
            for e in self.mLandMessage.specialEventsData.specialEvent:
                for v in e.variables.variable:
                    if v.name == name:
                        found = True
                        v.value = value
            if found == False:
                raise ValueError("ERR: can't found variable with name='%s'" % name)

    def varsPrint(self, names):
        printAll = names == None
        if printAll == False: ns = names.split(',')
        for e in self.mLandMessage.specialEventsData.specialEvent:
            for v in e.variables.variable:
                if printAll == False and ns.count(v.name) == 0: continue
                print("%s=%s" % (v.name, v.value))

    def standard(self, email, password):
        self.doAuth(email, password)
        self.doLandDownload()
        self.inventoryAdd("3704", 0, 15)  # 15 CubicZirconia
        self.inventoryAdd("1039", 0, 50)  # 50 special trees
        self.inventoryAdd("1040", 0, 50)  # 50 another special trees
        self.inventoryAdd("1217", 0, 200) # 200 IChochoseYou trains
        self.inventoryAdd("9", 2, 999)    # 999 Buddah (9)
        self.inventoryAdd("44", 2, 999)   # 999 Golden scratchers (44)
        self.inventoryAdd("5000", 2, 100) # 200 squidport tiles (5000)
        self.spendablesAllSet(987654321)
        self.donutsAdd(5432)
        self.doLandUpload()

### Operations with files ###

    def doSaveAsText(self):
        if self.mLandMessage.id == '':
            raise TypeError("ERR: LandMessage.id is empty!!!")
        with open("%s.txt" % self.mLandMessage.id, "w") as f:
            f.write(str(self.mLandMessage))

    def doFileSave(self, fn):
        with open(fn, "wb") as f: 
            data = self.mLandMessage.SerializeToString()
            f.write(struct.pack('i', int(time.time())))
            f.write(struct.pack('i', 0))
            f.write(struct.pack('i', len(data)))
            f.write(data)

    def doFileOpen(self, fn):
        with open(fn, "rb") as f:
            f.seek(0x0c)
            data = f.read()
        self.mLandMessage = LandData_pb2.LandMessage()
        self.mLandMessage.ParseFromString(data)

if __name__ == '__main__':
    exit
tsto = TSTO()
while True :
    cmds = raw_input("tsto > ").split()
    cmds_count = len(cmds)
    if cmds_count == 0:
        continue
    try:
        if (cmds[0] == "ia"):
            if cmds_count >= 4:
                tsto.inventoryAdd(cmds[1], int(cmds[2]), int(cmds[3]))
            elif cmds_count == 3:
                tsto.inventoryAdd(cmds[1], int(cmds[2]))
            elif cmds_count == 2:
                tsto.inventoryAdd(cmds[1])
        elif (cmds[0] == "ic"):
            tsto.inventoryCount(int(cmds[1]), int(cmds[2]), int(cmds[3]))
        elif (cmds[0] == "money"):
            tsto.set_money(int(cmds[1]))
        elif (cmds[0] == "spendable"):
            tsto.spendableSet(int(cmds[1]), int(cmds[2]))
        elif (cmds[0] == "qc"):
            tsto.questComplete(int(cmds[1]))
        elif (cmds[0] == "hurry"):
            tsto.hurry()
        elif (cmds[0] == "skins"):
            tsto.skinsSet(cmds[1])
        elif (cmds[0] == "astext"):
            tsto.doSaveAsText()
        elif (cmds[0] == "load"):
            tsto.doFileOpen(cmds[1])
        elif (cmds[0] == "save"):
            tsto.doFileSave(cmds[1])
        elif (cmds[0] == "std"):
            tsto.standard(cmds[1], cmds[2])
        elif (cmds[0] == "download"):
            tsto.doLandDownload()
        elif (cmds[0] == "protocurrency"):
            tsto.doLoadCurrency()
        elif (cmds[0] == "upload"):
            tsto.doLandUpload()
        elif (cmds[0] == "bm"):
            tsto.buildings_move(int(cmds[1]), int(cmds[2]), int(cmds[3]), int(cmds[4]))
        elif (cmds[0] == "uploadextra"):
            tsto.doUploadExtraLandMessage()
        elif (cmds[0] == "resetnotif"):
            tsto.doResetNotifications()
        elif (cmds[0] == "showtimes"):
            tsto.showTimes()
        elif (cmds[0] == "friends"):
            tsto.showFriends()
        elif (cmds[0] == "friendsdrop"):
            if cmds_count >= 2:
                tsto.dropFriends(int(cmds[1]))
            else:
                tsto.dropFriends(90)
        elif (cmds[0] == "donuts"):
            tsto.donutsAdd(int(cmds[1]))
        elif (cmds[0] == "setlevel"):
            tsto.set_level(int(cmds[1]))
        elif (cmds[0] == "login"):
            if cmds_count >= 3:
                tsto.doAuth(cmds[1], cmds[2])
            elif cmds_count == 2:
                tsto.doAuthWithToken(cmds[1])
        elif (cmds[0] == "vs"):
            tsto.varChange(cmds[1], int(cmds[2]))
        elif (cmds[0] == "vars"):
            if cmds_count >= 2:
                tsto.varsPrint(cmds[1])
            else:
                tsto.varsPrint(None)
        elif (cmds[0] == "cleandebris"):
            tsto.cleanDebris()
        elif (cmds[0] == "cleanr"):
            tsto.cleanR()
        elif (cmds[0] == "quit"):
            sys.exit(0)
        elif (cmds[0] == "help"):
            print("""
login email pass     - login origin account
download             - download LandMessage
showtimes            - show some times variables from LandMessage
friends              - show friends info
friendsdrop days=90  - drop friends who not playing more then given amount
resetnotif           - clear neighbor handshakes
protocurrency        - show ProtoCurrency information
upload               - upload current LandMessage to mayhem server
uploadextra          - upload current ExtraLandMessage to mayhem server

load filepath        - load LandMessage from local filepath
save filepath        - save LandMessage to local filepath
astext               - save LandMessage text representation into file

vs name[,name] val   - set variable(s) to value
vars [name[,name]]   - print variables with given names or all
donuts count         - set donuts for logined acc to count
ia ids type count=1  - add item(s) with id and type into inventory
ic id type count     - set count item with id and type
spendable id count   - set count spendable with id
money count          - set money count
skins 1,2,3          - set skins to (see: skinsmasterlist.xml)
setlevel level       - set current level (be careful)
qc id                - complete quest with id
hurry                - done all jobs and rewards
bm id x y flip       - set positions for all buildings with id
cleanr               - clear roads, rivers, broadwalk
cleandebris          - clean debris in subland 1 and 2
std email pass       - execute std routines for acc
help                 - this message
quit                 - exit""")
        else:
            print("WARN: unknown command")
    except Exception as e:
        print(traceback.print_exc())
