from mpos import Activity, MposKeyboard

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

class Main(Activity):
    def __init__(self, filename = "delme.txt"):
        self.filename = filename
        self.lines = []
        self.modified = False
        self.cursor = 0

     # --------------------

    def onCreate(self):
        self.load_file()
        self.build_ui()
        self.setContentView(self.scr)

    def onResume(self, screen):
        self.render_lines()

    def onPause(self, screen):
        pass

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
        self.scr = lv.obj()
        self.scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Header
        if False:
            header = lv.obj(self.scr)
            header.set_size(lv.pct(100), 50)
            header.align(lv.ALIGN.TOP_MID, 0, 25)
            header.set_flex_flow(lv.FLEX_FLOW.ROW)
            header.remove_flag(lv.obj.FLAG.SCROLLABLE)
            
            self.header_label = lv.label(header)
            self.update_header()

            btn_save = lv.button(header)
            btn_save.add_event_cb(self.save_file, lv.EVENT.CLICKED, None)
            lv.label(btn_save).set_text("Save")

            if False:
                btn_quit = lv.button(header)
                btn_quit.add_event_cb(self.quit_app, lv.EVENT.CLICKED, None)
                lv.label(btn_quit).set_text("Quit")

        # Line list (scrollable)
        self.list_container = lv.list(self.scr)
        self.list_container.set_size(lv.pct(100), lv.pct(80))
        #self.list_container.align_to(header, lv.ALIGN.OUT_BOTTOM_MID, 0, 5)
        self.list_container.align(lv.ALIGN.TOP_MID, 0, 25)
        self.list_container.set_scroll_dir(lv.DIR.VER)

        # Bottom action bar
        footer = lv.obj(self.scr)
        footer.set_size(lv.pct(100), 50)
        footer.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        footer.set_flex_flow(lv.FLEX_FLOW.ROW)
        footer.remove_flag(lv.obj.FLAG.SCROLLABLE)

        btn_edit = lv.button(footer)
        btn_edit.add_event_cb(self.edit_selected, lv.EVENT.CLICKED, None)
        lv.label(btn_edit).set_text("Ed")

        btn_insert = lv.button(footer)
        btn_insert.add_event_cb(self.insert_line, lv.EVENT.CLICKED, None)
        lv.label(btn_insert).set_text("Ins")

        btn_delete = lv.button(footer)
        btn_delete.add_event_cb(self.delete_line, lv.EVENT.CLICKED, None)
        lv.label(btn_delete).set_text("Del")

        btn_more = lv.button(footer)
        btn_more.add_event_cb(self.save_file, lv.EVENT.CLICKED, None)
        lv.label(btn_more).set_text("Save")
        
        btn_up = lv.button(footer)
        btn_up.add_event_cb(lambda x: self.move(-1), lv.EVENT.CLICKED, None)
        lv.label(btn_up).set_text("^")

        btn_down = lv.button(footer)
        btn_down.add_event_cb(lambda x: self.move(1), lv.EVENT.CLICKED, None)
        lv.label(btn_down).set_text("v")
        
    def update_header(self):
        if False:
            mark = " [+]" if self.modified else ""
            self.header_label.set_text(self.filename + mark)

    # -----------------------
    # Line Rendering
    # -----------------------

    def render_lines(self):
        self.list_container.clean()

        for idx, text in enumerate(self.lines):
            s = text
            if self.cursor == idx:
                s = "==>> " + s
            self.list_container.add_text(s)

    def select_line(self, idx):
        self.cursor = idx
        self.render_lines()

    # -----------------------
    # Operations
    # -----------------------

    def move(self, val):
        print("Move...", val)
        self.cursor += val
        self.render_lines()

    def edit_selected(self, e=None):
        print("Edit...")
        idx = self.cursor

        popup = lv.obj(self.scr)
        popup.set_size(lv.pct(100), lv.pct(100))
        popup.center()

        ta = lv.textarea(popup)
        ta.set_width(lv.pct(100))
        ta.set_text(self.lines[idx])
        ta.set_one_line(True)
        ta.align(lv.ALIGN.TOP_MID, 0, 2)

        btn_ok = lv.button(popup)
        btn_ok.align_to(ta, lv.ALIGN.OUT_BOTTOM_RIGHT, -30, 10)
        lv.label(btn_ok).set_text("OK")

        btn_cancel = lv.button(popup)
        btn_cancel.align_to(ta, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 10)
        lv.label(btn_cancel).set_text("Cancel")

        keyboard = MposKeyboard(popup)
        keyboard.set_textarea(ta)

        def save_edit(e):
            self.lines[idx] = ta.get_text()
            self.modified = True
            popup.delete()
            self.render_lines()
            self.update_header()

        btn_ok.add_event_cb(save_edit, lv.EVENT.CLICKED, None)
        btn_cancel.add_event_cb(lambda e: popup.delete(), lv.EVENT.CLICKED, None)

    def insert_line(self, e=None):
        print("Insert...")
        self.lines.insert(self.cursor + 1, "")
        self.modified = True
        self.render_lines()
        self.update_header()

    def delete_line(self, e=None):
        print("Delete...")
        if len(self.lines) > 1:
            self.lines.pop(self.cursor)
            if self.cursor >= len(self.lines):
                self.cursor = len(self.lines) - 1
            self.modified = True
            self.render_lines()
            self.update_header()

    def quit_app(self, e=None):
        self.scr.clean()


