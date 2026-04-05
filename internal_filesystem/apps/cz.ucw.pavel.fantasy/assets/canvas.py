import lvgl as lv
import mpos
from mpos import Activity, MposKeyboard, InputManager


# -----------------------------
# Canvas (LVGL)
# -----------------------------

class Canvas:
    """
    LVGL canvas + layer drawing Canvas.

    This matches ports where:
      - lv.canvas has init_layer() / finish_layer()
      - primitives are drawn via lv.draw_* into lv.layer_t
    """

    def __init__(self, scr, canvas):
        self.scr = scr

        # Screen size
        self.W = scr.get_width()
        self.H = scr.get_height()

        # Canvas drawing area (everything above button bar)
        self.draw_w = self.W
        self.draw_h = self.H

        # This is ratio Samsung s4 mini uses, should allow integer scaling
        self.draw_w = 180
        self.draw_h = 320

        self.canvas = canvas
        self.canvas.set_size(self.draw_w, self.draw_h)
        self.canvas.align(lv.ALIGN.TOP_LEFT, 0, 25)
        self.canvas.set_style_border_width(0, 0)

        # Background: white (change if you want dark theme)
        self.canvas.set_style_bg_color(lv.color_white(), lv.PART.MAIN)

        # Buffer: your working example uses 4 bytes/pixel
        # Reality filter: this depends on LV_COLOR_DEPTH; but your example proves it works.
        self.buf = bytearray(self.draw_w * self.draw_h * 4)
        self.canvas.set_buffer(self.buf, self.draw_w, self.draw_h, lv.COLOR_FORMAT.ARGB8888)

        print(dir(self.canvas))
        
        self.canvas.set_style_transform_scale(256 * 2, 0)

        # Layer used for draw engine
        self.layer = lv.layer_t()
        self.canvas.init_layer(self.layer)

        self.dragging = {"active": False, "last_x": 0, "last_y": 0}
        self.canvas.add_flag(lv.obj.FLAG.CLICKABLE)
        self.canvas.add_event_cb(self.touch_cb, lv.EVENT.ALL, None)

        # Clear once
        self.clear()
        for i in range(self.draw_w):
            self.put_pixel(i, i, 255, 0, 0)
            self.put_pixel(i, self.draw_h-i-1, 255, 0, 0)
            self.put_pixel(i, self.draw_h//2, 0, 255, 0)
        for i in range(self.draw_h):
            self.put_pixel(self.draw_w//2, i, 0, 0, 255)


    # --- Event handler ---
    def touch_cb(self, event):
        event_code=event.get_code()
	if event_code not in [19,23,25,26,27,28,29,30,49]:
            if event_code == lv.EVENT.PRESSING: # this is probably enough       
                x, y = InputManager.pointer_xy()
                print("Pressing", x, y)
                self.put_pixel(x,y, 128,128,128)
                self.update()
		return
        
        if event == lv.EVENT.PRESSED:
            point = lv.point_t()
            print("Touch:", point)
            obj.get_act_point(point)  # gets touch point relative to canvas
            self.dragging["active"] = True
            self.dragging["last_x"] = point.x
            self.dragging["last_y"] = point.y

        elif event == lv.EVENT.RELEASED:
            self.dragging["active"] = False

        elif False: # event == lv.EVENT.MOVED and dragging["active"]:
            point = lv.point_t()
            obj.get_act_point(point)
            dx = point.x - dragging["last_x"]
            dy = point.y - dragging["last_y"]
            self.dragging["last_x"] = point.x
            self.dragging["last_y"] = point.y

        print(self.dragging, event)

    # ----------------------------
    # Layer lifecycle
    # ----------------------------

    def _begin(self):
        # Start drawing into the layer
        self.canvas.init_layer(self.layer)

    def _end(self):
        # Commit drawing
        self.canvas.finish_layer(self.layer)

    # ----------------------------
    # Public API: drawing
    # ----------------------------

    def put_pixel(self, x, y, r, g, b):
        i = (y * self.draw_w + x) * 4
        self.buf[i] = b
        self.buf[i+1] = g
        self.buf[i+2] = r
        self.buf[i+3] = 255

    def clear(self):
        # Clear the canvas background
        self.canvas.fill_bg(lv.color_white(), lv.OPA.COVER)

    def update(self):
        self.canvas.invalidate()
        # Nothing needed; drawing is committed per primitive.
        # If you want, you can change the implementation so that:
        # - draw ops happen between clear() and update()
        # But then you must ensure the app calls update() once per frame.
        pass

# ----------------------------
# App logic
# ----------------------------

class CanvasActivity(Activity):
    def __init__(self):
        super().__init__()
        self.page = 0
        self.pages = 3

    def onCreate(self):
        self.scr = lv.obj()
        scr = self.scr

        # Screen size
        self.W = scr.get_width()
        self.H = scr.get_height()

        # Canvas drawing area
        self.draw_w = self.W
        self.draw_h = self.H

        # Canvas
        self.canvas = lv.canvas(self.scr)
        
        self.c = Canvas(self.scr, self.canvas)
        
        # Build buttons
        self.setContentView(self.c.scr)

    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, 1000, None)

    def onPause(self, screen):
        if self.timer:
            self.timer.delete()
            self.timer = None
            
    def tick(self, t):
        self.update()
        self.draw()

    def update(self):
        pass

    def draw_page_example(self):
        pass

    def draw(self):
        self.draw_page_example()
