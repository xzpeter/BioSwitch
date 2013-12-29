#!/usr/bin/python

import os
import sys
import signal
import wx
import wx.lib.rcsizer as rcs
import json
import datetime
import threading
import time
import copy
import serial
import struct

OS_TYPE=sys.platform            # can be 'darwin'
PROG_NAME = "Bio Relay Controller"
PROG_VERSION = "0.2"
LOG_LINES = 50
LEFT_PANEL_WIDTH = 500
BUTTON_SIZE = (150, 20)
MAX_CHANNEL_N = 8
QUICK_LOAD_CONFIG_FILE="quick_load.bio_config"
ABOUT_INFO = """This is a tiny program written for doudou for his bio experiment. Please
feel free to use it as a tool or for source code study. You can send mail to me
if you have any feedback or trouble. Thanks.  """
# set this if we don't want to really control the relay, but only test the logic
DEBUG = 1

# set default serial port
DEFAULT_PORT_LIST = {"darwin": "/dev/tty.usbserial", "win32": "COM1"}
if OS_TYPE not in DEFAULT_PORT_LIST:
    print "OS type not known: '%s'" % OS_TYPE
    exit (1)
DEFAULT_PORT = DEFAULT_PORT_LIST[OS_TYPE]

class RelayController():
    def __init__(self, logger, port, baudrate=9600):
        self.logger = logger
        if not DEBUG:
            self.log("initializing serial port (%s) with baudrate (%s)" % \
                            (port, baudrate))
            self.serial = serial.Serial(port=port, baudrate=baudrate)
            # stop all channels at first
            self.stop_all()
    def log(self, msg):
        self.logger(msg, name="relay")
    def stop_all(self):
        self.log("stopping all channels...")
        for i in range(MAX_CHANNEL_N):
            self.send_cmd(i+1, 0)
    def send_cmd(self, channel, value):
        """set the relay 'channel' with value 'value'. channel can be 1-8 and
        value can be 0-1"""
        if DEBUG:
            return
        if channel <= 0 or channel > MAX_CHANNEL_N:
            raise Exception("channel number (%s) should follow 0<ch<=%s" % \
                                (channel, MAX_CHANNEL_N))
        if value:
            value = 1
        else:
            value = 0
        data = struct.pack("5B", 0xFF, channel, value, channel + value, 0xEE)
        self.serial.write(data)
        self.serial.flush()

class WorkingThread(threading.Thread):
    STATUS_IDLE = 0
    STATUS_WORKING = 1
    def __init__(self, logger):
        threading.Thread.__init__(self)
        self.logger = logger
        self.event = threading.Event()
        self.cleanup()

    def cleanup (self):
        self.thread = None
        self.config = None
        self.control = None
        self.event.clear()
        self.state = WorkingThread.STATUS_IDLE

    def log(self, msg):
        self.logger(msg, name="thread")

    def start(self, config, port):
        # try to open the serial port first (which is called the RelayControler)
        try:
            self.control = RelayController(self.logger, port=port)
        except:
            self.control = None
            self.log("Thread didn't start due to init relay controller fail.")
            return

        self.log("going to START working thread...")
        self.state = WorkingThread.STATUS_WORKING
        self.config = copy.deepcopy(config)
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        if not self.thread:
            self.log("there is no working thread at all.")
            return
        self.log("going to STOP working thread... will stop at next event.")
        self.state = WorkingThread.STATUS_IDLE
        # notify thread that we are quitting
        self.event.set()
        # self.thread.join()
        # self.log("child thread joined.")
        # self.cleanup()

    def generate_event_queue(self, config):
        """generate event queue from the config file hash"""
        # config should have been checked before, just use it.
        channels = config["channels"]
        events = []
        for name in channels:
            channel = channels[name]["channel"]
            total = 0
            for duration in channels[name]["timing"]:
                duration["length"] += total
                total = duration["length"]
                duration["channel"] = channel
                duration["name"] = name
                events.append(duration)
        events.sort(key=lambda x: x["length"])
        return events

    def handle_event(self, event):
        """event should be: {"name", "length", "channel", "state"}"""
        name = event["name"]
        channel = event["channel"]
        state = event["state"]
        self.log("set channel '%s' [%s] ==> %s" % (name, channel, state))
        self.control.send_cmd(channel, state)

    def run(self):
        "config should be the config hash of app"
        config = self.config
        # generate the event queue to handle
        events = self.generate_event_queue(config)
        self.log("thread started with event queue: %s" % events)
        # this records the running time
        run_time = 0
        while self.state == WorkingThread.STATUS_WORKING:
            if len(events) == 0:
                # all the events handled
                break
            sleep_time = events[0]["length"] - run_time
            self.log("sleeping %s sec..." % sleep_time)
            # using events rather than raw sleep
            ret = self.event.wait(sleep_time)
            if ret == True:
                self.log("got stop event... quitting")
                self.event.clear()
                break
            run_time += sleep_time
            # handle events that should happen now
            while len(events) > 0 and events[0]["length"] == run_time:
                event = events.pop(0)
                self.handle_event(event)
        self.state = WorkingThread.STATUS_IDLE
        self.control.stop_all()
        self.cleanup()
        self.log("Thread stopped.")

class MainWindow (wx.Frame):
    def __init__ (self, parent, title):
        wx.Frame.__init__(self, parent=parent, title=title,
                          style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.WANTS_CHARS)
        self.config = None
        self.logLines = 0
        self.logBuffer = []
        self.InitFrame()
        self.workThread = WorkingThread(self.Log)

    def Log(self, str, name="main"):
        str = "%s: [%s] %s" % (datetime.datetime.now().ctime(), name, str)
        self.logBuffer.append(str)
        if len(self.logBuffer) > LOG_LINES:
            self.logBuffer.pop(0)
        self.FlushLog()

    def FlushLog(self):
        self.logArea.SetValue("\n".join(self.logBuffer))
        self.logArea.SetInsertionPointEnd()

    def AddFocusObject(self, obj):
        if not hasattr(self, "focusList"):
            self.focusList = []
        if type([]) == type(obj):
            for i in obj:
                self.focusList.append(i)
        else:
            self.focusList.append(obj)

    def SetFocusObjectKeyHandle(self):
        if hasattr(self, "focusList"):
            for item in self.focusList:
                # FIXME: bind all items that can get focus, this is poor and I
                # am too lazy to find the good way...This should make sure that
                # all F1-F8 can be used
                item.Bind(wx.EVT_KEY_UP, self.OnKeyUp)

    def InitFrame(self):
        self.statusBar = self.CreateStatusBar()

        # the File menu
        self.fileMenu = fileMenu = wx.Menu()
        loadButton = fileMenu.Append(wx.ID_ANY, "&Load Config File", "Load configuration file")
        fileMenu.AppendSeparator()
        quitButton = fileMenu.Append(wx.ID_ANY, "&Quit", "Quit the program")

        # the About menu
        self.aboutMenu = aboutMenu = wx.Menu()
        aboutButton = aboutMenu.Append(wx.ID_ANY, "&About", "About the program")

        # the menu bar creation
        self.menuBar = menuBar = wx.MenuBar()
        menuBar.Append(fileMenu, "&File")
        menuBar.Append(aboutMenu, "&About")
        self.SetMenuBar(menuBar)

        ########################
        # the main window layout
        ########################
        labelLink = wx.StaticText(self, -1, "(*) Please visit http://jsonlint.com/ to verify JSON data",
                                  style=wx.ALIGN_RIGHT)

        # control items
        sizerAll = wx.BoxSizer(wx.HORIZONTAL)
        sizerLeft = wx.BoxSizer(wx.VERTICAL)
        sizerRight = wx.BoxSizer(wx.VERTICAL)

        sizerAll.Add(sizerLeft, 0, wx.EXPAND)
        sizerAll.Add(sizerRight, 0, wx.EXPAND)

        sizerName = wx.BoxSizer(wx.HORIZONTAL)
        sizerConfig = wx.BoxSizer(wx.HORIZONTAL)
        sizerLog = wx.BoxSizer(wx.HORIZONTAL)

        sizerLeft.Add(sizerName, 0, wx.EXPAND)
        sizerLeft.Add(sizerConfig, 0, wx.EXPAND)
        sizerLeft.Add(labelLink, 0, wx.EXPAND)
        sizerLeft.Add(sizerLog, 0, wx.EXPAND)
        

        self.configName = configName = wx.TextCtrl(self,
                                                   size=(LEFT_PANEL_WIDTH, 30))
        self.configArea = configArea = wx.TextCtrl(self,
                                                   style=wx.TE_MULTILINE|wx.TE_PROCESS_TAB,
                                                   size=(LEFT_PANEL_WIDTH, 400))
        self.logArea = logArea = wx.TextCtrl(self,
                                             style=wx.TE_MULTILINE|wx.TE_READONLY,
                                             size=(LEFT_PANEL_WIDTH, 100))

        self.portLabel = wx.StaticText(self, -1, "Serial Port: ", style=wx.ALIGN_LEFT)
        self.portConfig = wx.TextCtrl(self, value=DEFAULT_PORT)
        self.buttonLoadConfig = btnLoad = wx.Button(self, -1, "Load Config", size=BUTTON_SIZE)
        self.buttonSaveConfig = btnSave = wx.Button(self, -1, "Save Config", size=BUTTON_SIZE)
        self.buttonStart = btnStart = wx.Button(self, -1, "Start Test", size=BUTTON_SIZE)
        self.buttonStop = btnStop = wx.Button(self, -1, "Stop Test", size=BUTTON_SIZE)
        self.buttonQuit = btnQuit = wx.Button(self, -1, "Quit Program", size=BUTTON_SIZE)
        self.buttonSaveQuick = btnSaveQuick = wx.Button(self, -1, "Save F1-F8 configs", size=BUTTON_SIZE)
        btnList = [btnLoad, btnSave, btnStart, btnStop, btnQuit]

        sizerRight.Add(self.portLabel, 0, wx.EXPAND)
        sizerRight.Add(self.portConfig, 0, wx.EXPAND)
        for btn in btnList:
            sizerRight.Add(btn, 0, wx.EXPAND)

        # adding F1-F8 shortcut keys
        self.labelFx = []
        self.configNameFx = []
        for i in range(8):
            # create the label X
            label = wx.StaticText(self, -1, "short key F%s: " % (i+1), style=wx.ALIGN_LEFT)
            sizerRight.Add(label, 0, wx.EXPAND)
            self.labelFx.append(label)

            # create the config name box X
            configBox = wx.TextCtrl(self, size=(150, -1))
            sizerRight.Add(configBox, 0, wx.EXPAND)
            self.configNameFx.append(configBox)
            self.AddFocusObject(configBox)
        # add one line help:
        label = wx.StaticText(self, -1, "Please use F1-F8 to \nquick load/run config files, \nor use F10 to stop any run.")
        sizerRight.Add(label, 0)
        sizerRight.Add(btnSaveQuick)

        # labels
        labelSize = (50, 20)
        labelName = wx.StaticText(self, -1, "Name:", size=labelSize, style=wx.ALIGN_RIGHT)
        labelConfig = wx.StaticText(self, -1, "Config:", size=labelSize, style=wx.ALIGN_RIGHT)
        labelLog = wx.StaticText(self, -1, "Logging:", size=labelSize, style=wx.ALIGN_RIGHT)

        # box sizer layout
        sizerName.Add(labelName, 0)
        sizerName.Add(configName, 0, wx.EXPAND)
        sizerConfig.Add(labelConfig, 0)
        sizerConfig.Add(configArea, 0, wx.EXPAND)
        sizerLog.Add(labelLog, 0)
        sizerLog.Add(logArea, 0, wx.EXPAND)

        # set the sizer
        self.SetSizer(sizerAll)
        self.SetAutoLayout(1)
        sizerAll.Fit(self)

        # event handlings
        self.Bind(wx.EVT_MENU, self.OnOpen, loadButton)
        self.Bind(wx.EVT_MENU, self.OnQuit, quitButton)
        self.Bind(wx.EVT_MENU, self.OnAbout, aboutButton)
        btnLoad.Bind(wx.EVT_BUTTON, self.OnOpen)
        btnSave.Bind(wx.EVT_BUTTON, self.OnSave)
        btnStart.Bind(wx.EVT_BUTTON, self.OnStart)
        btnStop.Bind(wx.EVT_BUTTON, self.OnStop)
        btnQuit.Bind(wx.EVT_BUTTON, self.OnQuit)
        btnSaveQuick.Bind(wx.EVT_BUTTON, self.OnSaveQuickConfig)

        # handle all the key inputs
        self.AddFocusObject([self.configArea, self.configName, self.logArea, self.portConfig])
        self.SetFocusObjectKeyHandle()

        # load the quick config files
        self.LoadQuickConfig()

        self.Show(True)

    def OnSaveQuickConfig(self, e):
        "Save all the quick configs into file"
        array = []
        for item in self.configNameFx:
            array.append(item.GetValue())
        f = open(QUICK_LOAD_CONFIG_FILE, "w")
        f.write(json.dumps(array))
        f.close()
        self.ShowMsg("Quick load config files saved.")

    def LoadQuickConfig (self):
        if os.path.isfile(QUICK_LOAD_CONFIG_FILE):
            try:
                self.Log("quick config found... will try to load it...")
                f = open(QUICK_LOAD_CONFIG_FILE, "r")
                data = json.loads(f.read())
                f.close
                for i in range(8):
                    self.configNameFx[i].SetValue(data[i])
            except:
                self.Log("failed load quick config, clearing the file...")
                os.unlink(QUICK_LOAD_CONFIG_FILE)

    def OnKeyUp(self, e):
        key = e.GetKeyCode()
        # handle stop running
        if key == wx.WXK_F10:
            self.OnStop(None)
        # handle shortcut load/start configs:
        if key >= wx.WXK_F1 and key <= wx.WXK_F8:
            key -= wx.WXK_F1
            self.HandleFxPressed(key)

    def HandleFxPressed(self, key):
        fileName = self.configNameFx[key].GetValue()
        if not fileName:
            self.ShowMsg("Please input file name before using shortcut keys.")
        if self.LoadConfigFile(fileName):
            # load config file nicely, try to run the config file
            self.OnStart(None)

    def SaveConfig(self, hash, fileName):
        "Save hash into fileName"
        dataJson = self.ConvertJson(hash)
        file = open(fileName, "w")
        file.write(dataJson)
        file.close()
        self.ShowMsg("Config data saved to '%s/%s'" % (os.getcwd(), fileName))

    def OnSave(self, e):
        dataHash = self.GetConfig()
        if not dataHash:
            return
        fileName = self.UpdateConfigFileName()
        if not fileName:
            return
        self.SaveConfig(dataHash, fileName)

    def CheckConfigFileName(self, name):
        if len(name) <= 5 or name[-5:] != ".conf":
            return False
        return True

    def UpdateConfigFileName(self):
        fileName = self.configName.GetValue()
        if not self.CheckConfigFileName(fileName):
            self.ShowMsg("Config file name format not right")
            return False
        self.fileName = fileName
        return fileName

    def GetConfig(self):
        data = self.configArea.GetValue()
        dataHash = self.ParseConfigData(data)
        return dataHash

    def OnStart (self, e):
        config = self.GetConfig()
        if not config:
            self.ShowMsg("config parse error, please fix config and then start again")
            return
        self.workThread.start(config, self.portConfig.GetValue().strip())

    def OnStop (self, e):
        self.workThread.stop()

    def ParseJson(self, str):
        "try to load the JSON string into hash"
        try:
            return json.loads(str)
        except:
            return None

    def ConvertJson(self, hash):
        return json.dumps(hash, indent=4)

    def ParseConfigData(self, str):
        dataHash = self.ParseJson(str)
        if not dataHash:
            self.ShowMsg("Config format not right, please fix")
            return None
        if "description" not in dataHash:
            self.ShowMsg("need 'description' entry!")
            return None
        if "channels" not in dataHash:
            self.ShowMsg("need 'channels' entry!")
            return None
        channels = dataHash["channels"]
        index_list = []
        for chnl in channels:
            value = channels[chnl]
            if "channel" not in value:
                self.ShowMsg("channel '%s' need key 'channel' as index" % \
                             chnl)
                return None
            index = value["channel"]
            if index in index_list:
                self.ShowMsg("channel '%s' existed more than once!" % index)
                return None
            index_list.append(index)
            if "timing" not in value:
                self.ShowMsg("channel '%s' need key 'timing'")
                return None
            for item in value["timing"]:
                for key in ["length", "state"]:
                    if key not in item:
                        self.ShowMsg("in item '%s' channel '%s', need '%s'" \
                                     % (item, chnl, key))
                        return None
        return dataHash
        return True

    def LoadConfigFile(self, path):
        """Will try to load a config file with name `filename`"""
        try:
            f = open(path, 'r')
            data = f.read()
            f.close()
        except:
            self.ShowMsg("failed to read config file: '%s'" % path)
            return False
        # first try load the data
        dataHash = self.ParseConfigData(data)
        if not dataHash:
            self.ShowMsg("failed parse config file: '%s'" % fileName)
            return False
        # load OK
        self.configPath = path
        self.fileName = os.path.basename(path)
        self.configArea.SetValue(self.ConvertJson(dataHash))
        self.configName.SetValue(self.fileName)
        self.Log("config file (%s) loaded." % self.fileName)
        return True

    def OnOpen(self, e):
        dlg = wx.FileDialog(self,
                            message="Please choose bio config file...",
                            defaultDir=os.getcwd(),
                            wildcard="*.conf",
                            style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            fileName = dlg.GetFilename()
            dirName = dlg.GetDirectory()
            path = os.path.join(dirName, fileName)
            self.LoadConfigFile(path)
        dlg.Destroy()

    def NotDone(self, e):
        dlg = wx.MessageDialog(self, "Hello...", "NOT IMPLEMENTED...", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def ShowMsg(self, message, caption=PROG_NAME):
        dlg = wx.MessageDialog(self, message, caption, wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnAbout(self, e):
        info = wx.AboutDialogInfo()
        info.Name = PROG_NAME
        info.Version = PROG_VERSION
        info.Copyright = "(C) Peter Xu (xzpeter@gmail.com)"
        info.Description = ABOUT_INFO
        info.WebSite = ("http://github.com/xzpeter", "Home page of me on github")
        info.Developers = [ "Peter Xu (xzpeter)" ]
        info.License = "LICENSE"

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)

    def OnQuit(self, e):
        self.Close(True)

app = wx.App(False)
frame = MainWindow(None, PROG_NAME)
app.MainLoop()
