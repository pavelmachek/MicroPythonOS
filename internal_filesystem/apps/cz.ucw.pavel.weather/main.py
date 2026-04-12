from mpos import Activity

"""
Look at https://open-meteo.com/en/docs , then design an application that would display current time and weather, and summary of forecast ("no change expected for 2 days" or maybe "rain in 5 hours"), with a way to access detailed forecast.
"""

import time

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, DownloadManager, TaskManager

import ujson
import utime
import usocket as socket

from weather import *

class MyWeather(Weather):
    def download_url(m, url):
        return DownloadManager.download_url(url)

weather = MyWeather()
        
# ------------------------------------------------------------
# Main activity
# ------------------------------------------------------------

class Main(Activity):
    def __init__(self):
        self.last_hour = 0
        self.load_task = None
        super().__init__()

     # --------------------

    def onCreate(self):
        self.screen = lv.obj()
        #self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)
        scr_main = self.screen

        # ---- MAIN SCREEN ----

        label_weather = lv.label(scr_main)
        label_weather.set_text(f"{weather.name} ({weather.lat}, {weather.lon})")
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
        if self.load_task and not self.load_task.done():
            self.load_task.cancel()
            self.load_task = None

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
        if self.load_task and not self.load_task.done():
            return
        self.label_summary.set_text("Requesting...")
        self.load_task = TaskManager.create_task(self.do_load_async())

    async def do_load_async(self):
        try:
            await weather.fetch()
        except Exception as e:
            print("Weather fetch failed:", e)
            self.label_summary.set_text("Download error")
            return
        self.label_summary.set_text(weather.summary)
        
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

    def foo():
        btn_hourly.add_event_cb(go_hourly, lv.EVENT.CLICKED, None)
        btn_daily.add_event_cb(go_daily, lv.EVENT.CLICKED, None)
        btn_back1.add_event_cb(go_back, lv.EVENT.CLICKED, None)
        btn_back2.add_event_cb(go_back, lv.EVENT.CLICKED, None)

        # -----------------------------
        # STARTUP
        # -----------------------------

        def go_hourly(e):
            populate_hourly()
            lv.scr_load(scr_hourly)

        def go_daily(e):
            populate_daily()
            lv.scr_load(scr_daily)

        def go_back(e):
            lv.scr_load(scr_main)
        
        def update_ui():
            if weather.current_temp is not None:
                text = "%s  %.1f C" % (
                    weather_code_to_text(weather.current_code),
                    weather.current_temp
                )
                label_weather.set_text(text)

            label_summary.set_text(weather.summary)

        def populate_hourly():
            hourly_list.clean()
            for h in weather.hourly[:24]:
                line = "%s  %.1fC  %.1fmm" % (
                    h["time"][11:16],
                    h["temp"],
                    h["precip"]
                )
                hourly_list.add_text(line)

        def populate_daily():
            daily_list.clean()
            for d in weather.daily:
                line = "%s  %.1f/%.1f" % (
                    d["date"],
                    d["high"],
                    d["low"]
                )
                daily_list.add_text(line)
