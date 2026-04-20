import lvgl as lv
import mpos
from mpos import Activity, MposKeyboard, InputManager

"""

Give me code in Python, for tic-80, using its documented
interfaces. Difference will be that code should be in separate class,
and tic interfaces should be called as self.

Notice you'll need to use state machines, as TIC() is not supposed to block,
and initialization should go to BOOT() function.

"""

import time
import random

# -----------------------------
# Canvas (LVGL)
# -----------------------------

class Color:
    def __init__(self, r,g,b):
        self.r = r
        self.g = g
        self.b = b

    def __repr__(self):
        return f"Color({self.r}, {self.g}, {self.b})"
    
class Canvas:
    """
    LVGL canvas + layer drawing Canvas.

    This matches ports where:
      - lv.canvas has init_layer() / finish_layer()
      - primitives are drawn via lv.draw_* into lv.layer_t
    """

    def __init__(self, scr, canvas):
        self.scr = scr

        self.start_time = time.time()
        self.clip_rect = None

        # Screen size
        self.W = scr.get_width()
        self.H = scr.get_height()

        # Canvas drawing area (everything above button bar)
        self.width = self.W
        self.height = self.H

        # This is ratio Samsung s4 mini uses, should allow integer scaling
        self.width = 180*2
        self.height = 320*2
        self.bpp = 4
        self.scale = 4
        self.width = self.width // self.scale
        self.height = self.height // self.scale

        self.canvas = canvas
        self.canvas.set_size(self.width, self.height)
        self.canvas.align(lv.ALIGN.TOP_LEFT, 0, 25)
        self.canvas.set_style_border_width(0, 0)

        # Background: white (change if you want dark theme)
        self.canvas.set_style_bg_color(lv.color_white(), lv.PART.MAIN)

        # Buffer: your working example uses 4 bytes/pixel
        # Reality filter: this depends on LV_COLOR_DEPTH; but your example proves it works.
        if self.bpp == 4:
            self.buf = bytearray(self.width * self.height * self.bpp)
            self.canvas.set_buffer(self.buf, self.width, self.height, lv.COLOR_FORMAT.ARGB8888)
        else:
            self.buf = bytearray(self.width * self.height * self.bpp)
            # Palette is available
            #self.canvas.set_buffer(self.buf, self.width, self.height, lv.COLOR_FORMAT.I8)
            self.canvas.set_buffer(self.buf, self.width, self.height, lv.COLOR_FORMAT.L8)

        self.canvas.set_style_transform_scale(256 * self.scale, 0)

        # Layer used for draw engine
        self.layer = lv.layer_t()
        self.canvas.init_layer(self.layer)

        self.dragging = {"active": False, "last_x": 0, "last_y": 0}
        self.last_dragging = False
        self.canvas.add_flag(lv.obj.FLAG.CLICKABLE)
        self.canvas.add_event_cb(self.touch_cb, lv.EVENT.ALL, None)

        # Clear once
        self.clear()
        for i in range(self.width):
            self.put_pixel(i, i, Color(255, 0, 0))
            self.put_pixel(i, self.height-i-1, Color(255, 0, 0))
            self.put_pixel(i, self.height//2, Color(0, 255, 0))
        for i in range(self.height):
            self.put_pixel(self.width//2, i, Color(0, 0, 255))

        self.BOOT()

    # --- Event handler ---
    def touch_cb(self, event):
        event_code=event.get_code()
	#if event_code not in [19,23,25,26,27,28,29,30,49]:
        if event_code == lv.EVENT.PRESSING: # this is probably enough       
            x, y = InputManager.pointer_xy()
            if not x and not y: # FIXME: some kind of bogosity?
                return
            print("Pressing", x, y)
            x /= self.scale
            y /= self.scale
            self.put_pixel(x, y, Color(128,128,128))
            self.dragging["active"] = True
            self.dragging["last_x"] = int(x)
            self.dragging["last_y"] = int(y)
            self.canvas_update()
            return
        if event_code == lv.EVENT.RELEASED:
            print("Released")
            self.dragging["active"] = False
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

    def put_pixel_nocheck(self, x, y, c):
        i = (y * self.width + x) * self.bpp
        if self.bpp == 4:
            self.buf[i] = c.b
            self.buf[i+1] = c.g
            self.buf[i+2] = c.r
            self.buf[i+3] = 255
        else:
            self.buf[i] = (c.b + c.g + c.r) // 3

    def put_pixel(self, x, y, c):
        x = int(x)
        y = int(y)
        if x < 0 or x >= self.width:
            return
        if y < 0 or y >= self.height:
            return
        self.put_pixel_nocheck(x, y, c)

    def clear(self):
        # Clear the canvas background
        self.canvas.fill_bg(lv.color_white(), lv.OPA.COVER)

    def canvas_update(self):
        self.canvas.invalidate()
        # Nothing needed; drawing is committed per primitive.
        # If you want, you can change the implementation so that:
        # - draw ops happen between clear() and update()
        # But then you must ensure the app calls update() once per frame.
        pass

    def debug(self, s):
        print(s)
    
# --- Shared with Android app

class Tic(Canvas):
    """
    Trick with direct exec of tic80-code might be feasible, something like

    6. exec hack (⚠️ not recommended)

        exec(\"\"\"
        x = 10
        y = 20
        \"\"\", {}, self.__dict__)

        👉 This actually lets you write code without self.

        BUT:
        hard to debug
        unsafe if input is dynamic
        no IDE support    
            ...

    LVGL should be able to do indexed 4 -- I4 -- palette.

    API description is at:
        https://tic80.com/learn


### BOOT
`BOOT`
Startup function.

### TIC
`TIC()`
Main function. It's called at 60fps (60 times every second).

### btn
`btn(id) -> pressed`
This function allows you to read the status of one of the buttons attached to TIC.
The function returns true if the key with the supplied id is currently in the pressed state.
It remains true for as long as the key is held down.
If you want to test if a key was just pressed, use `btnp()` instead.

### btnp
`btnp(id hold=-1 period=-1) -> pressed`
This function allows you to read the status of one of TIC's buttons.
It returns true only if the key has been pressed since the last frame.
You can also use the optional hold and period parameters which allow you to check if a button is being held down.
After the time specified by hold has elapsed, btnp will return true each time period is passed if the key is still down.
For example, to re-examine the state of button `0` after 2 seconds and continue to check its state every 1/10th of a second, you would use btnp(0, 120, 6).
Since time is expressed in ticks and TIC runs at 60 frames per second, we use the value of 120 to wait 2 seconds and 6 ticks (ie 60/10) as the interval for re-checking.

### circ
`circ(x y radius color)`
This function draws a filled circle of the desired radius and color with its center at x, y.
It uses the Bresenham algorithm.

### circb
`circb(x y radius color)`
Draws the circumference of a circle with its center at x, y using the radius and color requested.
It uses the Bresenham algorithm.

### clip
`clip(x y width height)
noclip()`
This function limits drawing to a clipping region or `viewport` defined by x,y,w,h.
Things drawn outside of this area will not be visible.
Calling noclip() 

### cls
`cls(color=0)`
Clear the screen.
When called this function clear all the screen using the color passed as argument.
If no parameter is passed first color (0) is used.

### elli
`elli(x y a b color)`
This function draws a filled ellipse of the desired a, b radiuses and color with its center at x, y.
It uses the Bresenham algorithm.

### ellib
`ellib(x y a b color)`
This function draws an ellipse border with the desired radiuses a b and color with its center at x, y.
It uses the Bresenham algorithm.

### exit
`exit()`
Interrupts program execution and returns to the console when the TIC function ends.

### key
`key(code=-1) -> pressed`
The function returns true if the key denoted by keycode is pressed.

### keyp
`keyp(code=-1 hold=-1 period=-1) -> pressed`
This function returns true if the given key is pressed but wasn't pressed in the previous frame.
Refer to `btnp()` for an explanation of the optional hold and period parameters.

### line
`line(x0 y0 x1 y1 color)`
Draws a straight line from point (x0,y0) to point (x1,y1) in the specified color.

### mouse
`mouse() -> x y left middle right scrollx scrolly`
This function returns the mouse coordinates and a boolean value for the state of each mouse button,with true indicating that a button is pressed.

### pix
`pix(x y color)
get_pix(x y) -> color`
This function can read or write pixel color values.
When called with a color parameter, the pixel at the specified coordinates is set to that color.

### print
`print(text x=0 y=0 color=15 fixed=false scale=1 smallfont=false) -> width`
This will simply print text to the screen using the font defined in config.
When set to true, the fixed width option ensures that each character will be printed in a `box` of the same size, so the character `i` will occupy the same width as the character `w` for example.
When fixed width is false, there will be a single space between each character.

### rect
`rect(x y w h color)`
This function draws a filled rectangle of the desired size and color at the specified position.
If you only need to draw the the border or outline of a rectangle (ie not filled) see `rectb()`.

### rectb
`rectb(x y w h color)`
This function draws a one pixel thick rectangle border at the position requested.
If you need to fill the rectangle with a color, see `rect()` instead.



### time
`time() -> ticks`
This function returns the number of milliseconds elapsed since the cartridge began execution.
Useful for keeping track of time, animating items and triggering events.

### trace
`trace(message color=15)`
This is a service function, useful for debugging your code.
It prints the message parameter to the console in the (optional) color specified.

### tri
`tri(x1 y1 x2 y2 x3 y3 color)`
This function draws a triangle filled with color, using the supplied vertices.

### trib
`trib(x1 y1 x2 y2 x3 y3 color)`
This function draws a triangle border with color, using the supplied vertices.

### tstamp
`tstamp() -> timestamp`
This function returns the number of seconds elapsed since January 1st, 1970.
Useful for creating persistent games which evolve over time between plays.
        
    """

    def BOOT(self):
        pass

    def TIC(self):
        pass
    
    def _in_clip(self, x, y):
        if self.clip_rect is None:
            return 0 <= x < self.width and 0 <= y < self.height
        cx, cy, cw, ch = self.clip_rect
        return (cx <= x < cx + cw) and (cy <= y < cy + ch)


    def pix(self, x, y, color=None):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None

        if color is None:
            return self.pixels[y][x]

        if type(color) is int:
            color = self.tc(color)

        if self._in_clip(x, y):
            self.put_pixel_nocheck(x, y, color)

    def get_pix(self, x, y):
        return self.pix(x, y)

    def clip(self, x, y, w, h):
        self.clip_rect = (x, y, w, h)

    def noclip(self):
        self.clip_rect = None

    def cls(self, color=0):
        color = self.tc(color)
        for y in range(self.height):
            for x in range(self.width):
                self.put_pixel_nocheck(x, y, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            self.pix(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def rect(self, x, y, w, h, color):
        color = self.tc(color)
        for j in range(y, y + h):
            for i in range(x, x + w):
                self.pix(i, j, color)


    def rectb(self, x, y, w, h, color):
        for i in range(x, x + w):
            self.pix(i, y, color)
            self.pix(i, y + h - 1, color)

        for j in range(y, y + h):
            self.pix(x, j, color)
            self.pix(x + w - 1, j, color)

    def _hline(self, x0, x1, y, color):
        if x0 > x1:
            x0, x1 = x1, x0

        for x in range(x0, x1 + 1):
            self.pix(x, y, color)

    def circ(self, cx, cy, r, color):
        x = r
        y = 0
        err = 0

        while x >= y:
            # Draw horizontal spans between symmetric points
            self._hline(cx - x, cx + x, cy + y, color)
            self._hline(cx - x, cx + x, cy - y, color)
            self._hline(cx - y, cx + y, cy + x, color)
            self._hline(cx - y, cx + y, cy - x, color)

            y += 1

            if err <= 0:
                err += 2 * y + 1
            if err > 0:
                x -= 1
                err -= 2 * x + 1

    def circb(self, cx, cy, r, color):
        x = r
        y = 0
        err = 0

        while x >= y:
            pts = [
                (cx + x, cy + y), (cx + y, cy + x),
                (cx - y, cy + x), (cx - x, cy + y),
                (cx - x, cy - y), (cx - y, cy - x),
                (cx + y, cy - x), (cx + x, cy - y),
            ]
            for px, py in pts:
                self.pix(px, py, color)

            y += 1
            if err <= 0:
                err += 2*y + 1
            if err > 0:
                x -= 1
                err -= 2*x + 1

    def ellib(self, cx, cy, a, b, color):
        x = 0
        y = b

        a2 = a * a
        b2 = b * b

        d1 = b2 - a2 * b + 0.25 * a2
        dx = 2 * b2 * x
        dy = 2 * a2 * y

        # Region 1
        while dx < dy:
            self._plot_ellipse_points(cx, cy, x, y, color)
            if d1 < 0:
                x += 1
                dx += 2 * b2
                d1 += dx + b2
            else:
                x += 1
                y -= 1
                dx += 2 * b2
                dy -= 2 * a2
                d1 += dx - dy + b2

        # Region 2
        d2 = (b2 * (x + 0.5)**2) + (a2 * (y - 1)**2) - (a2 * b2)

        while y >= 0:
            self._plot_ellipse_points(cx, cy, x, y, color)
            if d2 > 0:
                y -= 1
                dy -= 2 * a2
                d2 += a2 - dy
            else:
                y -= 1
                x += 1
                dx += 2 * b2
                dy -= 2 * a2
                d2 += dx - dy + a2


    def _plot_ellipse_points(self, cx, cy, x, y, color):
        pts = [
            (cx + x, cy + y), (cx - x, cy + y),
            (cx + x, cy - y), (cx - x, cy - y),
        ]
        for px, py in pts:
            self.pix(px, py, color)

    def elli(self, cx, cy, a, b, color):
        for y in range(-b, b + 1):
            # Solve ellipse equation for x span
            x_span = int(a * (1 - (y*y)/(b*b))**0.5)
            for x in range(-x_span, x_span + 1):
                self.pix(cx + x, cy + y, color)

    def tri(self, x1, y1, x2, y2, x3, y3, color):
        pts = sorted([(x1,y1), (x2,y2), (x3,y3)], key=lambda p: p[1])
        (x1,y1), (x2,y2), (x3,y3) = pts

        def interp(y, y0, x0, y1, x1):
            if y1 == y0:
                return x0
            return int(x0 + (x1 - x0) * (y - y0) / (y1 - y0))

        for y in range(y1, y3 + 1):
            if y < y2:
                xa = interp(y, y1, x1, y3, x3)
                xb = interp(y, y1, x1, y2, x2)
            else:
                xa = interp(y, y1, x1, y3, x3)
                xb = interp(y, y2, x2, y3, x3)

            if xa > xb:
                xa, xb = xb, xa

            for x in range(xa, xb + 1):
                self.pix(x, y, color)

    def trib(self, x1, y1, x2, y2, x3, y3, color):
        self.line(x1, y1, x2, y2, color)
        self.line(x2, y2, x3, y3, color)
        self.line(x3, y3, x1, y1, color)

    def time(self):
        return int((time.time() - self.start_time) * 1000)

    def tstamp(self):
        return int(time.time())

    def trace(self, message, color=15):
        print(f"[{color}] {message}")

    TIC80_FONT = {
        ' ': [0b0000,0b0000,0b0000,0b0000,0b0000,0b0000],
        '!': [0b0100,0b0100,0b0100,0b0100,0b0000,0b0100],
        '"': [0b1010,0b1010,0b0000,0b0000,0b0000,0b0000],
        '#': [0b1010,0b1111,0b1010,0b1111,0b1010,0b0000],
        '$': [0b0111,0b1100,0b0110,0b0011,0b1110,0b0100],
        '%': [0b1001,0b0010,0b0100,0b1000,0b1001,0b0000],
        '&': [0b0110,0b1001,0b0110,0b1001,0b0110,0b0000],
        "'": [0b0100,0b0100,0b0000,0b0000,0b0000,0b0000],
        '(': [0b0010,0b0100,0b0100,0b0100,0b0010,0b0000],
        ')': [0b0100,0b0010,0b0010,0b0010,0b0100,0b0000],
        '*': [0b0000,0b1010,0b0110,0b0110,0b1010,0b0000],
        '+': [0b0000,0b0100,0b1110,0b0100,0b0000,0b0000],
        ',': [0b0000,0b0000,0b0000,0b0100,0b0100,0b1000],
        '-': [0b0000,0b0000,0b1110,0b0000,0b0000,0b0000],
        '.': [0b0000,0b0000,0b0000,0b0000,0b1100,0b1100],
        '/': [0b0001,0b0010,0b0100,0b1000,0b0000,0b0000],

        '0': [0b0110,0b1001,0b1011,0b1101,0b1001,0b0110],
        '1': [0b0010,0b0110,0b0010,0b0010,0b0010,0b0111],
        '2': [0b0110,0b1001,0b0001,0b0010,0b0100,0b1111],
        '3': [0b1110,0b0001,0b0110,0b0001,0b0001,0b1110],
        '4': [0b0001,0b0011,0b0101,0b1111,0b0001,0b0001],
        '5': [0b1111,0b1000,0b1110,0b0001,0b0001,0b1110],
        '6': [0b0111,0b1000,0b1110,0b1001,0b1001,0b0110],
        '7': [0b1111,0b0001,0b0010,0b0100,0b0100,0b0100],
        '8': [0b0110,0b1001,0b0110,0b1001,0b1001,0b0110],
        '9': [0b0110,0b1001,0b1001,0b0111,0b0001,0b1110],

        ':': [0b0000,0b1100,0b1100,0b0000,0b1100,0b1100],
        ';': [0b0000,0b1100,0b1100,0b0000,0b1100,0b0100],
        '<': [0b0010,0b0100,0b1000,0b0100,0b0010,0b0000],
        '=': [0b0000,0b1110,0b0000,0b1110,0b0000,0b0000],
        '>': [0b0100,0b0010,0b0001,0b0010,0b0100,0b0000],
        '?': [0b1110,0b0001,0b0010,0b0100,0b0000,0b0100],
        '@': [0b0110,0b1001,0b1011,0b1011,0b1000,0b0111],

        'A': [0b0110,0b1001,0b1001,0b1111,0b1001,0b1001],
        'B': [0b1110,0b1001,0b1110,0b1001,0b1001,0b1110],
        'C': [0b0111,0b1000,0b1000,0b1000,0b1000,0b0111],
        'D': [0b1110,0b1001,0b1001,0b1001,0b1001,0b1110],
        'E': [0b1111,0b1000,0b1110,0b1000,0b1000,0b1111],
        'F': [0b1111,0b1000,0b1110,0b1000,0b1000,0b1000],
        'G': [0b0111,0b1000,0b1000,0b1011,0b1001,0b0111],
        'H': [0b1001,0b1001,0b1111,0b1001,0b1001,0b1001],
        'I': [0b1110,0b0100,0b0100,0b0100,0b0100,0b1110],
        'J': [0b0011,0b0001,0b0001,0b0001,0b1001,0b0110],
        'K': [0b1001,0b1010,0b1100,0b1010,0b1001,0b1001],
        'L': [0b1000,0b1000,0b1000,0b1000,0b1000,0b1111],
        'M': [0b1001,0b1111,0b1111,0b1001,0b1001,0b1001],
        'N': [0b1001,0b1101,0b1011,0b1001,0b1001,0b1001],
        'O': [0b0110,0b1001,0b1001,0b1001,0b1001,0b0110],
        'P': [0b1110,0b1001,0b1001,0b1110,0b1000,0b1000],
        'Q': [0b0110,0b1001,0b1001,0b1001,0b1010,0b0101],
        'R': [0b1110,0b1001,0b1001,0b1110,0b1010,0b1001],
        'S': [0b0111,0b1000,0b0110,0b0001,0b0001,0b1110],
        'T': [0b1111,0b0100,0b0100,0b0100,0b0100,0b0100],
        'U': [0b1001,0b1001,0b1001,0b1001,0b1001,0b0110],
        'V': [0b1001,0b1001,0b1001,0b1001,0b0101,0b0010],
        'W': [0b1001,0b1001,0b1001,0b1111,0b1111,0b1001],
        'X': [0b1001,0b1001,0b0110,0b0110,0b1001,0b1001],
        'Y': [0b1001,0b1001,0b0110,0b0100,0b0100,0b0100],
        'Z': [0b1111,0b0001,0b0010,0b0100,0b1000,0b1111],

        '[': [0b0110,0b0100,0b0100,0b0100,0b0100,0b0110],
        '\\': [0b1000,0b0100,0b0010,0b0001,0b0000,0b0000],
        ']': [0b0110,0b0010,0b0010,0b0010,0b0010,0b0110],
        '^': [0b0100,0b1010,0b0000,0b0000,0b0000,0b0000],
        '_': [0b0000,0b0000,0b0000,0b0000,0b0000,0b1111],
        '`': [0b0100,0b0010,0b0000,0b0000,0b0000,0b0000],

        'a': [0b0000,0b0110,0b0001,0b0111,0b1001,0b0111],
        'b': [0b1000,0b1000,0b1110,0b1001,0b1001,0b1110],
        'c': [0b0000,0b0111,0b1000,0b1000,0b1000,0b0111],
        'd': [0b0001,0b0001,0b0111,0b1001,0b1001,0b0111],
        'e': [0b0000,0b0110,0b1001,0b1111,0b1000,0b0111],
        'f': [0b0011,0b0100,0b1110,0b0100,0b0100,0b0100],
        'g': [0b0000,0b0111,0b1001,0b0111,0b0001,0b1110],
        'h': [0b1000,0b1000,0b1110,0b1001,0b1001,0b1001],
        'i': [0b0100,0b0000,0b1100,0b0100,0b0100,0b1110],
        'j': [0b0010,0b0000,0b0110,0b0010,0b0010,0b1100],
        'k': [0b1000,0b1001,0b1010,0b1100,0b1010,0b1001],
        'l': [0b1100,0b0100,0b0100,0b0100,0b0100,0b1110],
        'm': [0b0000,0b1110,0b1111,0b1011,0b1011,0b1011],
        'n': [0b0000,0b1110,0b1001,0b1001,0b1001,0b1001],
        'o': [0b0000,0b0110,0b1001,0b1001,0b1001,0b0110],
        'p': [0b0000,0b1110,0b1001,0b1110,0b1000,0b1000],
        'q': [0b0000,0b0111,0b1001,0b0111,0b0001,0b0001],
        'r': [0b0000,0b1011,0b1100,0b1000,0b1000,0b1000],
        's': [0b0000,0b0111,0b1000,0b0110,0b0001,0b1110],
        't': [0b0100,0b1110,0b0100,0b0100,0b0100,0b0011],
        'u': [0b0000,0b1001,0b1001,0b1001,0b1001,0b0111],
        'v': [0b0000,0b1001,0b1001,0b1001,0b0101,0b0010],
        'w': [0b0000,0b1001,0b1001,0b1111,0b1111,0b0110],
        'x': [0b0000,0b1001,0b0110,0b0110,0b1001,0b1001],
        'y': [0b0000,0b1001,0b1001,0b0111,0b0001,0b1110],
        'z': [0b0000,0b1111,0b0010,0b0100,0b1000,0b1111],

        '{': [0b0011,0b0100,0b0100,0b0100,0b0100,0b0011],
        '|': [0b0100,0b0100,0b0100,0b0100,0b0100,0b0100],
        '}': [0b1100,0b0010,0b0010,0b0010,0b0010,0b1100],
        '~': [0b0000,0b0110,0b1101,0b0000,0b0000,0b0000],
    }

    def _draw_char(self, x, y, ch, color, scale):
        glyph = self.TIC80_FONT.get(ch.upper(), self.TIC80_FONT["?"])

        for row in range(6):
            bits = glyph[row]
            for col in range(4):
                if bits & (1 << (3 - col)):
                    for sy in range(scale):
                        for sx in range(scale):
                            self.pix(
                                x + col * scale + sx,
                                y + row * scale + sy,
                                color
                            )

    def print(self, text, x=0, y=0, color=15, fixed=False, scale=1, smallfont=False):
        cursor_x = x

        char_w = 4 * scale
        spacing = scale  # 1 pixel spacing scaled

        for ch in text:
            self._draw_char(cursor_x, y, ch, color, scale)

            if fixed:
                cursor_x += char_w + spacing
            else:
                cursor_x += char_w + spacing  # TIC-80 still spaces; kerning is minimal

        return cursor_x - x

    def tc(self, index):
        """Return TIC-80 default color by index 0–15"""
        
        if not type(index) is int:
            return index
        
        palette = [
            Color(0, 0, 0),         # 0: Black
            Color(29, 43, 83),      # 1: Dark Blue
            Color(126, 37, 83),     # 2: Dark Purple
            Color(0, 135, 81),      # 3: Dark Green
            Color(171, 82, 54),     # 4: Brown
            Color(95, 87, 79),      # 5: Dark Gray
            Color(194, 195, 199),   # 6: Light Gray
            Color(255, 241, 232),   # 7: White
            Color(255, 0, 77),      # 8: Red
            Color(255, 163, 0),     # 9: Orange
            Color(255, 236, 39),    # 10: Yellow
            Color(0, 228, 54),      # 11: Green
            Color(41, 173, 255),    # 12: Blue
            Color(131, 118, 156),   # 13: Indigo
            Color(255, 119, 168),   # 14: Pink
            Color(255, 204, 170),   # 15: Peach
        ]
        if 0 <= index < 16:
            return palette[index]
        else:
            raise ValueError("TIC-80 color index must be 0–15")

    def mouse(self):
        return (self.dragging["last_x"], self.dragging["last_y"], self.dragging["active"],
                False, False, False, False)

    def btnp(self, i, hold = -1, period = -1):
        return False

    def btn(self, i):
        return False

class TicButton(Tic):
    def btn(self, i):
        # 1.. down, 2,3.. l/r, 4.. up

        if not self.dragging["active"]:
            return False
        x = self.dragging["last_x"]
        y = self.dragging["last_y"]

        x = (x*2) // self.width
        y = (y*4) // self.height
        if y==3:
            if x==0 and i==2:
                return True
            if x==1 and i==3:
                return True
        if y==2:
            if x==0 and i==1:
                return True
            if x==1 and i==4:
                return True
        return False

    def btnp(self, i, hold = -1, period = -1):
        if self.last_dragging:
            return False
        return self.btn(i)
    
class TicDemo(Tic):
    def BOOT(self):
        self.test2()

    def test1(self):
        self.circ(90, 100, 80, Color(170, 170, 0))
        self.circb(90, 100, 75, Color(170, 120, 0))

        self.print("Hello, world", x=1, color=Color(0,0,0))
        self.print("Hello, world", x=1, y=20, scale=2, color=Color(0,0,0))

    def test2(self):
        api=self
        api.cls((0))

        # --- PIX ---
        for i in range(20):
            api.pix(5 + i, 5, 12)

        # --- LINE ---
        api.line(0, 0, 50, 30, (11))
        api.line(50, 0, 0, 30, (11))

        # --- RECT / RECTB ---
        api.rect(60, 5, 20, 10, (2))
        api.rectb(60, 5, 20, 10, (15))

        # --- CIRCLE ---
        api.circb(30, 60, 15, (14))
        api.circ(70, 60, 15, (6))

        # --- ELLIPSE ---
        api.ellib(120, 60, 20, 10, (13))
        api.elli(160, 60, 15, 8, (5))

        # --- TRIANGLES ---
        api.trib(10, 90, 40, 90, 25, 70, (12))
        api.tri(50, 90, 80, 90, 65, 70, (3))

        # --- CLIP TEST ---
        api.clip(100, 0, 40, 40)
        api.rect(90, 0, 80, 40, (8))   # partially clipped
        api.noclip()

        # --- TEXT ---
        api.print("HELLO TIC80", 5, 110, (15))
        api.print("123 ABC xyz", 5, 120, (10))
        api.print("SCALED", 5, 130, (14), scale=2)

        # --- TIME / TSTAMP ---
        t = api.time()
        ts = api.tstamp()
        api.print(f"time:{t}", 120, 110, (9))
        api.print(f"ts:{ts}", 120, 120, (9))

        # --- TRACE ---
        api.trace("All tests executed", 10)

    def moving_test(self):
        api = self
        api.cls(0)

        t = api.time() // 10

        # moving circle
        api.circ(60 + (t % 50), 40, 10, 6)

        # rotating triangle-ish motion
        api.tri(120, 40,
                140 + (t % 20), 60,
                100 + (t % 20), 60,
                3)

        api.print(f"t={api.time()}", 5, 5, 15)

class GamePuyo(TicButton):
    GW = 6
    GH = 12
    CELL = 10

    COLORS = [2, 3, 4, 5]

    def BOOT(self):
        self.grid = [[0]*self.GW for _ in range(self.GH)]
        self.dirty_cells = set()

        self.spawn_pair()
        self.prev_pair_cells = []

        self.tick = 0
        self.drop_delay = 5
        self.cls(1)

        print("init")
        # initial full draw (once)
        for y in range(self.GH):
            for x in range(self.GW):
                print(x, y)
                self.dirty_cells.add((x, y))
        print("init ok")

    # ---------- GAME LOGIC ----------

    def spawn_pair(self):
        import random
        self.pair = {
            "x": self.GW // 2,
            "y": 0,
            "rot": 0,
            "colors": [random.choice(self.COLORS), random.choice(self.COLORS)]
        }

    def get_pair_cells(self):
        x, y = self.pair["x"], self.pair["y"]
        r = self.pair["rot"] % 4

        if r == 0: return [(x,y),(x,y-1)]
        if r == 1: return [(x,y),(x+1,y)]
        if r == 2: return [(x,y),(x,y+1)]
        if r == 3: return [(x,y),(x-1,y)]

    def can_move(self, dx, dy, rot=None):
        old_rot = self.pair["rot"]
        if rot is not None:
            self.pair["rot"] = rot

        for (x,y) in self.get_pair_cells():
            nx, ny = x+dx, y+dy
            if nx < 0 or nx >= self.GW or ny >= self.GH:
                self.pair["rot"] = old_rot
                return False
            if ny >= 0 and self.grid[ny][nx]:
                self.pair["rot"] = old_rot
                return False

        self.pair["rot"] = old_rot
        return True

    def lock_pair(self):
        for i,(x,y) in enumerate(self.get_pair_cells()):
            if y >= 0:
                self.grid[y][x] = self.pair["colors"][i]
                self.dirty_cells.add((x,y))

        self.resolve()
        self.spawn_pair()
        self.prev_pair_cells = []

    # ---------- MATCH / GRAVITY ----------

    def resolve(self):
        visited = [[False]*self.GW for _ in range(self.GH)]
        to_clear = []

        def flood(x,y,color,group):
            if x<0 or x>=self.GW or y<0 or y>=self.GH:
                return
            if visited[y][x] or self.grid[y][x] != color:
                return
            visited[y][x] = True
            group.append((x,y))
            flood(x+1,y,color,group)
            flood(x-1,y,color,group)
            flood(x,y+1,color,group)
            flood(x,y-1,color,group)

        for y in range(self.GH):
            for x in range(self.GW):
                if self.grid[y][x] and not visited[y][x]:
                    group = []
                    flood(x,y,self.grid[y][x],group)
                    if len(group) >= 4:
                        to_clear.extend(group)

        if to_clear:
            for (x,y) in to_clear:
                self.grid[y][x] = 0
                self.dirty_cells.add((x,y))
            self.apply_gravity()
            self.resolve()

    def apply_gravity(self):
        for x in range(self.GW):
            stack = [self.grid[y][x] for y in range(self.GH) if self.grid[y][x]]
            for y in range(self.GH-1, -1, -1):
                new_val = stack.pop() if stack else 0
                if self.grid[y][x] != new_val:
                    self.grid[y][x] = new_val
                    self.dirty_cells.add((x,y))

    # ---------- UPDATE ----------

    def update(self):
        self.tick += 1

        moved = False

        if self.btnp(2) and self.can_move(-1,0):
            self.pair["x"] -= 1
            moved = True
        if self.btnp(3) and self.can_move(1,0):
            self.pair["x"] += 1
            moved = True
        if self.btnp(4) and self.can_move(0,0,self.pair["rot"]+1):
            self.pair["rot"] += 1
            moved = True

        if self.tick % self.drop_delay == 0:
            if self.can_move(0,1):
                self.pair["y"] += 1
                moved = True
            else:
                self.lock_pair()
                return

        if moved:
            self.mark_pair_dirty()

    def mark_pair_dirty(self):
        new_cells = self.get_pair_cells()

        # mark old + new cells dirty
        for c in self.prev_pair_cells:
            if c[1] >= 0:
                self.dirty_cells.add(c)
        for c in new_cells:
            if c[1] >= 0:
                self.dirty_cells.add(c)

        self.prev_pair_cells = new_cells

    # ---------- DRAW ----------

    def draw_cell(self, x, y):
        px = x * self.CELL
        py = y * self.CELL

        color = self.grid[y][x]

        # check if falling pair overlaps
        for i,(pxy,pyy) in enumerate(self.get_pair_cells()):
            if (pxy,pyy) == (x,y):
                color = self.pair["colors"][i]

        # draw background (clear cell)
        self.rect(px, py, self.CELL, self.CELL, 0)

        if color:
            self.rect(px+1, py+1, self.CELL-2, self.CELL-2, color)

    def draw(self):
        if not self.dirty_cells:
            return

        for (x,y) in self.dirty_cells:
            if 0 <= x < self.GW and 0 <= y < self.GH:
                self.draw_cell(x,y)

        self.dirty_cells.clear()

    # ---------- MAIN ----------

    def TIC(self):
        self.update()
        self.draw()
    
class GameVirus(TicButton):
    def BOOT(self):
        self.w = 8
        self.h = 16
        self.cell = 8

        self.colors = [2,3,4]

        self.grid = [[0 for _ in range(self.w)] for _ in range(self.h)]
        self.virus = [[False for _ in range(self.w)] for _ in range(self.h)]

        self.score = 0
        self.tick = 0

        self.spawn_viruses(12)
        self.spawn()

    # -------------------------
    # Setup
    # -------------------------
    def spawn_viruses(self, count):
        placed = 0
        while placed < count:
            x = random.randint(0, self.w-1)
            y = random.randint(self.h//2, self.h-1)

            if self.grid[y][x] == 0:
                col = random.choice(self.colors)
                self.grid[y][x] = col
                self.virus[y][x] = True
                placed += 1

    def spawn(self):
        def rcolor(): return random.choice(self.colors)
        def rcolor(): return self.colors[0]
        self.pill = {
            "x": 3,
            "y": 0,
            "rot": 0,
            "parts": [
                [0,0,rcolor()],
                [1,0,rcolor()]
            ]
        }

    # -------------------------
    # Helpers
    # -------------------------
    def cells(self, p):
        res = []
        for part in p["parts"]:
            x,y,c = part

            if p["rot"] == 1: x,y = -y,x
            if p["rot"] == 2: x,y = -x,-y
            if p["rot"] == 3: x,y = y,-x

            res.append((p["x"]+x, p["y"]+y, c))
        return res

    def collides(self, p):
        for x,y,_ in self.cells(p):
            if x < 0 or x >= self.w or y >= self.h:
                return True
            if y >= 0 and self.grid[y][x] != 0:
                return True
        return False

    # -------------------------
    # Lock + Clear
    # -------------------------
    def lock(self):
        for x,y,c in self.cells(self.pill):
            if y >= 0:
                self.grid[y][x] = c
                self.virus[y][x] = False

        total_cleared = self.resolve()
        self.score += total_cleared * 100

        self.spawn()

    def resolve(self):
        total = 0

        while True:
            cleared = self.clear_matches()
            if cleared == 0:
                break

            total += cleared
            self.apply_gravity()

        return total

    def clear_matches(self):
        mark = [[False]*self.w for _ in range(self.h)]

        # horizontal
        for y in range(self.h):
            count = 1
            for x in range(1,self.w):
                if self.grid[y][x] != 0 and self.grid[y][x] == self.grid[y][x-1]:
                    count += 1
                else:
                    if count >= 4:
                        for k in range(count):
                            mark[y][x-1-k] = True
                    count = 1
            if count >= 4:
                for k in range(count):
                    mark[y][self.w-1-k] = True

        # vertical
        for x in range(self.w):
            count = 1
            for y in range(1,self.h):
                if self.grid[y][x] != 0 and self.grid[y][x] == self.grid[y-1][x]:
                    count += 1
                else:
                    if count >= 4:
                        for k in range(count):
                            mark[y-1-k][x] = True
                    count = 1
            if count >= 4:
                for k in range(count):
                    mark[self.h-1-k][x] = True

        cleared = 0

        for y in range(self.h):
            for x in range(self.w):
                if mark[y][x]:
                    if self.grid[y][x] != 0:
                        cleared += 1
                    self.grid[y][x] = 0
                    self.virus[y][x] = False

        return cleared

    def apply_gravity(self):
        moved = True
        while moved:
            moved = False
            for y in range(self.h-2, -1, -1):
                for x in range(self.w):
                    if self.grid[y][x] != 0 and self.grid[y+1][x] == 0:
                        self.grid[y+1][x] = self.grid[y][x]
                        self.grid[y][x] = 0

                        self.virus[y+1][x] = self.virus[y][x]
                        self.virus[y][x] = False

                        moved = True

    # -------------------------
    # Update
    # -------------------------
    def update(self):
        self.tick += 1

        if self.btnp(2):
            print("left")
            self.pill["x"] -= 1
            if self.collides(self.pill):
                self.pill["x"] += 1

        if self.btnp(3):
            print("right")
            self.pill["x"] += 1
            if self.collides(self.pill):
                self.pill["x"] -= 1

        if self.btnp(4):
            print("rot")
            old = self.pill["rot"]
            self.pill["rot"] = (old + 1) % 4
            if self.collides(self.pill):
                self.pill["rot"] = old

        speed = 6
        if self.btn(1):
            print("down")
            speed = 5

        if self.tick % speed == 0:
            self.pill["y"] += 1
            if self.collides(self.pill):
                self.pill["y"] -= 1
                self.lock()

    # -------------------------
    # Draw
    # -------------------------
    def draw(self):
        #self.cls(0)

        # grid
        for y in range(self.h):
            for x in range(self.w):
                c = self.grid[y][x]
                if True or c != 0:
                    self.rect(x*self.cell, y*self.cell, self.cell, self.cell, c)

                    # draw virus marker
                    if self.virus[y][x]:
                        self.circ(x*self.cell+4, y*self.cell+4, 2, 0)

        # pill
        for x,y,c in self.cells(self.pill):
            if y >= 0:
                self.rect(x*self.cell, y*self.cell, self.cell, self.cell, c)

        # score
        self.print("SCORE: {}".format(self.score), 70, 10, 12)

    # -------------------------
    def TIC(self):
        self.update()
        self.draw()

# Self tests class

class SelfTests(Tic):
    def BOOT(self):
        self.state = "menu"
        self.menu_stack = [self.main_menu()]
        self.cursor = 0

        # Mouse state
        self.prev_mouse = False

        # Draw test
        self.brush_size = 3
        self.color = 12

        # Fake GPS data
        self.gga_data = [
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
            "$GPGGA,123520,4807.040,N,01131.002,E,1,08,0.9,545.5,M,46.9,M,,*48",
            "$GPGGA,123521,4807.042,N,01131.004,E,1,08,0.9,545.6,M,46.9,M,,*49",
        ]

        self.last_tick_time = time.time()
        self.frame_msec = 0

    # ---------------- MENU ----------------

    def main_menu(self):
        return {
            "title": "SELF TESTS",
            "items": [
                ("Draw Test", lambda: self.enter_menu(self.paint_menu())),
                ("GPS Test", lambda: self.set_state("gps")),
                ("Clock Test", lambda: self.set_state("clock")),
            ]
        }

    def paint_menu(self):
        return {
            "title": "DRAW SETTINGS",
            "items": [
                ("Brush +", lambda: self.brush(1)),
                ("Brush -", lambda: self.brush(-1)),
                ("Color +", self.next_color),
                ("Start Drawing", lambda: self.set_state("draw")),
                ("Back", self.pop_menu),
            ]
        }

    def enter_menu(self, menu):
        self.menu_stack.append(menu)

    def pop_menu(self):
        if len(self.menu_stack) > 1:
            self.menu_stack.pop()

    def current_menu(self):
        return self.menu_stack[-1]

    def set_state(self, state):
        self.state = state

    # ---------------- INPUT ----------------

    def mouse_pressed(self):
        mx, my, left, _, _, _, _= self.mouse()
        pressed = left and not self.prev_mouse
        self.prev_mouse = left
        return pressed, mx, my, left

    def mouse_released(self):
        mx, my, left, _, _, _, _= self.mouse()
        pressed = not left and self.prev_mouse
        self.prev_mouse = left
        return pressed, mx, my, left

    # ---------------- MENU RENDER ----------------

    def update_menu(self):
        pass

    def button_at(self, x, y, width, released, mx, my, name, action):
        hover = y <= my <= y + 16
        color = 15 if hover else 6
        bg = 0
        if hover:
            bg = 1
        if hover and released:
            bg = 15

        self.rect(x, y, width, 14, bg)
        self.print(name, x + 5, y + 4, color)

        if released:
            action()

    def draw_menu(self):
        self.cls(0)
        menu = self.current_menu()
        self.print(menu["title"], 10, 5, 12)

        released, mx, my, left = self.mouse_released()

        y = 22
        for name, action in menu["items"]:
            self.button_at(0, y, 120, released, mx, my, name, action)
            y += 16

        self.print(f"Touch {mx} x {my}, {left}", 5, y + 4, 15)
        y += 12
        self.print(f"Frame: {self.frame_msec} ms", 5, y + 4, 15)
        self.debug(f"Frame: {self.frame_msec} ms")
        y += 12
        self.print(f"{self.dragging}, {left}", 5, y + 4, 15)
        y += 12
        self.print(f"{self.width} x {self.height} @ {self.bpp*8} bits", 5, y+4, 15)
        self.pix(mx, my, 15)

    # ---------------- DRAW TEST ----------------

    def brush(self, delta):
        self.brush_size = max(1, self.brush_size + delta)

    def next_color(self):
        self.color = (self.color + 1) % 16

    def update_draw(self):
        mx, my, left, _, _, _, _ = self.mouse()

        if left:
            self.circ(mx, my, self.brush_size, self.color)

        pressed, mx, my, _ = self.mouse_pressed()

        # back button (top-left)
        if pressed and mx < 40 and my < 20:
            self.set_state("menu")

    def draw_draw(self):
        self.print("DRAW MODE", 5, 5, 12)
        self.print(f"Brush: {self.brush_size}", 5, 15, 12)
        self.print(f"Color: {self.color}", 5, 25, 12)
        self.print("BACK", 5, 35, 8)

    # ---------------- GPS TEST ----------------

    def update_gps(self):
        pressed, mx, my, _ = self.mouse_pressed()
        if pressed and mx < 40 and my < 20:
            self.set_state("menu")

    def draw_gps(self):
        self.cls(0)
        self.print("GPS GGA", 90, 10, 12)

        for i, line in enumerate(self.gga_data):
            self.print(line, 5, 30 + i * 12, 6)

        self.print("BACK", 5, 5, 8)

    # ---------------- CLOCK TEST ----------------

    def update_clock(self):
        pass

    def draw_clock(self):
        import math

        self.cls(0)

        pressed, mx, my, _ = self.mouse_pressed()
        if pressed and mx < 40 and my < 20:
            self.set_state("menu")

        self.print("BACK", 5, 5, 8)
        

        t = self.time() // 1000
        sec = t % 60
        minute = (t // 60) % 60
        hour = (t // 3600) % 24

        # digital
        self.print(f"{hour:02}:{minute:02}:{sec:02}", 84, 10, 12)

        # analog
        cx, cy = 120, 70
        self.circ(cx, cy, 30, 15)

        def hand(angle, length, color):
            x = cx + math.sin(angle) * length
            y = cy - math.cos(angle) * length
            self.line(cx, cy, int(x), int(y), color)

        hand(sec * math.pi / 30, 25, 12)
        hand(minute * math.pi / 30, 20, 11)
        hand((hour % 12) * math.pi / 6, 15, 10)

    # ---------------- MAIN ----------------

    def TIC(self):
        now = time.time()
        self.frame_msec = int((now - self.last_tick_time) * 1000)
        self.last_tick_time = now

        if self.state == "menu":
            self.update_menu()
            self.draw_menu()

        elif self.state == "draw":
            self.update_draw()
            self.draw_draw()

        elif self.state == "gps":
            self.update_gps()
            self.draw_gps()

        elif self.state == "clock":
            self.update_clock()
            self.draw_clock()

# --- End of shared code

# ----------------------------
# App logic
# ----------------------------

class CanvasActivity(Activity):
    def __init__(self):
        super().__init__()
        self.page = 0
        self.pages = 3

    def onCreate(self):
        print("\n\n\n\nFantasy Phone hacks")
        self.scr = lv.obj()
        scr = self.scr

        # Screen size
        self.W = scr.get_width()
        self.H = scr.get_height()

        # Canvas drawing area
        self.width = self.W
        self.height = self.H

        # Canvas
        self.canvas = lv.canvas(self.scr)

        if True:
            self.c = SelfTests(self.scr, self.canvas)
        elif False:
            self.c = GameVirus(self.scr, self.canvas)
        else:
            self.c = GamePuyo(self.scr, self.canvas)
        
        # Build buttons
        self.setContentView(self.c.scr)

    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, 1000//60, None)

    def onPause(self, screen):
        if self.timer:
            self.timer.delete()
            self.timer = None
            
    def tick(self, t):
        t1 = time.time()
        print("tick...")
        self.c.TIC()
        self.c.last_dragging = self.c.dragging["active"]
        self.c.canvas_update()
        print("...done %.3f" % (time.time() - t1))
