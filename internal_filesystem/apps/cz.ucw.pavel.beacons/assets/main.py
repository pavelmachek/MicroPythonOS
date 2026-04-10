from mpos import Activity

"""
"""

import time
import os

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, MposKeyboard, DownloadManager

import ujson
import utime
import usocket as socket
import ujson
import requests

# -----------------------------
#
# -----------------------------

class Weather:
    def __init__(self):
        self.summary = "(no data)"

    def fetch(self):
        print()
        print()

        # GSM,230,1,22,932,,17.2540622,49.0349105,1704,32,1,1459086249,1459097316,

        self.mcc = 230        # country code
        self.mnc = 1          # operator
        self.type = "gsm"     # or "lte"
        self.lac = 22
        self.cid = 932
        self.cell_signal = -70

        self.wifi_aps = [
            {"mac": "11:22:33:44:55:66", "rssi": -1 },
        ]

        self.summary = "...locating..."

        host = "api.beacondb.net"
        path = "/v1/geolocate"
        url = "https://" + host + path

        # Radiotype can be also lte
        payload = {
            "cellTowers": [
                {
                    "radioType": self.type,
                    "mobileCountryCode": self.mcc,
                    "mobileNetworkCode": self.mnc,
                    "locationAreaCode": self.lac,
                    "cellId": self.cid,
                    "signalStrength": self.cell_signal
                }
            ],
            "wifiAccessPoints": [
                {
                    "macAddress": ap["mac"],
                    "signalStrength": ap["rssi"]
                }
                for ap in self.wifi_aps
            ],
            "considerIp": False
        }

        print("BeaconDB fetch:", url)
        print("Payload:", payload)

        headers = {
            "User-Agent": "MyGeoClient/1.0 (Python requests; BeaconDB lookup)"
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
        except Exception as e:
            print("Request failed:", e)
            self.summary = "Download error"
            return

        if resp.status_code != 200:
            print("HTTP error:", resp.status_code, resp.text)
            self.summary = "HTTP error"
            return

        try:
            data = resp.json()
        except Exception as e:
            print("JSON parse error:", e)
            self.summary = "Parse error"
            return

        try:
            loc = data["location"]
            self.lat = loc["lat"]
            self.lon = loc["lng"]
            self.accuracy = data.get("accuracy")

            self.summary = f"Lat: {self.lat},\nLon: {self.lon},\n±{self.accuracy}m"
            print(data, "\n\n")

        except Exception as e:
            print("Data error:", e)
            self.summary = "No location"
        
weather = Weather()
        
# ------------------------------------------------------------
# Main activity
# ------------------------------------------------------------

class Main(Activity):
    def __init__(self):
        self.last_hour = 0
        super().__init__()

     # --------------------

    def onCreate(self):
        self.screen = lv.obj()
        #self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)
        scr_main = self.screen

        # ---- MAIN SCREEN ----

        label_weather = lv.label(scr_main)
        label_weather.set_text(f"(fixme))")
        label_weather.align(lv.ALIGN.TOP_LEFT, 10, 24)
        label_weather.set_style_text_font(lv.font_montserrat_14, 0)
        self.label_weather = label_weather

        btn_hourly = lv.button(scr_main)
        btn_hourly.align(lv.ALIGN.TOP_RIGHT, -5, 24)
        lv.label(btn_hourly).set_text("Reload")
        btn_hourly.add_event_cb(lambda x: self.do_load(), lv.EVENT.CLICKED, None)
        
        label_time = lv.label(scr_main)
        label_time.set_text("(time)")
        label_time.align_to(btn_hourly, lv.ALIGN.TOP_LEFT, -85, -10)
        label_time.set_style_text_font(lv.font_montserrat_24, 0)
        self.label_time = label_time

        label_summary = lv.label(scr_main)
        label_summary.set_text("(weather)")
        #label_summary.set_long_mode(lv.label.LONG.WRAP)
        #label_summary.set_width(300)
        label_summary.align_to(label_weather, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
        label_summary.set_style_text_font(lv.font_montserrat_24, 0)
        self.label_summary = label_summary

        if False:
            btn_daily = lv.button(scr_main)
            btn_daily.set_size(100, 40)
            btn_daily.align(lv.ALIGN.BOTTOM_RIGHT, -10, -10)
            lv.label(btn_daily).set_text("Daily")


        self.setContentView(self.screen)

    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, 15000, None)
        self.tick(0)

    def onPause(self, screen):
        if self.timer:
            self.timer.delete()
            self.timer = None

    # --------------------

    def tick(self, t):
        now = time.localtime()
        y, m, d = now[0], now[1], now[2]
        hh, mm, ss = now[3], now[4], now[5]

        if hh != self.last_hour:
            self.last_hour = hh
            self.do_load()

        self.label_time.set_text("%02d:%02d" % (hh, mm))
        self.label_summary.set_text(weather.summary)

    def do_load(self):
        self.label_summary.set_text("Requesting...")
        weather.fetch()
        
    # --------------------

    def code():
        # -----------------------------
        # LVGL UI
        # -----------------------------

        scr_main = lv.obj()
        scr_hourly = lv.obj()
        scr_daily = lv.obj()


        # ---- HOURLY SCREEN ----

        hourly_list = lv.list(scr_hourly)
        hourly_list.set_size(320, 200)
        hourly_list.align(lv.ALIGN.TOP_MID, 0, 10)

        btn_back1 = lv.button(scr_hourly)
        btn_back1.set_size(80, 30)
        btn_back1.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        lv.label(btn_back1).set_text("Back")

        # ---- DAILY SCREEN ----

        daily_list = lv.list(scr_daily)
        daily_list.set_size(320, 200)
        daily_list.align(lv.ALIGN.TOP_MID, 0, 10)

        btn_back2 = lv.button(scr_daily)
        btn_back2.set_size(80, 30)
        btn_back2.align(lv.ALIGN.BOTTOM_MID, 0, -5)
        lv.label(btn_back2).set_text("Back")
