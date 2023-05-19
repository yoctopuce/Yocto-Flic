#!/usr/bin/env python
# -*- coding: utf-8 -*-


#TODO : 0-10V TX
#TODO : 4-20mA TX
#TODO : display message . counter

import sys
pythonVersion = float(sys.version_info[0]) + float(sys.version_info[1])/10
if  pythonVersion  < 3.3:
    print ("This script was launched with Python "+str(pythonVersion)+" , but version 3.3 or more is required.")
    sys.exit()

from http.server import BaseHTTPRequestHandler, HTTPServer

import fliclib
from threading import Thread
from yocto_api import *
from yocto_relay import *
from yocto_buzzer import *
from yocto_servo  import *
from yocto_voltageoutput import *
from yocto_currentloopoutput import *
from yocto_wakeupmonitor import *



import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import os
import urllib
import socket
import hashlib
import datetime




buttonHandler = None
yoctoHandler = None
yoctoConnectionHandler = None
saveAllowed =False
stopPlz = False

# thanks  Jamieson Becker @ stackoverflow
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

serverIP = get_ip()
serverPort = 8081
configfilename = os.path.join( os.path.dirname(os.path.abspath(__file__)),"config.xml")

def quote(str):
    return '"'+str +'"'

def log(line):
    print( str(datetime.datetime.now())[:-3]+" "+line)

class YoctoFunction:

   def __init__ (self,hwid, f,type, isOnline, fname):
      self._hwdid    = hwid
      self._function = f
      self._isOnline = isOnline
      self._type = type
      self._value=0
      self._name = fname
      self.loadFriendlyName()
      self._function.registerValueCallback(self.valueCallback)

   def get_type(self):
      return  self._type

   def valueCallback(self,m,value):
      self._value=value
      log(self._hwdid+" new value "+ self._value)

   def loadFriendlyName(self):
      if  (self._isOnline) :
        try:
          self._name = self._function.get_friendlyName()
        except Exception as e:
          log(self._hwdid+":"+"failed to get Friendly name")

   def getXmlCode(self):
     return "  <YDEVICE hwdid="+quote(self._hwdid)+ " type="+quote(self._type) + " name="+quote(self._name)+"/>\n"

   def get_isOnline(self):
      return self._isOnline

   def set_isOnline(self,online):
       self._isOnline = online
       if online :
            log(self._hwdid+" went online")
       else:
            log(self._hwdid+" went offline")

   def configChanged(self):
       self.loadFriendlyName()


   def getJsonCode(self, extraInfo):
       online = "false"
       if (self._isOnline) : online="true"
       res =   quote(self._hwdid)+': {"hwdID":'+quote(self._hwdid)+',"type":'+quote(self._type)+' ,"name": '+quote(self._name)+',"online":'+online
       if (extraInfo!='') : res=res+","+extraInfo
       res=res+"}"
       return res

   def capabilitiesToJson(data):
       res=""
       for el in data:
           if (res!="") : res=res+","
           res=res+el.toJson()
       return res

   def checkActionValidity(ActionList, action, params):
      for i in  range(0,len(ActionList)):
          a=ActionList[i]

          if action==a.get_id() :
             if len(params)==0  and a.get_params() is None :  return True
             if len(params)>0   and a.get_params() is None :  return False
             if len(params)==len(a.get_params()):  return True
      return False



class YDeviceActionParam:
   def __init__ (self,description,default,unit,help):
      self._description = description
      self._default = default
      self._unit = unit
      self._help = help

   def toJson(self):
      return '{"description":'+quote(self._description)+ ',"default":"'+str(self._default)+'","unit":"'+self._unit+'","help":"'+self._help+'"}'


class YDeviceAction:
    def __init__ (self,id,description,params):
      self._id = id
      self._description = description
      self._params = params

    def get_id(self):
       return self._id

    def get_params(self):
       return self._params

    def  toJson(self):
      res= quote(self._id)+':{"Desc":'+quote(self._description)+',"params":'
      if  self._params is None:
         res=res+"null"
      else:
        res=res+"["
        for i in range(0,len(self._params)):
          if i>0: res=res+','
          res=res+self._params[i].toJson()
        res=res+']'
      res=res+   "}"
      return res
#
#  ************ RELAY SUPPORT
#

class YoctoRelay(YoctoFunction):

   capabilities = []

   def __init__ (self,hwid, type, isOnline,fname):
      log("new  relay "+hwid)
      super(YoctoRelay,self).__init__(hwid,YRelay.FindRelay(hwid),type,isOnline,fname)
      self._type="Relay"

   def  getJsonCode(self):
      return super(YoctoRelay,self).getJsonCode( "")

   def getCapability(self):

      return '"Relay":{"actions":{'+YoctoFunction.capabilitiesToJson(YoctoRelay.capabilities)+'}}'

   def executeAction(self, action, params):
       log("executeAction "+action+"("+str(params)+")")
       if self._function.isOnline():
           try:
            if action=="TOGGLE" : self._function.toggle()
            elif action=="SWITCHA" : self._function.set_state(YRelay.STATE_A)
            elif action=="SWITCHB" : self._function.set_state(YRelay.STATE_B)
            elif action=="PULSE"  and len(params)>=1: self._function.pulse(int(params[0]))
           except  Exception as e :
            log ("Relay action "+action+" failed: "+str(e))
       else:
            log( self._hwdid + "is offline, action canceled")

   @staticmethod
   def staticInit():
       YoctoRelay.capabilities.append(YDeviceAction("TOGGLE","Toggle",None))
       YoctoRelay.capabilities.append(YDeviceAction("SWITCHB","Switch to B",None))
       YoctoRelay.capabilities.append(YDeviceAction("SWITCHA","Switch to A",None))
       YoctoRelay.capabilities.append(YDeviceAction("PULSE","Pulse",[YDeviceActionParam("Duration",2500,"ms","")]))

   def checkActionValidity(targetType, action, params):
       if targetType!="Relay" : return False
       return YoctoFunction.checkActionValidity( YoctoRelay.capabilities,action,params)


#
#  ************ WAKEUP MONITOR SUPPORT
#

class YoctoWakeUpMonitor(YoctoFunction):

   capabilities = []

   def __init__ (self,hwid, type, isOnline,fname):
      log("new  WakeUpMonitor "+hwid)
      super( YoctoWakeUpMonitor,self).__init__(hwid,YWakeUpMonitor.FindWakeUpMonitor(hwid),type,isOnline,fname)
      self._type="WakeUpMonitor"

   def  getJsonCode(self):
      return super(YoctoWakeUpMonitor,self).getJsonCode( "")

   def getCapability(self):

      return '"WakeUpMonitor":{"actions":{'+YoctoFunction.capabilitiesToJson(YoctoWakeUpMonitor.capabilities)+'}}'

   def executeAction(self, action, params):
       log("executeAction "+action+"("+str(params)+")")
       if self._function.isOnline():
           try:
            if action=="SLEEP" : self._function.sleep(1)
            elif action=="SLEEPFOR"   and len(params)>=1: self._function.sleepFor(int(params[0]))

           except  Exception as e :
            log ("WakeUpMonitor action "+action+" failed: "+str(e))
       else:
            log( self._hwdid + "is offline, action canceled")

   @staticmethod
   def staticInit():
       YoctoWakeUpMonitor.capabilities.append(YDeviceAction("SLEEP","Sleep",None))
       YoctoWakeUpMonitor.capabilities.append(YDeviceAction("SLEEPFOR","Sleep for",[YDeviceActionParam("Duration",3600,"s","")]))


   def checkActionValidity(targetType, action, params):
       if targetType!="WakeUpMonitor" : return False
       return YoctoFunction.checkActionValidity( YoctoWakeUpMonitor.capabilities,action,params)


#
#  ************ BUZZER SUPPORT
#

class YoctoBuzzer(YoctoFunction):

    capabilities = []

    def __init__ (self,hwid, type, isOnline,fname):
        log("new  buzzer  "+hwid)
        super(YoctoBuzzer,self).__init__(hwid,YBuzzer.FindBuzzer(hwid),type,isOnline,fname)
        self._type="Buzzer"

    def  getJsonCode(self):
        return super(YoctoBuzzer,self).getJsonCode( "")

    def getCapability(self):
        return '"Buzzer":{"actions":{'+YoctoFunction.capabilitiesToJson(YoctoBuzzer.capabilities)+'}}'

    def executeAction(self, action, params):
        log("executeAction "+action+"("+str(params)+")")
        if self._function.isOnline():
            try:
              if action=="PLAY"  and len(params)>=1: self._function.playNotes(params[0])
              elif action=="PULSE"  and len(params)>=2: self._function.pulse(params[0],params[1])
            except  Exception as e :
              log ("Buzzer action "+action+" failed: "+str(e))
        else:
            log( self._hwdid + "is offline, action canceled")

    @staticmethod
    def staticInit():
        YoctoBuzzer.capabilities.append(YDeviceAction("PULSE","Pulse",[YDeviceActionParam("Frequence",1000,"Hz",""),YDeviceActionParam("Duration",1500,"ms",""),  ]))
        YoctoBuzzer.capabilities.append(YDeviceAction("PLAY","Play tune",[YDeviceActionParam("Notes","200% D8! C! D! A! F! A! ,D4! ","","Tune to play, more info about syntax on <a href='http://http://www.yoctopuce.com/EN/article/fancy-ringtones-for-the-yocto-buzzer'>Yoctopuce web site</a>.")]))

    def checkActionValidity(targetType, action, params):
        if targetType!="Buzzer" : return False
        return YoctoFunction.checkActionValidity( YoctoBuzzer.capabilities,action,params)





#
#  ************ SERVO SUPPORT
#

class YoctoServo(YoctoFunction):

    capabilities = []

    def __init__ (self,hwid, type, isOnline,fname):
        log("new  servo  "+hwid)
        super(YoctoServo,self).__init__(hwid,YServo.FindServo(hwid),type,isOnline,fname)
        self._type="Servo"

    def  getJsonCode(self):
        return super(YoctoServo,self).getJsonCode( "")

    def getCapability(self):
        return '"Servo":{"actions":{'+YoctoFunction.capabilitiesToJson(YoctoServo.capabilities)+'}}'

    def executeAction(self, action, params):
        log("execute Action "+action+"("+str(params)+")")
        currentpos = float(self._value)
        if self._function.isOnline():
            try:
                if action == "TOGGLE" and len(params)>=3:
                    pos1  = min (max(-1000, float(params[0])),1000)
                    pos2  = min (max(-1000, float(params[1])),1000)
                    if pos1>pos2 : pos1, pos2 = pos2, pos1  # python trick to  swap 2 variables
                    middle = (pos1+pos2) /2
                    targetPos = pos2
                    if currentpos>middle : targetPos = pos1
                    speed = max(float(params[2]),0.1)
                    time =  (100/speed)*1000*(abs(currentpos-targetPos)/2000)

                    self._function.move(targetPos, time)
                if action=="MOVE"  and len(params)>=2:
                    targetPos = min (max(-1000, float(params[0])),1000)
                    speed = max(float(params[1]),0.1)
                    time =  (100/speed)*1000*(abs(currentpos-targetPos)/2000)
                    self._function.move(targetPos, time)

            except  Exception as e :
                log ("Servo action "+action+" failed: "+str(e))
        else:
            log( self._hwdid + "is offline, action canceled")

    @staticmethod
    def staticInit():
        YoctoServo.capabilities.append(YDeviceAction("MOVE","Move",[YDeviceActionParam("Position",1000,"",""),YDeviceActionParam("Speed",100,"%/s",""),  ]))
        YoctoServo.capabilities.append(YDeviceAction("TOGGLE","Toggle",[YDeviceActionParam("Position 1",-1000,"",""),YDeviceActionParam("Position 2",1000,"",""),YDeviceActionParam("Speed",100,"%/s","The servo will toggle between position 1 & 2 at specified speed"),  ]))

    def checkActionValidity(targetType, action, params):
        if targetType!="Servo" : return False
        return YoctoFunction.checkActionValidity( YoctoServo.capabilities,action,params)

#
#  ************ VOLTAGEOUPUT SUPPORT
#

class YoctoVoltageOutput(YoctoFunction):

    capabilities = []

    def __init__ (self,hwid, type, isOnline,fname):
        log("new  VoltageOutput  "+hwid)
        super(YoctoVoltageOutput,self).__init__(hwid,YVoltageOutput.FindVoltageOutput(hwid),type,isOnline,fname)
        self._type="VoltageOutput"

    def  getJsonCode(self):
        return super(YoctoVoltageOutput,self).getJsonCode( "")

    def getCapability(self):
        return '"VoltageOutput":{"actions":{'+YoctoFunction.capabilitiesToJson(YoctoVoltageOutput.capabilities)+'}}'

    def executeAction(self, action, params):
        log("execute Action "+action+"("+str(params)+")")
        currentpos = float(self._value)
        if self._function.isOnline():
            try:
                if action == "TOGGLE" and len(params)>=3:
                    pos1  = min (max(0, float(params[0])),10)
                    pos2  = min (max(0, float(params[1])),10)
                    if pos1>pos2 : pos1, pos2 = pos2, pos1  # python trick to  swap 2 variables
                    middle = (pos1+pos2) /2
                    targetPos = pos2
                    if currentpos>middle : targetPos = pos1
                    speed = max(float(params[2]),0.1)
                    time =  (100/speed)*1000*(abs(currentpos-targetPos)/10)
                    self._function.voltageMove(targetPos, time)
                if action=="MOVE"  and len(params)>=2:
                    targetPos = min (max(0, float(params[0])),10)
                    speed = max(float(params[1]),0.1)
                    time =  (100/speed)*1000*(abs(currentpos-targetPos)/10)
                    self._function.voltageMove(targetPos, time)

            except  Exception as e :
                log ("VoltageOutput action "+action+" failed: "+str(e))
        else:
            log( self._hwdid + "is offline, action canceled")

    @staticmethod
    def staticInit():
        YoctoVoltageOutput.capabilities.append(YDeviceAction("MOVE","Move",[YDeviceActionParam("Position",10,"V",""),YDeviceActionParam("Speed",100,"%/s",""),  ]))
        YoctoVoltageOutput.capabilities.append(YDeviceAction("TOGGLE","Toggle",[YDeviceActionParam("Position 1",0,"V",""),YDeviceActionParam("Position 2",10,"V",""),YDeviceActionParam("Speed",100,"%/s","The voltage output will toggle between position 1 & 2 at specified speed"),  ]))

    def checkActionValidity(targetType, action, params):
        if targetType!="VoltageOutput" : return False
        return YoctoFunction.checkActionValidity( YoctoVoltageOutput.capabilities,action,params)

#
#  ************ CURRENTLOOPOUTPUT SUPPORT
#

class YoctoCurrentLoopOutput(YoctoFunction):

    capabilities = []

    def __init__ (self,hwid, type, isOnline,fname):
        log("new  CurrentLoopOutput  "+hwid)
        super(YoctoCurrentLoopOutput,self).__init__(hwid,YCurrentLoopOutput.FindCurrentLoopOutput(hwid),type,isOnline,fname)
        self._type="CurrentLoopOutput"

    def  getJsonCode(self):
        return super(YoctoCurrentLoopOutput,self).getJsonCode( "")

    def getCapability(self):
        return '"CurrentLoopOutput":{"actions":{'+YoctoFunction.capabilitiesToJson(YoctoCurrentLoopOutput.capabilities)+'}}'

    def executeAction(self, action, params):
        log("execute Action "+action+"("+str(params)+")")
        currentpos = float(self._value)
        if self._function.isOnline():
            try:
                if action == "TOGGLE" and len(params)>=3:
                    pos1  = min (max(4, float(params[0])),20)
                    pos2  = min (max(4, float(params[1])),20)
                    if pos1>pos2 : pos1, pos2 = pos2, pos1  # python trick to  swap 2 variables
                    middle = (pos1+pos2) /2
                    targetPos = pos2
                    if currentpos>middle : targetPos = pos1
                    speed = max(float(params[2]),0.1)
                    time =  (100/speed)*1000*(abs(currentpos-targetPos)/16)
                    self._function.currentMove(targetPos, time)
                if action=="MOVE"  and len(params)>=2:
                    targetPos = min (max(4, float(params[0])),20)
                    speed = max(float(params[1]),0.1)
                    time =  (100/speed)*1000*(abs(currentpos-targetPos)/16)
                    self._function.currentMove(targetPos, time)

            except  Exception as e :
                log ("CurrentLoopOutput action "+action+" failed: "+str(e))
        else:
            log( self._hwdid + "is offline, action canceled")

    @staticmethod
    def staticInit():
        YoctoCurrentLoopOutput.capabilities.append(YDeviceAction("MOVE","Move",[YDeviceActionParam("Position",20,"mA",""),YDeviceActionParam("Speed",100,"%/s",""),  ]))
        YoctoCurrentLoopOutput.capabilities.append(YDeviceAction("TOGGLE","Toggle",[YDeviceActionParam("Position 1",4,"mA",""),YDeviceActionParam("Position 2",20,"mA",""),YDeviceActionParam("Speed",100,"%/s","The loop current will toggle between position 1 & 2 at specified speed"),  ]))

    def checkActionValidity(targetType, action, params):
        if targetType!="CurrentLoopOutput" : return False
        return YoctoFunction.checkActionValidity( YoctoCurrentLoopOutput.capabilities,action,params)

def pouet(m):
    log("pouet")

class  YoctoDevicesHandler:

   def __init__(self):
      self._flist= {}
      YAPI.InitAPI(YAPI.Y_DETECT_NONE)
      YAPI.RegisterDeviceArrivalCallback(self.deviceArrival)
      YAPI.RegisterDeviceRemovalCallback(self.deviceRemoval)

   def start(self):
      thread = Thread(target = self.yocto_bg_thread,args=())
      thread.start()

   def getXmlCode(self):
     res= "<YDEVICES>\n"
     for d in self._flist:
         res=res+self._flist[d].getXmlCode()
     res = res + "</YDEVICES>\n"
     return res

   def initFromXml(self,xmlNode):
      for node in xmlNode:
         if (node.tag=="YDEVICE")  and ("hwdid" in node.attrib.keys())  and ("type" in node.attrib.keys())  and ("name" in node.attrib.keys()):
          hwdid  = node.attrib["hwdid"]
          type  = node.attrib["type"]
          name  = node.attrib["name"]

          if not(hwdid in self._flist.keys()):
               #log("loading "+hwdid+" from xml file ")
               if  type == "Relay" :  self._flist[hwdid] = YoctoRelay(hwdid,type,False,name)
               if  type == "Buzzer" :  self._flist[hwdid] = YoctoBuzzer(hwdid,type,False,name)
               if  type == "Servo" :  self._flist[hwdid] = YoctoServo(hwdid,type,False,name)
               if  type == "VoltageOutput" :  self._flist[hwdid] = YoctoVoltageOutput(hwdid,type,False,name)
               if  type == "CurrentLoopOutput" :  self._flist[hwdid] = YoctoCurrentLoopOutput(hwdid,type,False,name)
               if  type == "WakeUpMonitor" :  self._flist[hwdid] = YoctoWakeUpMonitor(hwdid,type,False,name)


   def yocto_bg_thread(self):
    global stopPlz
    log('starting Yoctopuce background thread')
    while not(stopPlz):
        try:
          YAPI.Sleep(2000)
          YAPI.UpdateDeviceList()
        except Exception as e:
          log("Background loop error : "+str(e))
    log('stopping Yoctopuce background thread')

   def deviceArrival(self,m):
      global yoctoConnectionHandler
      mustsave =False
      yoctoConnectionHandler.deviceArrival(m)
      log("arrival "+m.get_serialNumber())
      for i in range(0,m.functionCount()):
         type=  m.functionType(i)
         id = m.get_serialNumber()+"."+m.functionId(i)
         if not(id in self._flist.keys()):
            if  type == "Relay" :
                self._flist[id] = YoctoRelay(id,type,True,"")
                mustsave =True
            if  type == "Buzzer" :
                self._flist[id] = YoctoBuzzer(id,type,True,"")
                mustsave =True
            if  type == "Servo" :
                self._flist[id] = YoctoServo(id,type,True,"")
                mustsave =True
            if  type == "VoltageOutput" :
                self._flist[id] = YoctoVoltageOutput(id,type,True,"")
                mustsave =True
            if  type == "CurrentLoopOutput" :
                self._flist[id] = YoctoCurrentLoopOutput(id,type,True,"")
                mustsave =True
            if type == "WakeUpMonitor":
                self._flist[id] = YoctoWakeUpMonitor(id, type, True, "")
                mustsave = True
         else:
            self._flist[id].set_isOnline(True)
            m.registerConfigChangeCallback(self.deviceConfigChange)
            m.triggerConfigChangeCallback()

         if mustsave :
            saveConfig()
            m.registerConfigChangeCallback(self.deviceConfigChange)


   def deviceRemoval(self,m):
       global yoctoConnectionHandler

       yoctoConnectionHandler.deviceRemoval(m)
       log("removal "+m.get_serialNumber())
       serial = m.get_serialNumber()
       for  key in  self._flist:
           if (key[:len(serial)] == serial):
               self._flist[key].set_isOnline(False)

   def deviceConfigChange(self,m):
       log("Config change for "+m.get_serialNumber())
       serial = m.get_serialNumber()
       for  key in  self._flist:
          if (key[:len(serial)] == serial):
              self._flist[key].configChanged()

   def removeDevice(self,hwid):
       global buttonHandler

       if hwid in self._flist.keys():
          buttonHandler.ydeviceRemoved(hwid)
          self._flist.pop(hwid)
          saveConfig()

   def executeAction(self,hwdid,action,param):
        if hwdid in self._flist.keys() :
             self._flist[hwdid].executeAction(action,param)

   def getList(self):
      res=  ""
      for  key in  self._flist:
        if res != "": res= res  + ","
        res= res + self._flist[key].getJsonCode()
      return '"ydevices":{'+res+"}"

   def get_device(self,id):
       if (id in  self._flist.keys()): return self._flist[id]
       return None

   def getDevicesCapabilities(self):
       return '"capabilities":{' +YoctoRelay.getCapability()\
                                 +","+YoctoBuzzer.getCapability()\
                                 +","+YoctoServo.getCapability()\
                                 +","+YoctoVoltageOutput.getCapability()\
                                 +","+YoctoCurrentLoopOutput.getCapability() \
                                 +","+YoctoWakeUpMonitor.getCapability() \
                                 +"}"

   def checkActionValidity(target, action, params):
     global yoctoHandler
     dev = yoctoHandler. get_device(target)
     if dev is None :
         log("unknown action target "+target)
         return False

     targetType = dev.get_type()

     if YoctoRelay.checkActionValidity(targetType, action, params) : return True
     if YoctoBuzzer.checkActionValidity(targetType, action, params) : return True
     if YoctoServo.checkActionValidity(targetType, action, params) : return True
     if YoctoVoltageOutput.checkActionValidity(targetType, action, params) : return True
     if YoctoCurrentLoopOutput.checkActionValidity(targetType, action, params) : return True
     if YoctoWakeUpMonitor.checkActionValidity(targetType, action, params): return True
     return False


#
#  flic button stuff
#

class FlicButtonAction:
    def __init__(self, actionType , targetHwdId, actionId, ActionParams):
        self._actionType   = actionType
        self._targetHwdId  = targetHwdId
        self._actionId     = actionId
        self._actionParams  = ActionParams


    def justDoIt(self):
         global yoctoHandler
         try:
           yoctoHandler.executeAction (self._targetHwdId,self._actionId, self._actionParams)
         except Exception as e:
           log("action "+self._actionId+" on "+self._targetHwdId+" failed ("+str(e)+")" )

    def  initFromXml(self,xmlNode):
        if ("type" in xmlNode.attrib.keys()) :    self._actionType = xmlNode.attrib["type"]
        if ("id" in xmlNode.attrib.keys()) :      self._actionId = xmlNode.attrib["id"]
        if ("target" in xmlNode.attrib.keys()) :  self._targetHwdId = xmlNode.attrib["target"]
        self._actionParams = None
        for node in xmlNode:
           if (node.tag=="PARAM"):
              if ("value" in node.attrib.keys()):
                if  self._actionParams is None :
                   self._actionParams = [ node.attrib["value" ] ]
                else:
                   self._actionParams.append( node.attrib["value" ] )


    def get_type(self): return self._actionType
    def get_target(self): return self._targetHwdId
    def get_actionId(self): return self._actionId
    def get_actionParams(self): return self._actionParams
    def  getXmlCode(self):
         res = '  <ACTION type='+quote(self._actionType)+' id='+ quote(self._actionId)\
                +' target='+quote(self._targetHwdId)+ '>\n'
         if not self._actionParams is None:
             for i in range(0,len(self._actionParams)):
                res=res+"        <PARAM value="+quote(self._actionParams[i])+"/>\n"
         res=res+"    </ACTION>\n"
         return res



    def getJson(self):
         paramLine = "null"
         if not self._actionParams is None:
             paramLine = "["
             for i in range (0,len(self._actionParams)):
                 if i>0 :  paramLine=paramLine+","
                 paramLine=paramLine+quote(str(self._actionParams[i]))
             paramLine = paramLine +"]"

         return '{"id":'+quote(self._actionId)+','\
                +'"target":'+quote(self._targetHwdId)+',"param":'+paramLine+'}'

class  FlicButton:
    _buttoncount = 0

    def __init__(self, handler, id, online):
       self._buttonid = id
       self._description = ""
       self._color = ""
       self.UUID = ""
       self._online=online
       self._handler = handler
       self._lastUsed = 0
       self._onclick     = None
       self._ondblclick  = None
       self._onhold = None
       self._battery = -1;
       FlicButton._buttoncount=FlicButton._buttoncount+1
       if (self._online):
           self._description= self._handler.newUniqueName()
           self.connect()

    def ydeviceRemoved(self,hwid):
       if not(self._onclick is None) and (self._onclick.get_target()==hwid) : self._onclick=None
       if not(self._ondblclick is None) and (self._ondblclick.get_target()==hwid) : self._ondblclick=None
       if not(self._onhold is None) and (self._onhold.get_target()==hwid) : self._onhold=None

    def buttonUpOrDown(self,channel, click_type, was_queued, time_diff):
       #log(channel.bd_addr + " " + str(click_type) + " " + str(time_diff))
       if click_type ==  fliclib.ClickType.ButtonSingleClick: self.click()
       elif click_type ==  fliclib.ClickType.ButtonDoubleClick :self.dblclick()
       elif  click_type ==  fliclib.ClickType.ButtonHold : self.hold()

    def get_description(self):
       return self._description;

    def click(self):
        self._lastUsed = time.time()
        if not(self._onclick is None) :  self._onclick.justDoIt()

    def dblclick(self):
        self._lastUsed = time.time()
        if not(self._ondblclick is None) :  self._ondblclick.justDoIt()

    def hold(self):
        self._lastUsed = time.time()
        if not(self._onhold is None) :  self._onhold.justDoIt()

    def setDescription(self,description):
      self._description = description

    def setAction(self,action):
      type = action.get_type()
      if type=="onclick" : self._onclick = action
      if type=="ondblclick" : self._ondblclick = action
      if type=="onhold" : self._onhold = action

    def connectionStatusChanged(self,channel, connection_status, disconnect_reason):
       log("zz"+channel.bd_addr + " " + str(connection_status) + (" " + str(disconnect_reason) if connection_status == fliclib.ConnectionStatus.Disconnected else ""))

    def batteryMessage(self, bd_addr, battery_percentage, timestamp):
       log(self._buttonid + " battery level is "+str(battery_percentage))
       self._battery = battery_percentage;

    def connect(self):
       if self._color=="": self.get_button_color()
       cc = fliclib.ButtonConnectionChannel(self._buttonid)
       cc.on_button_single_or_double_click_or_hold = lambda channel, click_type, was_queued, time_diff :\
                                    self.buttonUpOrDown(channel, click_type, was_queued, time_diff)
       cc.on_connection_status_changed =  lambda channel, connection_status, disconnect_reason:\
                                  self.connectionStatusChanged(channel, connection_status, disconnect_reason)
       self._handler.get_client().add_connection_channel(cc)
       listener = fliclib.BatteryStatusListener(self._buttonid)
       listener.on_battery_status = lambda  bd_addr, battery_percentage, timestamp:\
           self.batteryMessage( bd_addr, battery_percentage, timestamp)
       self._handler.get_client().add_battery_status_listener(listener)

    def configure(self,name, onclickAction  ):
       self._description=name
       self._onclick = onclickAction

    def setOnlinestate(self,online):
       if online and not(self._online): self.connect()
       self._online=online

    def isOnline(self):
       return  self._online

    def get_button_color(self):
       self._handler.get_button_extrainfo(self._buttonid,   lambda bd_addr, uuid , color , serial_number, flic_version,firmware_version: self.buttoninfo_received (bd_addr, uuid , color,serial_number, flic_version,firmware_version))

    def buttoninfo_received( self, bd_addr, uuid , color,serial_number, flic_version,firmware_version):
       #log("bd_addr = "+bd_addr)
       #log("uuid = "+uuid)
       #log( color)
       if color is None :
           log(bd_addr+"'s color is unknown, using white instead")
           self._color = "white"
           return
       self._color = color
       self.UUID = uuid

    def  getHTMLCode(self):
      return str(self._buttonid)+" <a href='?action=delete&id="+str(self._buttonid)+"'>delete</a><br>"

    def  getJsonCode(self):
      res= quote(self._buttonid) + ':{"ID":'+ quote(self._buttonid) \
                                 +',"Description":' +  quote(self._description)\
                                 +',"Color":'+quote(self._color)\
                                 +',"Battery":'+quote(str(self._battery))\
                                 +',"recentlyUsed":'
      if time.time()-self._lastUsed<2:
          res=res+"true"
      else:
          res=res+"false"


      if not (self._onclick is None): res=res +',"onclick":'+self._onclick.getJson()
      if not (self._ondblclick is None): res=res +',"ondblclick":'+self._ondblclick.getJson()
      if not (self._onhold is None): res=res +',"onhold":'+self._onhold.getJson()


      res=res+"}"
      return res;

    def initFromXml(self,xmlNode):
        if ("name" in xmlNode.attrib.keys())    :  self._description = xmlNode.attrib["name"]
        if ("color" in xmlNode.attrib.keys())   :  self._color = xmlNode.attrib["color"]
        if ("battery" in xmlNode.attrib.keys()) :  self._battery = xmlNode.attrib["battery"]
        for node in xmlNode:
          if (node.tag=="ACTIONS"):
            for subnode in node:
               if (subnode.tag=="ACTION") :
                    action = FlicButtonAction(None,None,None,None)
                    action.initFromXml(subnode)
                    if (action.get_type()=="onclick") : self._onclick = action
                    if (action.get_type()=="ondblclick") : self._ondblclick = action
                    if (action.get_type()=="onhold") : self._onhold = action

    def getXMLcode(self):
        res =  "<BUTTON id="+quote(self._buttonid)
        res=res+" name="+quote(self._description)+" color="+quote(self._color)+" battery="+quote(str(self._battery))+">\n"
        res=res+"    <ACTIONS>\n"
        if  not(self._onclick is  None)    :  res=res+"    "+self._onclick.getXmlCode();
        if  not(self._ondblclick is  None) :  res=res+"    "+self._ondblclick.getXmlCode();
        if  not(self._onhold is  None)     :  res=res+"    "+self._onhold.getXmlCode();
        res=res+"    </ACTIONS>\n  </BUTTON>\n"
        return res

class  FlicButtons:

   def __init__(self):
     global stopPlz;
     self._client =  None
     self._ButtonsList = {}
     self._scanner = None
     self._scanning=False
     self._scantimestamp=0

     self._scanLastmessage = ""
     self._scanLastmessageTimestamp = 0

     try:
       self._client = fliclib.FlicClient("localhost")
     except Exception as e:
       log("Cannot connect to localhost Flic server ("+str(e)+"). Make sure that the flick SDK (github.com/50ButtonsEach/fliclib-linux-hci) is up and running on local computer.")
       stopPlz =True
       sys.exit(-1)

   def newUniqueName(self):
     n=1; name = "Button "+str(n)
     found=True
     while found:
        found =False
        for id in self._ButtonsList:
           if  self._ButtonsList[id].get_description() == name : found =True
        if  found :
           n=n+1
           name = "Button "+str(n)
     return name

   def get_client(self):
      return   self._client

   def ydeviceRemoved(self,hwid):
     for id in self._ButtonsList:
          self._ButtonsList[id].ydeviceRemoved(hwid)

   def click(self,id):
      if id in self._ButtonsList.keys(): self._ButtonsList[id].click()

   def dblclick(self,id):
      if id in self._ButtonsList.keys(): self._ButtonsList[id].dblclick()

   def hold(self,id):
      if id in self._ButtonsList.keys(): self._ButtonsList[id].hold()

   def start(self):
     thread = Thread(target=self.flic_bg_thread,args=())
     thread.start()
     self.get_info()

   def scan_status(self):
      scan ="false"
      if self._scanning: scan ="true";
      res =  '"scan":{"Running":'+scan+',"LastMessage":'+ quote(self._scanLastmessage) + ',"stillActive": '
      if  time.time()-self._scanLastmessageTimestamp<3:
          res=res+"true"
      else:
          res=res+"false"
      return res+"}"

   def  flic_bg_thread(self):
    log('starting flic background thread')
    self._client.handle_events()

   def get_button_extrainfo(self,id,callback):
     #log("looking up for more info about button "+id)
     self._client.get_button_info(id,callback)

   def infoCallBack(self,info):

     idlist = info['bd_addr_of_verified_buttons']
     log( str(len(self._ButtonsList))+" button total" )
     for id in idlist:
        if not(id in self._ButtonsList.keys()):
           log ("new button "+id)
           self._ButtonsList[id]= FlicButton(self,id,True)

        else:
           log ("Button "+id+ " is registered")
           self._ButtonsList[id].setOnlinestate(True)

   def get_info(self):
       self._client.get_info(self.infoCallBack)

   def deleteButton(self,id):
     log("deleting button "+str(id))
     if not (id in self._ButtonsList.keys()):
          log("delete: invalid button"+str(id))
          return
     self._client.delete_button(id)
     self._ButtonsList[id].setOnlinestate(False)
     self.get_info()

   def ConfigureButton(self,id,name,onclick):
     if not (id in self._ButtonsList.keys()):
       log("configure: invalid button"+str(id))
       return
     self._ButtonsList[id].configure(name,onclick)
     saveConfig()

   def setDescription(self,id,description):
    if not (id in self._ButtonsList.keys()):
       log("configure: invalid button"+str(id))
       return
    self._ButtonsList[id].setDescription(description)
    saveConfig()

   def setAction(self,id,action):
    if not (id in self._ButtonsList.keys()):
       log("configure: invalid button"+str(id))
       return
    self._ButtonsList[id].setAction(action)
    saveConfig()

   def getList(self):
     res=  ""
     for  key in  self._ButtonsList:
         if self._ButtonsList[key].isOnline():
           if res != "": res= res  + ","
           res= res + self._ButtonsList[key].getJsonCode()
     return '"buttons":{'+res+"}"

   def initFromXml(self,xmlNode):
      for node in xmlNode:
         if (node.tag=="BUTTON")  and ("id" in node.attrib.keys()):
          id  = node.attrib["id"]
          if not(id in self._ButtonsList.keys()):
            bt = FlicButton( self,id,False )
            bt.initFromXml(node)
            self._ButtonsList[id]=bt

   def getXmlCode(self):
     res=  "<BUTTONS>\n"
     for  key in  self._ButtonsList:
        res=res+"  "+self._ButtonsList[key].getXMLcode()
     res= res+ "</BUTTONS>\n"
     return res

   def done(self,bd_addr):
       self._scanLastmessage = "Button " + bd_addr + " was successfully added!"
       log(self._scanLastmessage)
       buttonHandler.get_info()
       self._scanning=False

   def on_adv_packet(self, scanner, bd_addr, name, rssi, is_private, already_verified,already_connected_to_this_device, already_connected_to_other_device ):
       #log(" *** SCAN ADV  PACKET")
       if already_verified:
          return
       if is_private:

           if ((time.time()-self._scantimestamp)>30):
              log("timeout")
              self._scanLastmessage="Scan timeout"
              self._scanLastmessageTimestamp = time.time()
              self._client.remove_scanner(scanner)
              self._scanning=False
              return

           msg = "Button " + bd_addr + " is currently private. Hold it down for 7 seconds to make it public."
           if msg != self._scanLastmessage:
              self._scanLastmessage=msg
              self._scanLastmessageTimestamp = time.time()
              log("++"+self._scanLastmessage)
           return
       log("Found public button " + bd_addr + ", now connecting...")
       self._scanLastmessage="Button registered"
       self._scanLastmessageTimestamp = time.time()
       self._client.remove_scanner(scanner)
       #log(" *** SCAN COMPLETED")
       self._scanning=False

       def restart_scan():
            #log(" *** SCAN RESTART")
            self._client.add_scanner(scanner)

       def timeout(channel):
            self._client.remove_connection_channel(channel)
            self._client.remove_scanner(scanner)
            self._scanLastmessage="Scan timeout"
            self._scanLastmessageTimestamp = time.time();
            #log(" *** SCAN TIMEOUT")
            log("--"+self._scanLastmessage)
            self._scanning=False

       def on_create(channel, error, connection_status):
            #log(" *** SCAN RESTART")
            if connection_status == fliclib.ConnectionStatus.Ready:
                self.done(bd_addr)
                self._client.remove_connection_channel(channel)
                self._scanLastmessage="Completed"
                self._scanLastmessageTimestamp = time.time();
                self._scanning=False

            elif error != fliclib.CreateConnectionChannelError.NoError:
                self._scanLastmessage="Failed: " + str(error)
                self._scanLastmessageTimestamp = time.time();
                log("**"+self._scanLastmessage)

                restart_scan()
            else:
                self._client.set_timer(30 * 1000, lambda: timeout(channel))

       def on_removed(channel, removed_reason):
           #log(" *** SCAN REMOVED")
           self._scanLastmessage="Failed: " + str(removed_reason)
           self._scanLastmessageTimestamp = time.time();
           log(self._scanLastmessage)
           restart_scan()

       def on_connection_status_changed(channel, connection_status, disconnect_reason):
           #log(" *** SCAN STATUS CHANGED")
           if connection_status == fliclib.ConnectionStatus.Ready:  self.done(bd_addr)

       channel = fliclib.ButtonConnectionChannel(bd_addr)
       channel.auto_disconnect_time = 15;
       channel.on_create_connection_channel_response = on_create
       channel.on_removed =on_removed
       channel.on_connection_status_changed = on_connection_status_changed
       self._client.add_connection_channel(channel)

   def startScan(self):
      if self._scanning:
          log("Scanning is already running")
          return
      log("SCAN start button scan...")
      self._scanning=True
      self._scantimestamp=time.time()
      self._scanLastmessage="Scanning.. press on the new button you want to add"
      self._scanLastmessageTimestamp = time.time();
      scanner = fliclib.ButtonScanner()
      scanner.on_advertisement_packet = self.on_adv_packet
      self._client.add_scanner(scanner)

# HTTPRequestHandler class
class testHTTPServer_RequestHandler(BaseHTTPRequestHandler):

    def get_basehtml(self):
        with open('index.html', 'r') as myfile:
            return myfile.read()

    def updateCode(self,checksum):
        global buttonHandler
        global yoctoHandler
        global yoctoConnectionHandler
        l =     yoctoConnectionHandler.get_list()+','\
               +yoctoHandler.getList() +", "\
               +yoctoHandler.getDevicesCapabilities()+","\
               +buttonHandler.getList()+ ","\
               +buttonHandler.scan_status()


        m = hashlib.md5()
        m.update(l.encode('utf-8'))
        hex= m.hexdigest();
        signature = '"checksum":"'+ hex+'"'

       #  print("\n\nchecksum="+hex+" data="+l);

        if checksum==hex:
            l=signature
        else:
            l=signature+","+l;


        return "<!DOCTYPE html><HTML><meta charset='UTF-8'><BODY><tt>"+l+"</tt>\n<SCRIPT>\nwindow.parent.update({" +l+"});</SCRIPT></BODY></HTML>"

    def process_cmd(self,urlParameters):
        global buttonHandler
        global yoctoConnectionHandler
        global yoctoHandler
        checksum="";

        if "checksum" in urlParameters.keys():
            checksum =  urlParameters['checksum'];


        if "action" in urlParameters.keys():
            #log ("Action="+urlParameters['action'])

            if urlParameters['action'] =="deleteDevice" :
                id = urllib.parse.unquote(urlParameters['id'])
                yoctoHandler.removeDevice(id)
                return self.updateCode(checksum)
            if urlParameters['action'] =="fullrefresh" :
                return self.updateCode(checksum)
            if (urlParameters['action'] =="delete")  and ("id" in urlParameters.keys()):
                id = urllib.parse.unquote(urlParameters['id'])
                buttonHandler.deleteButton(id)
                return self.updateCode(checksum)
            if (urlParameters['action'] =="click") and ("id" in urlParameters.keys()):
                id = urllib.parse.unquote(urlParameters['id'])
                buttonHandler.click(id)
                return self.updateCode(checksum)
            if (urlParameters['action'] =="dblclick") and ("id" in urlParameters.keys()):
                id = urllib.parse.unquote(urlParameters['id'])
                buttonHandler.dblclick(id)
                return self.updateCode(checksum)
            if (urlParameters['action'] =="hold") and ("id" in urlParameters.keys()):
                id = urllib.parse.unquote(urlParameters['id'])
                buttonHandler.hold(id)
                return self.updateCode(checksum)
            if (urlParameters['action'] =="scan") :
                buttonHandler.startScan()
                return self.updateCode(checksum)
            if (urlParameters['action'] =="addHub") and ("addr" in urlParameters.keys()):
                yoctoConnectionHandler.addConnection(urlParameters['addr'])
                saveConfig()
                return self.updateCode(checksum)
            if (urlParameters['action'] =="removeHub") and ("addr" in urlParameters.keys()):
                yoctoConnectionHandler.deleteConnection(urlParameters['addr'])
                saveConfig()
                return self.updateCode(checksum)
            if (urlParameters['action'] =="configureBtn")  and ("id" in urlParameters.keys()):
                description = ""
                id = urllib.parse.unquote(urlParameters['id'])
                log("change for "+id);
                if   ("desc" in urlParameters.keys()):
                    description = urllib.parse.unquote(urlParameters['desc'])
                    buttonHandler.setDescription(id,description)
                if  ("type" in urlParameters.keys()) and  ("target" in urlParameters.keys()) and ("targetAction" in urlParameters.keys())   :
                    type = urllib.parse.unquote(urlParameters['type'])
                    target = urllib.parse.unquote(urlParameters['target'])
                    action = urllib.parse.unquote(urlParameters['targetAction'])
                    paramid= "targetActionParam0"
                    params=[]
                    n=0
                    while paramid in urlParameters.keys():
                       actionParam  = urllib.parse.unquote(urlParameters[paramid])
                       params.append(actionParam)
                       n=n+1
                       paramid= "targetActionParam"+str(n)

                    if ((type=='onclick')  or  (type=='ondblclick') or  (type=='onhold')):
                      if YoctoDevicesHandler.checkActionValidity(  target, action, params):
                         actionObject = FlicButtonAction(type , target, action, params)
                         buttonHandler.setAction(id,actionObject)
                      else:
                         log("Invalid action configuration. ignored")

                saveConfig()
                return self.updateCode(checksum)

#            if (urlParameters['action'] == "delete") and ("id" in urlParameters.keys()):
#                deleteButton(urlParameters['id'])

        return "<!DOCTYPE html><HTML>Nothing to do:<br>"  +str(urlParameters)+  "  </HTML>"


    # GET
    def do_GET(self):
        global buttonHandler
        urlParameters = {}
        url = self.path
        n = url.find("/?")
        if (n>=0):
          url=url[n+2:]
          n = url.find(" ")
          if (n>0): url= url[:n]
          parameters = url.split('&')
          for s  in parameters:
              tokens = s.split('=')
              if len(tokens)==2:
                  urlParameters[tokens[0]] =  tokens[1]

        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type','text/html')
        self.end_headers()
        message=""

        # Send message back to client
        if (len(urlParameters) == 0):
            message = self.get_basehtml()
        else:
            message = self.process_cmd(urlParameters)

        # Write content as utf-8 data
        try:
          self.wfile.write(bytes(message, "utf8"))
        except Exception as e:
          log("Failed to send answer to client browser :"+str(e))
        return
    def log_message(self, format, *args):
        return


class YoctoConnection:

    def __init__ (self,addr):
        self._addr    = addr
        self._online   = False
        self._hubserial = "";
        if (addr.upper()=="USB"): self._hubserial = "usb";

        if  self._hubserial == "usb":
          try:
            errmsg=YRefParam()
            YAPI.RegisterHub('usb',errmsg)
            self._online   = True
          except   :
            log('Failed register USB : '+ errmsg.value)

        else:
          log("preregistering "+self._addr)
          YAPI.PreregisterHub(self._addr)

    def deviceArrival(self,m):
        count = m.functionCount()
        for i in range(0,count):
            if (m.functionType(i)=="Network"):

               url = m.get_url()
               #print("----------[NETWORK ARRIVAL ]--->"+url)
               p = url.index("://")
               if p>0 : url=url[p+3:]
               p = url.index(":")
               if p>0 : url=url[:p]
               if url==self._addr:
                   self._online=True
                   self._hubserial = m.get_serialNumber()
                   log("new network device "+m.get_serialNumber()+"/"+url)

    def deviceRemoval(self,m):
        if m.get_serialNumber() ==  self._hubserial : self._online   = False;

    def isOnline(self):
        return self._online

    def delete(self):
        log("about to delete usb")
        YAPI.UnregisterHub(self._addr)
        self._online=False

    def getXmlCode(self):
        return '<HUB Addr="'+escape(self._addr)+'"/>\n'

    def getJsonCode(self):
        online="true"
        if not(self._online) : online="false"
        res =   quote(self._addr)+': {"Addr":'+quote(self._addr)+',"online":'+online+'  }'
        return res


class YoctoConnectionHandler:
    def __init__ (self):
      self._ConnectionList = {}

    def initFromXml(self,xmlNode):
      for node in xmlNode:
         if "Addr" in node.attrib.keys():
             self.addConnection( node.attrib["Addr"])

    def deviceArrival(self,m):
        for  addr in self._ConnectionList:
           self._ConnectionList[addr].deviceArrival(m)

    def deviceRemoval(self,m):
     for  addr in self._ConnectionList:
         self._ConnectionList[addr].deviceRemoval(m)

    def addConnection(self,addr):
        if addr in self._ConnectionList.keys(): return
        self._ConnectionList[addr] = YoctoConnection(addr)

    def deleteConnection(self,addr):
        if not(addr in self._ConnectionList.keys()): return
        connection = self._ConnectionList[addr]
        del self._ConnectionList[addr]
        connection.delete()

    def getXmlCode(self):
        res="<HUBS>\n"
        for key in self._ConnectionList:
          res=res+"  "+self._ConnectionList[key].getXmlCode()
        res=res+"</HUBS>\n"
        return res

    def get_list(self):
        res=  ""
        for  key in  self._ConnectionList:
           if res != "": res= res  + ","
           res= res + self._ConnectionList[key].getJsonCode()
        return '"connections":{'+res+"}"





def saveConfig():
    global buttonHandler
    global yoctoHandler
    global yoctoConnectionHandler
    global  configfilename
    global saveAllowed
    if not(saveAllowed) : return
    xml = '<?xml version="1.0" ?>\n<ROOT version="1.0">\n'
    # nodes order is critical
    xml = xml + yoctoConnectionHandler.getXmlCode()
    xml = xml + yoctoHandler.getXmlCode()
    xml = xml + buttonHandler.getXmlCode()
    xml = xml +"</ROOT>\n"
    text_file = open(configfilename, "w")
    text_file.write(xml)
    text_file.close()


def run():
    global buttonHandler
    global yoctoHandler
    global yoctoConnectionHandler
    global configfilename
    global serverIP
    global serverPort


    global saveAllowed

    YoctoRelay.staticInit()
    YoctoBuzzer.staticInit()
    YoctoServo.staticInit()
    YoctoVoltageOutput.staticInit()
    YoctoCurrentLoopOutput.staticInit()
    YoctoWakeUpMonitor.staticInit()

    log("Welcome to yocto-Flic, a Flic buttons to Yoctopuce devices bridge")
    log("Now compatible with Flic2")

    log("Command line parameters")
    log(" -config configfile        default is "+configfilename)
    log(" -ip serverBindingAddress  default is first interface found ("+serverIP+")")
    log(" -port serverBindingPort   default is "+str(serverPort))
    log("YAPI version: "+YAPI.GetAPIVersion());


    paramcount= len(sys.argv)
    i =0
    while i<paramcount:
        if sys.argv[i]=="-config" and i<paramcount-1 :
            configfilename=sys.argv[i+1]
            i=i+1
        elif sys.argv[i]=="-ip" and i<paramcount-1 :
            serverIP=sys.argv[i+1]
            i=i+1
        elif sys.argv[i]=="-port" and i<paramcount-1 :
            serverPort=int(sys.argv[i+1])
            i=i+1
        i=i+1


    xmlRroot= None

    if os.path.isfile(configfilename):
        log("loading config file "+configfilename)
        xmlRroot= ET.parse(configfilename).getroot()
    else:
        log("Using default config")
        xmlRroot= ET.fromstring('<?xml version="1.0" ?><ROOT version="1.0"><HUBS><HUB Addr="usb"/></HUBS></ROOT>')

    yoctoConnectionHandler = YoctoConnectionHandler()
    yoctoHandler = YoctoDevicesHandler()
    buttonHandler=  FlicButtons()

    for child in xmlRroot:
        if child.tag=="HUBS":    yoctoConnectionHandler.initFromXml(child)
        if child.tag=="BUTTONS":  buttonHandler.initFromXml(child)
        if child.tag=="YDEVICES":  yoctoHandler.initFromXml(child)

    buttonHandler.start()

    yoctoHandler.start()

    # Server settings
    # Choose port 8080, for port 80, which is normally used for a http server, you need root access


    log("Starting web server on "+serverIP+":"+str(serverPort))
    server_address = (serverIP, serverPort)
    try:
      httpd = HTTPServer(server_address, testHTTPServer_RequestHandler)
    except Exception as e:
      log("Cannot start web server on "+serverIP+":"+str(serverPort)+ " ("+str(e)+")")
      return

    saveAllowed =True
    saveConfig()
    httpd.serve_forever()

run()




