import time
import os
import uselect
import json
import time
import math
import re

from pcanvas import *

try:
    import lvgl as lv
except ImportError:
    pass

import mpos
from mpos import Activity, MposKeyboard

# -------------------------------------------------
# Enter Target dialog
# -------------------------------------------------

class TextIn(Activity):
    def __init__(self):
        super().__init__()

    def onCreate(self):
        self.scr = lv.obj()

        # Position input
        self.pos_ta = lv.textarea(self.scr)
        self.pos_ta.set_size(300, 40)
        self.pos_ta.align(lv.ALIGN.TOP_MID, 0, 18)
        self.pos_ta.set_placeholder_text("N 50 30.123 E 14 13.231")

        title = lv.label(self.scr)
        title.set_text("Goto position")
        title.align_to(self.pos_ta, lv.ALIGN.OUT_BOTTOM_MID, 0, 10)

        if False:
            # Filename input
            self.file_ta = lv.textarea(self.scr)
            self.file_ta.set_size(300, 40)
            self.file_ta.align(lv.ALIGN.TOP_MID, 0, 10)
            self.file_ta.set_placeholder_text("track.txt")

        # Record checkbox
        self.record_cb = lv.checkbox(self.scr)
        self.record_cb.set_text("Record track")
        self.record_cb.align_to(title, lv.ALIGN.OUT_BOTTOM_MID, 0, 10)

        if False:
            # Status label
            self.status = lv.label(self.scr)
            self.status.set_text("")
            self.status.align(lv.ALIGN.TOP_MID, 0, 10)

        # Apply button
        apply_btn = lv.button(self.scr)
        apply_btn.set_size(120, 50)
        apply_btn.align(lv.ALIGN.BOTTOM_RIGHT, -20, -5)
        apply_btn.add_event_cb(self.on_apply, lv.EVENT.CLICKED, None)

        lbl_apply = lv.label(apply_btn)
        lbl_apply.set_text("Apply")
        lbl_apply.center()

        # Back button
        back_btn = lv.button(self.scr)
        back_btn.set_size(120, 50)
        back_btn.align(lv.ALIGN.BOTTOM_LEFT, 20, -5)
        back_btn.add_event_cb(self.on_back, lv.EVENT.CLICKED, None)

        lbl_back = lv.label(back_btn)
        lbl_back.set_text("Back")
        lbl_back.center()

        if False:
            keyboard = MposKeyboard(self.scr)
            keyboard.set_textarea(self.pos_ta)
        else:
            keyboard = lv.keyboard(self.scr)
            keyboard.set_textarea(self.pos_ta)
            

        self.setContentView(self.scr)

    def onResume(self, screen):
        pass

    def on_back(self, e):
        self.finish()

    def load(self):
        lv.scr_load(self.scr)

