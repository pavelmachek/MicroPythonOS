from mpos import Activity

"""

"""

import time
import os

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, MposKeyboard


# ------------------------------------------------------------
#
# ------------------------------------------------------------

class Main(Activity):

    def __init__(self):
        super().__init__()

     # --------------------

    def onCreate(self):
        self.screen = lv.obj()
        #self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Top labels
        self.lbl_time = lv.label(self.screen)
        self.lbl_time.set_style_text_font(lv.font_montserrat_20, 0)
        self.lbl_time.align(lv.ALIGN.TOP_LEFT, 6, 4)

        self.lbl_date = lv.label(self.screen)
        self.lbl_date.align(lv.ALIGN.TOP_LEFT, 6, 40)

        self.lbl_month = lv.label(self.screen)
        self.lbl_month.align(lv.ALIGN.TOP_RIGHT, -6, 10)

        # Upcoming events list
        self.upcoming_list = lv.list(self.screen)
        self.upcoming_list.set_size(lv.pct(90), 60)
        self.upcoming_list.align_to(self.lbl_date, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 10)

        self.setContentView(self.screen)

    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, 3000, None)
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

        self.lbl_time.set_text("%02d:%02d" % (hh, mm))
        self.lbl_date.set_text("%04d-%02d-%02d %s" % (y, m, d, ""))

    # --------------------


