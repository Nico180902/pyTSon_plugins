import ts3defines, ts3lib, re, pytson
from pluginhost import PluginHost
from ts3plugin import ts3plugin
from ts3client import CountryFlags
from json import loads
from datetime import timedelta
from pytsonui import setupUi
from collections import OrderedDict
from PythonQt.QtGui import QDialog, QComboBox, QListWidget, QListWidgetItem, QValidator, QRegExpValidator
from PythonQt.QtCore import Qt, QUrl, QRegExp
from PythonQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QHostAddress
from bluscream import saveCfg, loadCfg, timestamp, getScriptPath, confirm, escapeStr, parseCommand, getServerType, ServerInstanceType
from configparser import ConfigParser
from traceback import format_exc

class customBan(ts3plugin):
    path = getScriptPath(__name__)
    name = "Custom Ban"
    try: apiVersion = pytson.getCurrentApiVersion()
    except: apiVersion = 22
    requestAutoload = True
    version = "1.0"
    author = "Bluscream"
    description = "Requested by @mrcraigtunstall (217.61.6.128)\nExtended for @SossenSystems (ts3public.de)"
    offersConfigure = False
    commandKeyword = ""
    infoTitle = None
    menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CLIENT, 0, "Ban Client", "scripts/%s/ban_client.svg"%__name__)]
    hotkeys = []
    ini = "%s/config.ini"%path
    dlg = None
    cfg = ConfigParser()
    cfg["general"] = { "template": "", "whitelist": "", "ipapi": "True" , "stylesheet": "alternate-background-color: white;background-color: black;"}
    cfg["last"] = { "ip": "False", "name": "False", "uid": "True", "mytsid": "True", "hwid": "True", "reason": "", "duration": "0", "expanded": "False", "height": "", "alternate": "False", "ban on doubleclick": "False" }
    templates = {}
    whitelist = ["127.0.0.1"]
    waiting_for = (0,0)
    mytsids = {}

    def __init__(self):
        loadCfg(self.ini, self.cfg)
        url = self.cfg.get("general", "template")
        if url:
            self.nwmc_template = QNetworkAccessManager()
            self.nwmc_template.connect("finished(QNetworkReply*)", self.loadTemplates)
            self.nwmc_template.get(QNetworkRequest(QUrl(url)))
        url = self.cfg.get("general", "whitelist")
        if url:
            self.nwmc_whitelist = QNetworkAccessManager()
            self.nwmc_whitelist.connect("finished(QNetworkReply*)", self.loadWhitelist)
            self.nwmc_whitelist.get(QNetworkRequest(QUrl(url)))
        if PluginHost.cfg.getboolean("general", "verbose"): ts3lib.printMessageToCurrentTab("{0}[color=orange]{1}[/color] Plugin for pyTSon by [url=https://github.com/{2}]{2}[/url] loaded.".format(timestamp(),self.name,self.author))

    def stop(self):
        saveCfg(self.ini, self.cfg)

    def onIncomingClientQueryEvent(self, schid, command):
        cmd = parseCommand(command)
        if cmd[0] == "notifycliententerview":
            if not cmd[1]["client_myteamspeak_id"]: return
            if not schid in self.mytsids: self.mytsids[schid] = {}
            self.mytsids[schid][cmd[1]["clid"]] = cmd[1]["client_myteamspeak_id"]
        elif cmd[0] == "notifyclientleftview":
            if not schid in self.mytsids: return
            if not cmd[1]["clid"] in self.mytsids[schid]: return
            del self.mytsids[schid][cmd[1]["clid"]]

    def onMenuItemEvent(self, schid, atype, menuItemID, selectedItemID):
        print(self.mytsids)
        if atype != ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CLIENT or menuItemID != 0: return
        self.waiting_for = (schid, selectedItemID)
        ts3lib.requestClientVariables(schid, selectedItemID)

    def onUpdateClientEvent(self, schid, clid, invokerID, invokerName, invokerUID):
        if schid != self.waiting_for[0]: return
        if clid != self.waiting_for[1]: return
        self.waiting_for = (0, 0)
        (err, uid) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientProperties.CLIENT_UNIQUE_IDENTIFIER)
        if err != ts3defines.ERROR_ok: uid = ""
        (err, mytsid) = ts3lib.getClientVariable(schid, clid, 61)
        if err != ts3defines.ERROR_ok or not mytsid:
            if schid in self.mytsids and clid in self.mytsids[schid]:
                mytsid = self.mytsids[schid][clid]
            else: mytsid = ""
        (err, name) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientProperties.CLIENT_NICKNAME)
        if err != ts3defines.ERROR_ok: name = ""
        self.clid = clid; type = getServerType(schid)
        (err, ip) = ts3lib.getConnectionVariable(schid, clid, ts3defines.ConnectionProperties.CONNECTION_CLIENT_IP)
        if err != ts3defines.ERROR_ok or not ip:
            retCode = ts3lib.createReturnCode()
            ts3lib.requestConnectionInfo(schid, clid, retCode)
            (err, ip) = ts3lib.getConnectionVariable(schid, clid, ts3defines.ConnectionProperties.CONNECTION_CLIENT_IP)
        if not self.dlg: self.dlg = BanDialog(self, schid, clid, uid, name, ip, mytsid, "", type)
        else: self.dlg.setup(self, schid, clid, uid, name, ip, mytsid, "", type)
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def onConnectionInfoEvent(self, schid, clid):
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name,"> onConnectionInfoEvent", schid, clid)
        if not hasattr(self, "clid") or clid != self.clid: return
        (err, ip) = ts3lib.getConnectionVariable(schid, clid, ts3defines.ConnectionProperties.CONNECTION_CLIENT_IP)
        if ip and self.dlg: self.dlg.txt_ip.setText(ip)
        del self.clid

    def loadTemplates(self, reply):
        try:
            data = reply.readAll().data().decode('utf-8')
            self.templates = loads(data, object_pairs_hook=OrderedDict)
            if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> Downloaded ban templates:", self.templates)
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def loadWhitelist(self, reply):
        try:
            data = reply.readAll().data().decode('utf-8')
            self.whitelist = []
            for line in data.splitlines():
                ip = QHostAddress(line.strip())
                if ip.isNull(): print(self.name,">",line,"is not a valid IP! Not adding to whitelist.")
                else: self.whitelist.append(line.strip())
            if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> Downloaded ip whitelist:", self.whitelist)
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

class BanDialog(QDialog):
    moveBeforeBan = False
    clid = 0
    def __init__(self, script, schid, clid, uid, name, ip, mytsid, hwid, servertype, parent=None):
        try:
            super(QDialog, self).__init__(parent)
            setupUi(self, "%s/ban.ui"%script.path)
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.cfg = script.cfg
            self.ini = script.ini
            self.schid = schid
            self.templates = script.templates
            self.whitelist = script.whitelist
            self.name = script.name
            if script.cfg.getboolean("last", "expanded"):
                self.disableReasons(True)
            height = script.cfg.get("last", "height")
            if height: self.resize(self.width, int(height))
            else: self.disableReasons()
            alt = script.cfg.getboolean("last", "alternate")
            if alt: self.chk_alternate.setChecked(True)
            dblclick = script.cfg.getboolean("last", "ban on doubleclick")
            if dblclick: self.chk_doubleclick.setChecked(True)
            for reason in script.templates:
                self.lst_reasons.addItem(reason)
                self.box_reason.addItem(reason)
            self.box_reason.setEditText(script.cfg.get("last", "reason")) # setItemText(0, )

            """
            ipREX = QRegExp("[\w+\/]{27}=")
            ipREX.setCaseSensitivity(Qt.CaseInsensitive)
            ipREX.setPatternSyntax(QRegExp.RegExp)

            regValidator = QRegExpValidator(ipREX,0)
            self.txt_ip.setValidator(regValidator)
            """
            self.txt_ip.setInputMask( "000.000.000.000" );

            self.setup(script, schid, clid, uid, name, ip, mytsid, hwid, servertype)
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def setup(self, script, schid, clid, uid, name, ip, mytsid, hwid, servertype):
        self.setWindowTitle("Ban \"{}\" ({})".format(name, clid))
        self.clid = clid
        if not ip: (err, ip) = ts3lib.getConnectionVariable(schid, clid, ts3defines.ConnectionProperties.CONNECTION_CLIENT_IP)
        url = script.cfg.getboolean("general", "ipapi")
        if url:
            self.nwmc_ip = QNetworkAccessManager()
            self.nwmc_ip.connect("finished(QNetworkReply*)", self.checkIP)
            self.countries = CountryFlags()
            self.countries.open()
        self.disableISP()
        self.grp_ip.setChecked(script.cfg.getboolean("last", "ip"))
        self.txt_ip.setText(ip)
        self.grp_name.setChecked(script.cfg.getboolean("last", "name"))
        if name:
            regex = ""
            name = name.strip()
            name = re.escape(name)
            for char in name:
                if char.isalpha(): regex += "[%s%s]"%(char.upper(), char.lower())
                else: regex += char
            self.txt_name.setText(".*%s.*"%regex)
        else: self.txt_name.setText("")
        self.grp_uid.setChecked(script.cfg.getboolean("last", "uid"))
        self.txt_uid.setText(uid)
        self.grp_mytsid.setChecked(script.cfg.getboolean("last", "mytsid"))
        self.txt_mytsid.setText(mytsid)
        if servertype == ServerInstanceType.TEASPEAK:
            self.grp_hwid.setChecked(script.cfg.getboolean("last", "hwid"))
            self.txt_hwid.setText(hwid)
        else: self.grp_hwid.setVisible(False)
        self.setDuration(script.cfg.getint("last", "duration"))

    def disableReasons(self, enable=False):
        for item in [self.lst_reasons,self.line,self.chk_alternate,self.chk_doubleclick,self.chk_keep]:
            item.setVisible(enable)
        if enable:
            self.btn_reasons.setText("Reasons <")
            self.setFixedWidth(675) # self.resize(675, self.height)
        else:
            self.btn_reasons.setText("Reasons >")
            self.setFixedWidth(320) # self.resize(320, self.height)

    def disableISP(self, enable=False):
        # if not enable and self.txt_loc.isVisible(): return
        # elif enable and not self.txt_loc.isVisible(): return
        for item in [self.lbl_isp,self.txt_isp,self.lbl_flag,self.txt_loc]:
            item.setVisible(enable)

    def disableAlt(self, enable=False):
        self.lst_reasons.setAlternatingRowColors(enable)
        self.lst_reasons.setStyleSheet(self.cfg.get("general", "stylesheet") if enable else "")

    def checkIP(self, reply):
        try:
            data = reply.readAll().data().decode('utf-8')
            # if PluginHost.cfg.getboolean("general", "verbose"): print(self.name,"> checkIP() data:",data)
            data = loads(data)
            if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> Resolved IP ", self.txt_ip.text,":", data)
            if data["status"] != "success": self.disableISP(); return
            self.txt_isp.setText(data["isp"])
            self.txt_loc.setText("{}, {}, {}".format(data["city"], data["regionName"], data["country"]))
            code = data["countryCode"]
            self.lbl_flag.setToolTip(code)
            self.lbl_flag.setPixmap(self.countries.flag(code))
            if not self.txt_isp.isVisible(): self.disableISP(True)
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def on_txt_ip_textChanged(self, text):
        try:
            if not hasattr(self, "nwmc_ip"): self.disableISP(); return
            if not text: self.disableISP(); return
            if len(text) < 7: self.disableISP(); return
            ip = QHostAddress(text)
            if ip.isNull() or ip.isLoopback() or ip.isMulticast(): self.disableISP(); return
            if text.strip() in ["127.0.0.1", "0.0.0.0", "255.255.255"]: self.disableISP(); return
            self.nwmc_ip.get(QNetworkRequest(QUrl("http://ip-api.com/json/{ip}".format(ip=text))))
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def on_txt_uid_textChanged(self, text):
        if not text: return
        valid = re.match('^[\w+\/]{27}=$', text)
        valid_teaspeak = re.match('^music#[\w]{15}$', text)
        if not valid and not valid_teaspeak: self.txt_uid.setStyleSheet("background-color:#5C4601")
        else: self.txt_uid.setStyleSheet("")

    def on_txt_mytsid_textChanged(self, text):
        if not text: return
        valid = re.match('^[\w+\/]{44}$', text)
        if not valid: self.txt_mytsid.setStyleSheet("background-color:#5C4601")
        else: self.txt_mytsid.setStyleSheet("")

    def on_txt_hwid_textChanged(self, text):
        if not text: return
        valid = re.match('^[a-z0-9]{32},[a-z0-9]{32}$', text)
        if not valid: self.txt_hwid.setStyleSheet("background-color:#5C4601")
        else: self.txt_hwid.setStyleSheet("")

    def on_box_reason_currentTextChanged(self, text):
        if not text in self.templates: return
        self.setDuration(self.templates[text])

    def on_lst_reasons_itemClicked(self, item):
        try: self.box_reason.setEditText(item.text())
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def on_lst_reasons_itemDoubleClicked(self, item):
        if not self.chk_doubleclick.isChecked(): return
        self.box_reason.setEditText(item.text())
        self.on_btn_ban_clicked()

    def on_chk_alternate_toggled(self, enabled):
        self.disableAlt(enabled)

    def setDuration(self, bantime:int):
        delta = timedelta(seconds=bantime)
        days, seconds = delta.days, delta.seconds
        hours = days * 24 + seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = (seconds % 60)
        self.int_duration.setValue(seconds)
        self.int_duration_m.setValue(minutes)
        self.int_duration_h.setValue(hours)
        self.int_duration_d.setValue(days)

    """
    def on_grp_hwid_toggled(self, enabled:bool):
        if enabled:
            self.grp_ip.setChecked(True)
            self.grp_uid.setChecked(True)
            self.grp_mytsid.setChecked(True)
            self.grp_name.setEnabled(False)
        else:
            self.grp_name.setEnabled(True)
    """

    def on_btn_ban_clicked(self):
        try:
            ip = self.txt_ip.text if self.grp_ip.isChecked() else ""
            name = self.txt_name.text if self.grp_name.isChecked() else ""
            uid = self.txt_uid.text if self.grp_uid.isChecked() else ""
            mytsid = self.txt_mytsid.text if self.grp_mytsid.isChecked() else ""
            hwid = self.txt_hwid.text if self.grp_hwid.isVisible() and self.grp_hwid.isChecked() else ""
            reason = self.box_reason.currentText
            if reason[0].isdigit():
                reason = "§" + reason
            delta = timedelta(seconds=self.int_duration.value,minutes=self.int_duration_m.value,hours=self.int_duration_h.value,days=self.int_duration_d.value)
            duration = delta.seconds
            if self.moveBeforeBan: ts3lib.requestClientMove(self.schid, self.clid, 26, "")
            # if uid:
            if ip:
                check = True
                if len(self.whitelist) < 1: check = confirm("Empty IP Whitelist!", "The IP whitelist is empty! Are you sure you want to ban \"{}\"?\n\nMake sure your whitelist URL\n{}\nis working!".format(ip, self.cfg.get("general", "whitelist")))
                if ip in self.whitelist: ts3lib.printMessageToCurrentTab("{}: [color=red]Not banning whitelisted IP [b]{}".format(self.name, ip))
                elif check: ts3lib.banadd(self.schid, ip, "", "", duration, reason)
            if name: ts3lib.banadd(self.schid, "", name, "", duration, reason)
            if uid: ts3lib.banadd(self.schid, "", "", uid, duration, reason)
            if mytsid: ts3lib.requestSendClientQueryCommand(self.schid, "banadd mytsid={} banreason={} time={}".format(mytsid, escapeStr(reason), duration))
            if hwid: ts3lib.requestSendClientQueryCommand(self.schid, "banadd hwid={} banreason={} time={}".format(hwid, escapeStr(reason), duration))
            # msgBox("schid: %s\nip: %s\nname: %s\nuid: %s\nduration: %s\nreason: %s"%(self.schid, ip, name, uid, duration, reason))
            self.cfg["last"] = {
                "ip": str(self.grp_ip.isChecked()),
                "name": str(self.grp_name.isChecked()),
                "uid": str(self.grp_uid.isChecked()),
                "mytsid": str(self.grp_mytsid.isChecked()),
                "hwid": str(self.grp_hwid.isChecked()),
                "reason": reason,
                "duration": str(duration),
                "expanded": str(self.lst_reasons.isVisible()),
                "height": str(self.height),
                "alternate": str(self.chk_alternate.isChecked()),
                "ban on doubleclick": str(self.chk_doubleclick.isChecked()),
            }
            if not self.chk_keep.isChecked():
                self.close()
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def on_btn_cancel_clicked(self):
        self.cfg.set("last", "expanded", str(self.lst_reasons.isVisible()))
        self.cfg.set("last", "height", str(self.height))
        self.cfg.set("last", "alternate", str(self.chk_alternate.isChecked()))
        self.cfg.set("last", "ban on doubleclick", str(self.chk_doubleclick.isChecked()))
        self.close()

    def on_btn_reasons_clicked(self):
        if self.lst_reasons.isVisible():
            self.disableReasons()
        else: self.disableReasons(True)
