import lvgl as lv
import mpos
from mpos import Activity, MposKeyboard, InputManager


# -----------------------------
# Canvas (LVGL)
# -----------------------------

class Color:
    def __init__(self, r,g,b):
        self.r = r
        self.g = g
        self.b = b

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
        self.scale = 2
        self.canvas.set_style_transform_scale(256 * self.scale, 0)

        # Layer used for draw engine
        self.layer = lv.layer_t()
        self.canvas.init_layer(self.layer)

        self.dragging = {"active": False, "last_x": 0, "last_y": 0}
        self.canvas.add_flag(lv.obj.FLAG.CLICKABLE)
        self.canvas.add_event_cb(self.touch_cb, lv.EVENT.ALL, None)

        # Clear once
        self.clear()
        for i in range(self.draw_w):
            self.put_pixel(i, i, Color(255, 0, 0))
            self.put_pixel(i, self.draw_h-i-1, Color(255, 0, 0))
            self.put_pixel(i, self.draw_h//2, Color(0, 255, 0))
        for i in range(self.draw_h):
            self.put_pixel(self.draw_w//2, i, Color(0, 0, 255))


    # --- Event handler ---
    def touch_cb(self, event):
        event_code=event.get_code()
	if event_code not in [19,23,25,26,27,28,29,30,49]:
            if event_code == lv.EVENT.PRESSING: # this is probably enough       
                x, y = InputManager.pointer_xy()
                print("Pressing", x, y)
                self.put_pixel(x/self.scale,y/self.scale, Color(128,128,128))
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

    def __put_pixel(self, x, y, c):
        i = (y * self.draw_w + x) * 4
        self.buf[i] = c.b
        self.buf[i+1] = c.g
        self.buf[i+2] = c.r
        self.buf[i+3] = 255

    def put_pixel(self, x, y, c):
        x = int(x)
        y = int(y)
        if x < 0 or x >= self.draw_w:
            return
        if y < 0 or y >= self.draw_h:
            return
        self.__put_pixel(x, y, c)

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

### MENU
`MENU(index)`
Game Menu handler.

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
