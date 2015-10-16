#!/usr/bin/python

"""
TSTO tool.
WARNING: absolutly no warranties. Use this script at own risk.
"""

__author__ = 'jsbot@ya.ru (Oleg Polivets)'

import requests
import json
import gzip
import StringIO
import time
import struct
import sys
import traceback
import random
import LandData_pb2
import os.path
from stat import S_ISREG, ST_CTIME, ST_MODE

URL_SIMPSONS = 'prod.simpsons-ea.com'
URL_OFRIENDS = 'm.friends.dm.origin.com'
URL_AVATAR   = 'm.avatar.dm.origin.com'
URL_TNTAUTH  = 'auth.tnt-ea.com'
URL_TNTNUCLEUS = 'nucleus.tnt-ea.com'
CT_PROTOBUF  = 'application/x-protobuf'
CT_JSON      = 'application/json'
CT_XML       = 'application/xaml+xml'
VERSION_LAND = '32'
VERSION_APP  = '4.17.1'

class TSTO:
    def __init__(self):
        self.dataVerison                   = int(VERSION_LAND)
        self.mLogined                      = False
        self.mLandMessage                  = LandData_pb2.LandMessage()
        self.mExtraLandMessage             = None
        self.headers                       = dict()
        self.headers["Accept"]             = "*/*"
        self.headers["Accept-Encoding"]    = "gzip"
        self.headers["client_version"]     = VERSION_APP
        self.headers["server_api_version"] = "4.0.0"
        self.headers["EA-SELL-ID"]         = "857120"
        self.headers["platform"]           = "android"
        self.headers["os_version"]         = "15.0.0"
        self.headers["hw_model_id"]        = "0 0.0"
        self.headers["data_param_1"]       = "2633815347"
        self.mMhClientVersion              = "Android." + VERSION_APP

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
        if method == "POST":
            r = requests.post(url=url, headers=headers, verify=False, data=body)
        elif method == "GET":
            r = requests.get(url=url, headers=headers, verify=False)
        elif method == "PUT":
            r = requests.put(url=url, headers=headers, verify=False)

        # reading response
        data = r.content

        if (len(data) == 0):
            print("no content")
        else:
            if r.headers['Content-Type'] == 'application/x-protobuf':
                print(r.headers['Content-Type'])
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

    def doAuth(self, args):
        email    = args[1]
        password = args[2]
        data = self.doRequest("POST", CT_JSON, URL_TNTNUCLEUS
            , "/rest/token/%s/%s/" % (email, password))
        data = json.JSONDecoder().decode(data)
        self.mUserId    = data["userId"]
        self.mEncrToken = data["encryptedToken"]
        self.doAuthWithToken(data["token"])

    def doAuthWithCryptedToken(self, cryptedToken):
        data = self.doRequest("POST", CT_JSON, URL_TNTNUCLEUS
            , "/rest/token/%s/" % (cryptedToken))
        data = json.JSONDecoder().decode(data)
        self.mUserId = data["userId"]
        self.mEncrToken = data["encryptedToken"]
        self.doAuthWithToken(data["token"])

    def doAuthWithToken(self, token):
        self.mToken = token
        self.headers["nucleus_token"] = token
        self.headers["AuthToken"] = token

        data = self.doRequest("GET", CT_JSON, URL_TNTAUTH
            , "/rest/oauth/origin/%s/Simpsons-Tapped-Out/" % self.mToken)
        data = json.JSONDecoder().decode(data)
        self.mCode  = data["code"]
        self.mTntId = data["tntId"]
        self.headers["mh_auth_method"]    = "tnt"
        self.headers["mh_auth_params"]    = data["code"]
        self.headers["mh_client_version"] = self.mMhClientVersion

        data = self.doRequest("PUT", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/users?appVer=2.2.0&appLang=en&application=tnt&applicationUserId=%s" % self.mTntId, True)
        urm  = LandData_pb2.UsersResponseMessage()
        urm.ParseFromString(data)
        self.mUid     = urm.user.userId
        self.mSession = urm.token.sessionKey
        self.headers["mh_uid"]         = self.mUid
        self.headers["mh_session_key"] = self.mSession

        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS
                , "/mh/games/bg_gameserver_plugin/checkToken/%s/protoWholeLandToken/" % (self.mUid), True)
        wltr = LandData_pb2.WholeLandTokenRequest()
        if self.protobufParse(wltr, data) == False:
            wltr = LandData_pb2.WholeLandTokenRequest()
            wltr.requestId = self.mTntId
            data = wltr.SerializeToString()
            data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS
                , "/mh/games/bg_gameserver_plugin/protoWholeLandToken/%s/" % self.mUid, True, data)
            wltr = LandData_pb2.WholeLandTokenRequest()
            wltr.ParseFromString(data)
        self.mUpdateToken = wltr.requestId
        self.headers["target_land_id"]    = self.mUid
        self.headers["land-update-token"] = self.mUpdateToken
        self.mLogined = True

    def doLandDownload(self):
        self.checkLogined()
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS
                , "/mh/games/bg_gameserver_plugin/protoland/%s/" % self.mUid, True)
        self.mLandMessage = LandData_pb2.LandMessage()
        self.mLandMessage.ParseFromString(data)
        # make backup
        args=[]
        args.insert(0, "save")
        args.insert(1, "%s.%f" % (self.mUid, time.time()))
        self.doFileSave(args)

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
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/protoland/%s/" % self.mUid, True, data, uncomressedLen)

    def doLoadCurrency(self):
        self.checkLogined()
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS
                , "/mh/games/bg_gameserver_plugin/protocurrency/%s/" % self.mUid, True)
        currdat = LandData_pb2.CurrencyData()
        currdat.ParseFromString(data)
        print(str(currdat))
        return currdat

    def doDownloadFriendsData(self):
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/friendData?debug_mayhem_id=%s" % self.mUid)
        fdresp = LandData_pb2.GetFriendDataResponse()
        fdresp.ParseFromString(data)
        return fdresp

    def doUploadExtraLandMessage(self):
        msg = self.mExtraLandMessage
        if msg == None:
            return
        data = msg.SerializeToString()
        data = self.doRequest("POST", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/extraLandUpdate/%s/protoland/" % self.mUid, True, data)
        self.mExtraLandMessage = None

    def doResetNotifications(self):
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/event/%s/protoland/" % self.mUid, True)
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
        data = self.doRequest("POST", CT_XML, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/usernotificationstatus/?type=reset_count", True)
        data = self.doRequest("POST", CT_XML, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/usernotificationstatus/?type=reset_time", True)

    # show sorted friends list

    def friendsShow(self):
        self.checkLogined()
        friends = self.doDownloadFriendsData()
        fds = []
        for fd in friends.friendData:
            f = fd.friendData
            fds.append("%s|%d|%s|%s|%s" % (
                time.strftime("%Y%m%d%H%M", time.localtime(f.lastPlayedTime)),
                f.level,
                fd.externalId,
                fd.friendId,
                f.name))
        fds.sort()
        print("LASTPLAYTIME | LEVEL | ORIGINID | MYHEMID | NAME")
        for f in fds:
            print(f)

    # drop single Origin friend by its id

    def friendDrop(self, args):
        friendOriginId = int(args[1])
        # resolve myhemId of Origin user
        friendMyhemId = ''
        for fd in self.doDownloadFriendsData().friendData:
            if fd.externalId == friendOriginId:
                friendMyhemId = fd.friendId
                break

        if friendMyhemId == '':
            raise TypeError("ERR: nothing found.")

        # resolve its index in current user land
        friendIdx = -1
        for idx in range(len(self.mLandMessage.friendListData)):
            fld = self.mLandMessage.friendListData[idx]
            if fld.friendID == friendMyhemId:
                friendIdx = idx
                break

        if friendIdx == -1:
            raise TypeError("ERR: not found friendIdx.")

        # delete
        self.doRequest("GET", CT_JSON, URL_OFRIENDS
            , "/friends/deleteFriend?nucleusId=%s&friendId=%s" % (self.mUserId, friendOriginId)
            , True)
        del self.mLandMessage.friendListData[friendIdx]
        self.mLandMessage.innerLandData.numSavedFriends = len(self.mLandMessage.friendListData)

    # drop friends that not playing more given days

    def friendsDropNotActive(self, args):
        days = 90
        if len(args) > 1:
            days = int(args[1])
        self.checkLogined()
        ts = time.mktime(time.localtime())
        crit = (24 * 60 * 60 * days)
        friends = self.doDownloadFriendsData()

#        for key, value in self.headers.items():
#            print (key, value)

#        self.doRequest("GET", CT_JSON, URL_OFRIENDS
#            , "//friends/user/%s/pendingfriends" % (self.mUserId)
#            , True)
#        self.doRequest("GET", CT_JSON, URL_OFRIENDS
#            , "//friends/user/%s/globalgroup/friendIds" % (self.mUserId)
#            , True)
        
        # find what don't need to delete
        notDel=[]
        delAll=False 
        for fd in friends.friendData:
            f = fd.friendData
            if (ts - f.lastPlayedTime) < crit:
                notDel.append(fd.friendId)
                continue
            print("%s|%d|%s|%s|%s" % (
                time.strftime("%Y%m%d%H%M", time.localtime(f.lastPlayedTime)),
                f.level,
                fd.externalId,
                fd.friendId,
                f.name))
            # user is confirmed?
            if delAll == False:
                inp = raw_input("Drop this friend (Y/N/A) ").lower()
                delAll = (inp == 'a')
            if delAll or inp == 'y':
                self.doRequest("GET", CT_JSON, URL_OFRIENDS
                    , "/friends/deleteFriend?nucleusId=%s&friendId=%s" % (self.mUserId, fd.externalId)
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

    def inventoryAdd(self, args):
        itemsid = args[1]
        itemtype = 0
        count = 1
        if len(args) > 2:
            itemtype = int(args[2])
        if len(args) > 3:
            count = int(args[3])

        items = self.arrSplit(itemsid)
        # now add
        for it in items:
            # item exists?
            found = False
            for item in self.mLandMessage.inventoryItemData:
                if item.itemID == it and item.itemType == itemtype:
                    # item found, change its amount
                    found = True
                    args[1] = it
                    args[2] = itemtype
                    args[3] = count
                    self.inventoryCount(args)
                    break
            # already exists? then precess next item
            if found == True:
                continue
            # or add item with given itemid and itemtype
            # into inventory
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

    def inventoryCount(self, args):
        itemid   = int(args[1])
        itemtype = int(args[2])
        count    = int(args[3])
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
                args[1] = str(itemid)
                args[2] = itemtype
                args[3] = count
                self.inventoryAdd(args)

    def donutsAdd(self, args):
        amout = int(args[1])
        elm = self.mExtraLandMessage
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

    def spendablesShow(self):
        self.checkLogined()
        if (len(self.mLandMessage.spendablesData.spendable) == 0):
            raise TypeError("ERR: Download land first.")
        donuts = self.doLoadCurrency()
        print("donuts=%s" % (donuts.vcBalance))
        print("money=%s" % (self.mLandMessage.userData.money))
        for sp in self.mLandMessage.spendablesData.spendable:
            print("%d=%d" % (sp.type, sp.amount))

    def spendableSet(self, args):
        amount   = int(args[2])
        types    = self.arrSplit(args[1])
        notExist = types[:]
        # set amount for exists spendables and
        for sp in self.mLandMessage.spendablesData.spendable:
            if sp.type in types:
                sp.amount = amount
                notExist.remove(sp.type)
        # create not exists spendables
        for sp in notExist:
            sd = self.mLandMessage.spendablesData.spendable.add()
            sd.type   = int(sp)
            sd.amount = amount

    def configShow(self):
        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/games/bg_gameserver_plugin/protoClientConfig"
              "/?id=ca0ddfef-a2c4-4a57-8021-27013137382e")
        cliConf = LandData_pb2.ClientConfigResponse()
        cliConf.ParseFromString(data)

        data = self.doRequest("GET", CT_PROTOBUF, URL_SIMPSONS
            , "/mh/gameplayconfig")
        gameConf = LandData_pb2.GameplayConfigResponse()
        gameConf.ParseFromString(data)

        print("[protoClientConfig]")
        for item in cliConf.items:
            print("%s=%s" % (item.name, item.value))

        print("[gameplayconfig]")
        for item in gameConf.item:
            print("%s=%s" % (item.name, item.value))

    def skinsSet(self, args):
        data = args[1]
        self.mLandMessage.skinUnlocksData.skinUnlock      = data
        self.mLandMessage.skinUnlocksData.skinReceived    = data
        self.mLandMessage.skinUnlocksData.skinUnlockLen   = len(data)
        self.mLandMessage.skinUnlocksData.skinReceivedLen = len(data)

    def skinsAdd(self, args):
        unlocked = self.mLandMessage.skinUnlocksData.skinUnlock
        skins = self.arrSplit(unlocked)
        toAdd = self.arrSplit(args[1])
        for skinId in toAdd:
            if skinId not in skins:
               unlocked += "," + str(skinId)
        args[1] = unlocked
        self.skinsSet(args)

    def buildings_move(self, args):
        building = int(args[1])
        x = int(args[2])
        y = int(args[3])
        flip = int(args[4])

        for b in self.mLandMessage.buildingData:
            if b.building == building:
                b.positionX = x
                b.positionY = y
                b.flipState = flip

    def set_money(self, args):
        amount = int(args[1])
        self.mLandMessage.userData.money = amount

    def set_level(self, args):
        level = int(args[1])
        self.mLandMessage.friendData.level = level
        self.mLandMessage.userData.level = level

    def hurry(self):
        for job in self.mLandMessage.jobData:
            job.state = 2

    def questComplete(self, args):
        quests = tsto.arrSplit(args[1])
        for id in quests:
            # find questData for each quest
            qst = None
            for q in self.mLandMessage.questData:
                if q.questID == id:
                    qst = q
                    break
            # not found?
            if qst == None:
                # then create new one
                qst = self.mLandMessage.questData.add()
                qst.questID = id
                qst.timesCompleted = 0
                qst.header.id = self.mLandMessage.innerLandData.nextInstanceID
                self.mLandMessage.innerLandData.nextInstanceID = qst.header.id + 1
                self.mLandMessage.innerLandData.numQuests      = len(self.mLandMessage.questData)
            qst.questState = 5
            qst.numObjectives = 0
            qst.questScriptState = 0
            qst.timesCompleted += 1
            # delete objective data
            for i in reversed(range(len(qst.objectiveData))):
                del qst.objectiveData[i]

    def questsShow(self):
        print("questState | timesCompleted | numObjectives | questID")
        for q in self.mLandMessage.questData:
            if q.numObjectives > 0:
                print("%s : %s : %s : %s" % (q.questState, q.timesCompleted, q.numObjectives, q.questID))

    def nextPrizeSet(self, args):
        specialEventId = int(args[1])
        nextPrize = int(args[2])
        se = None
        for e in self.mLandMessage.specialEventsData.specialEvent:
            if e.id == specialEventId:
                se = e
                break
        if se == None:
            raise TypeError("ERR: specialEvent with given id not found.")

        se.prizeDataSet.prizeData[0].nextPrize = nextPrize

    def cleanPurchases(self):
        for i in reversed(range(len(self.mLandMessage.purchases))):
            del self.mLandMessage.purchases[i]

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

    def varChange(self, args):
        value = args[2]
        for name in args[1].split(','):
            found = False
            for e in self.mLandMessage.specialEventsData.specialEvent:
                for v in e.variables.variable:
                    if v.name == name:
                        found = True
                        v.value = int(value)
                        break
            if found == False:
                for v in self.mLandMessage.objectVariables.variables.variable:
                    if v.name == name:
                        found = True
                        v.value = str(value)
                        break
            if found == False:
                raise ValueError("ERR: can't found variable with name='%s'" % name)

    def varsPrint(self, args):
        names = None
        if (len(args) > 1):
            names = args[1]
        printAll = names == None
        if printAll == False: ns = names.split(',')
        print("[specialEvent]")
        for e in self.mLandMessage.specialEventsData.specialEvent:
            for v in e.variables.variable:
                if printAll == False and ns.count(v.name) == 0: continue
                print("%s=%s" % (v.name, v.value))
        print("[objectVariables]")
        for v in self.mLandMessage.objectVariables.variables.variable:
            if printAll == False and ns.count(v.name) == 0: continue
            print("%s=%s" % (v.name, v.value))

### Operations with files ###

    def doSaveAsText(self):
        if self.mLandMessage.id == '':
            raise TypeError("ERR: LandMessage.id is empty!!!")
        with open("dbg.%s.txt" % self.mLandMessage.id, "w") as f:
            f.write(str(self.mLandMessage))

    def doFileSave(self, args):
        fn = args[1]
        with open(fn, "wb") as f: 
            data = self.mLandMessage.SerializeToString()
            f.write(struct.pack('i', int(time.time())))
            f.write(struct.pack('i', 0))
            f.write(struct.pack('i', len(data)))
            f.write(data)

    def doFileOpen(self, args):
        fn = args[1]
        with open(fn, "rb") as f:
            f.seek(0x0c)
            data = f.read()
        self.mLandMessage = LandData_pb2.LandMessage()
        self.mLandMessage.ParseFromString(data)

    def tokenPath(self):
        return os.path.join(os.path.expanduser('~'), '.tsto.conf')

    def tokenStore(self):
        self.checkLogined()
        with open(self.tokenPath(), 'w') as f:
            f.write(self.mEncrToken)

    def tokenForget(self):
        os.remove(self.tokenPath())

    def tokenLogin(self):
        encrToken = ''
        with open(self.tokenPath(), 'r') as f:
            encrToken = f.read().replace('\n', '')
        if encrToken != '':
            self.doAuthWithCryptedToken(encrToken)

    def backupsShow(self):
        self.checkLogined()
        begining = self.mUid + '.'
        entries  = (fn for fn in os.listdir('.') if fn.startswith(begining))
        entries  = ((os.stat(path), path) for path in entries)
        entries  = ((stat[ST_CTIME], path) for stat, path in entries if S_ISREG(stat[ST_MODE]))
        for cdate, path in sorted(entries):
            print ("%s | %s" % (time.ctime(cdate), os.path.basename(path)))

    def doQuit(self):
        sys.exit(0)

    def doHelp(self):
        print("""SUPPORTED COMMANDS
login email pass     - login origin account
download             - download LandMessage
showtimes            - show some times variables from LandMessage
friends              - show friends info
friendsdrop days=90  - drop friends who not playing more then given amount
frienddrop ORIGINID  - drop friend by its Origin id
resetnotif           - clear neighbor handshakes
protocurrency        - show ProtoCurrency information
upload               - upload current LandMessage to mayhem server
uploadextra          - upload current ExtraLandMessage to mayhem server
config               - show current game config variables

tokenstore           - store current logined token in home dir
tokenforget          - remove stored encrypted token file
tokenlogin           - login by token stored in file in home dir

load filepath        - load LandMessage from local filepath
save filepath        - save LandMessage to local filepath
astext               - save LandMessage text representation into file

prizeset id number   - set current prize number for specialEvent with given id 
vs name[,name] val   - set variable(s) to value
vars [name[,name]]   - print variables with given names or all
donuts count         - set donuts for logined acc to count
ia ids type count=1  - add item(s) with id and type into inventory
ic id type count     - set count item with id and type
spendable id count   - set count spendable with id
money count          - set money count
ss 1,2,3             - set skins to (see: skinsmasterlist.xml)
sa 60,73             - append skins with ids 60 and 73 into unlocked
setlevel level       - set current level (be careful)
qc id                - complete quest with id
quests               - show not completed quests
hurry                - done all jobs and rewards
bm id x y flip       - set positions for all buildings with id
cleanr               - clear roads, rivers, broadwalk
cleandebris          - clean debris in subland 1 and 2
help                 - this message
quit                 - exit""")

if __name__ == '__main__':
    exit
tsto = TSTO()
cmdwarg = {
    "sa": tsto.skinsAdd,
    "ss": tsto.skinsSet,
    "vs": tsto.varChange,
    "ia": tsto.inventoryAdd,
    "ic": tsto.inventoryCount,
    "qc": tsto.questComplete,
    "bm": tsto.buildings_move,
    "vars": tsto.varsPrint,
    "load": tsto.doFileOpen,
    "save": tsto.doFileSave,
    "login": tsto.doAuth,
    "money": tsto.set_money,
    "donuts": tsto.donutsAdd,
    "setlevel": tsto.set_level,
    "prizeset": tsto.nextPrizeSet,
    "spendable": tsto.spendableSet,
    "frienddrop": tsto.friendDrop,
    "friendsdrop": tsto.friendsDropNotActive,
}
cmds = {
    "quit": tsto.doQuit,
    "help": tsto.doHelp,
    "hurry": tsto.hurry,
    "upload": tsto.doLandUpload,
    "config": tsto.configShow,
    "quests": tsto.questsShow,
    "cleanr": tsto.cleanR,
    "astext": tsto.doSaveAsText,
    "backups": tsto.backupsShow,
    "friends": tsto.friendsShow,
    "download": tsto.doLandDownload,
    "showtimes": tsto.showTimes,
    "resetnotif": tsto.doResetNotifications,
    "spendables": tsto.spendablesShow,
    "tokenlogin": tsto.tokenLogin,
    "tokenstore": tsto.tokenStore,
    "tokenforget": tsto.tokenForget,
    "cleandebris": tsto.cleanDebris,
    "uploadextra": tsto.doUploadExtraLandMessage,
    "protocurrency": tsto.doLoadCurrency,
    "cleanpurchases": tsto.cleanPurchases,
}
while True :
    args = raw_input("tsto > ").split()
    args_count = len(args)
    if args_count == 0:
        continue
    try:
        func = cmds.get(args[0])
        if func is not None:
            func()
        else:
            func = cmdwarg.get(args[0])
            if func is not None:
                func(args)
        if func is None:
            print("ERR: unknown command '%s'.\nMaybe you should try 'help'." % (args[0]))
    except Exception as e:
        print(traceback.print_exc())
