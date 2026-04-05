from mpos import Activity

"""
Simple cellular-network example
"""

import time
import os
import json

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, MposKeyboard
import canvas

TMP = "/tmp/cmd.json"


def run_cmd_json(cmd):
    rc = os.system(cmd + " > " + TMP)
    if rc != 0:
        raise RuntimeError("command failed")

    with open(TMP, "r") as f:
        data = f.read().strip()

    return json.loads(data)

def dbus_json(cmd):
    return run_cmd_json("sudo /home/mobian/g/MicroPythonOS/internal_filesystem/apps/cz.ucw.pavel.cellular/assets/phone.py " + cmd)

class CellularManager:
    def init(self):
        v = dbus_json("loc_on")
    
    def poll(self):
        v = dbus_json("signal")
        print(v)
        self.signal = v

    def call(self, num):
        v = dbus_json("call '%s'" % num)

    def sms(self, num, text):
        v = dbus_json("call '%s' '%s'" % (num, text))

cm = CellularManager()

# ------------------------------------------------------------
# User interface
# ------------------------------------------------------------

class Main(CanvasActivity):
    def __init__(self):
        super().__init__()

    # --------------------

    def on_call(self):
        num = self.number.get_text()
        cm.call(num)

    def on_sms(self):
        num = self.number.get_text()
        text = self.sms.get_text()
        cm.sms(num, text)

    def tick(self, t):
        now = time.localtime()
        y, m, d = now[0], now[1], now[2]
        hh, mm, ss = now[3], now[4], now[5]

        cm.poll()
        s = ""
        s += cm.signal["OperatorName"] + "\n"
        s += "RegistrationState %d\n" % cm.signal["RegistrationState"]
        s += "State %d " % cm.signal["State"]
        sq, re = cm.signal["SignalQuality"]
        s += "Signal %d\n" % sq

    # --------------------


