from mpos import Activity

"""
Micropythonos, research/write an application to edit text files, using available resources. You may need to do something like vi.

Take a look at lvgl, it has input field, and you may want to research, but I have not seen multiline editor so far. So you'll want to do multiline display with buttons such as delete line, insert line here, and edit this line, then take advantage of built-in field editor to edit simple line. Feel free to assume file fits in memory.
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


#!/usr/bin/env micropython
import lvgl as lv
import os

class TouchTextEditor:
    def __init__(self, filename):
        self.filename = filename
        self.lines = []
        self.modified = False
        self.selected_index = 0

        self.load_file()
        self.build_ui()
        self.render_lines()

    # -----------------------
    # File Handling
    # -----------------------

    def load_file(self):
        try:
            with open(self.filename, "r") as f:
                self.lines = [l.rstrip("\n") for l in f]
        except:
            self.lines = [""]
        if not self.lines:
            self.lines = [""]

    def save_file(self, e=None):
        with open(self.filename, "w") as f:
            for l in self.lines:
                f.write(l + "\n")
        self.modified = False
        self.update_header()

    # -----------------------
    # UI
    # -----------------------

    def build_ui(self):
        self.scr = lv.scr_act()

        # Header
        header = lv.obj(self.scr)
        header.set_size(lv.pct(100), 30)
        header.align(lv.ALIGN.TOP_MID, 0, 0)
        header.set_flex_flow(lv.FLEX_FLOW.ROW)

        self.header_label = lv.label(header)
        self.update_header()

        btn_save = lv.btn(header)
        btn_save.add_event_cb(self.save_file, lv.EVENT.CLICKED, None)
        lv.label(btn_save).set_text("Save")

        btn_quit = lv.btn(header)
        btn_quit.add_event_cb(self.quit_app, lv.EVENT.CLICKED, None)
        lv.label(btn_quit).set_text("Quit")

        # Line list (scrollable)
        self.list_container = lv.obj(self.scr)
        self.list_container.set_size(lv.pct(100), 170)
        self.list_container.align(lv.ALIGN.TOP_MID, 0, 35)
        self.list_container.set_scroll_dir(lv.DIR.VER)
        self.list_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)

        # Bottom action bar
        footer = lv.obj(self.scr)
        footer.set_size(lv.pct(100), 40)
        footer.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        footer.set_flex_flow(lv.FLEX_FLOW.ROW)

        btn_edit = lv.btn(footer)
        btn_edit.add_event_cb(self.edit_selected, lv.EVENT.CLICKED, None)
        lv.label(btn_edit).set_text("Edit")

        btn_insert = lv.btn(footer)
        btn_insert.add_event_cb(self.insert_line, lv.EVENT.CLICKED, None)
        lv.label(btn_insert).set_text("Insert")

        btn_delete = lv.btn(footer)
        btn_delete.add_event_cb(self.delete_line, lv.EVENT.CLICKED, None)
        lv.label(btn_delete).set_text("Delete")

    def update_header(self):
        mark = " [+]" if self.modified else ""
        self.header_label.set_text(self.filename + mark)

    # -----------------------
    # Line Rendering
    # -----------------------

    def render_lines(self):
        self.list_container.clean()

        for idx, text in enumerate(self.lines):
            row = lv.label(self.list_container)
            row.set_width(lv.pct(100))
            row.set_long_mode(lv.label.LONG.DOT)
            row.set_text(text)

            if idx == self.selected_index:
                row.add_state(lv.STATE.CHECKED)

            row.add_event_cb(
                lambda e, i=idx: self.select_line(i),
                lv.EVENT.CLICKED,
                None
            )

    def select_line(self, idx):
        self.selected_index = idx
        self.render_lines()

    # -----------------------
    # Operations
    # -----------------------

    def edit_selected(self, e=None):
        idx = self.selected_index

        popup = lv.obj(self.scr)
        popup.set_size(280, 120)
        popup.center()

        ta = lv.textarea(popup)
        ta.set_width(lv.pct(100))
        ta.set_text(self.lines[idx])
        ta.set_one_line(True)

        btn_ok = lv.btn(popup)
        btn_ok.align(lv.ALIGN.BOTTOM_LEFT, 0, 0)
        lv.label(btn_ok).set_text("OK")

        btn_cancel = lv.btn(popup)
        btn_cancel.align(lv.ALIGN.BOTTOM_RIGHT, 0, 0)
        lv.label(btn_cancel).set_text("Cancel")

        def save_edit(e):
            self.lines[idx] = ta.get_text()
            self.modified = True
            popup.delete()
            self.render_lines()
            self.update_header()

        btn_ok.add_event_cb(save_edit, lv.EVENT.CLICKED, None)
        btn_cancel.add_event_cb(lambda e: popup.delete(), lv.EVENT.CLICKED, None)

    def insert_line(self, e=None):
        self.lines.insert(self.selected_index + 1, "")
        self.modified = True
        self.render_lines()
        self.update_header()

    def delete_line(self, e=None):
        if len(self.lines) > 1:
            self.lines.pop(self.selected_index)
            if self.selected_index >= len(self.lines):
                self.selected_index = len(self.lines) - 1
            self.modified = True
            self.render_lines()
            self.update_header()

    def quit_app(self, e=None):
        self.scr.clean()

# Launch
TouchTextEditor("test.txt")

