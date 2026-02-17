"""
Robot translated that from bwatch/magcali.js

"""

import time
import os
import math

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, MposKeyboard, SensorManager

# -----------------------------
# Utilities
# -----------------------------

def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def to_rad(deg):
    return deg * math.pi / 180.0

def to_deg(rad):
    return rad * 180.0 / math.pi

# -----------------------------
# Calibration + heading
# -----------------------------

class CompassCalibrator:
    def __init__(self):
        self.reset()

    def reset(self):
        self.vmin = [10000.0, 10000.0, 10000.0]
        self.vmax = [-10000.0, -10000.0, -10000.0]

    def step(self, v):
        """
        Update min/max. Returns True if calibration box changed ("bad" in JS).
        """
        bad = False
        for i in range(3):
            if v[i] < self.vmin[i]:
                self.vmin[i] = v[i]
                bad = True
            if v[i] > self.vmax[i]:
                self.vmax[i] = v[i]
                bad = True
        return bad

    def compensated(self, v):
        """
        Returns:
          vh = v - center
          sc = scaled to [-1..+1]
        """
        vh = [0.0, 0.0, 0.0]
        sc = [0.0, 0.0, 0.0]

        for i in range(3):
            center = (self.vmin[i] + self.vmax[i]) / 2.0
            vh[i] = v[i] - center

            denom = (self.vmax[i] - self.vmin[i])
            if denom == 0:
                sc[i] = 0.0
            else:
                sc[i] = (v[i] - self.vmin[i]) / denom * 2.0 - 1.0

        return vh, sc

    def heading_flat(self, sc):
        """
        Equivalent of:
          heading = atan2(sc[1], sc[0]) * 180/pi - 90
        """
        h = to_deg(math.atan2(sc[1], sc[0])) - 90.0
        while h < 0:
            h += 360.0
        while h >= 360.0:
            h -= 360.0
        return h


class TiltCompensatedCompass:
    def __init__(self):
        self.calib_done = False
        self.offset = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.scale = {'x': 1.0, 'y': 1.0, 'z': 1.0}

    def tilt_calibrate(self, vmin, vmax):
        """
        JS tiltCalibrate(min,max)
        vmin/vmax are dicts with x,y,z
        """
        offset = {
            'x': (vmax['x'] + vmin['x']) / 2.0,
            'y': (vmax['y'] + vmin['y']) / 2.0,
            'z': (vmax['z'] + vmin['z']) / 2.0,
        }
        delta = {
            'x': (vmax['x'] - vmin['x']) / 2.0,
            'y': (vmax['y'] - vmin['y']) / 2.0,
            'z': (vmax['z'] - vmin['z']) / 2.0,
        }
        avg = (delta['x'] + delta['y'] + delta['z']) / 3.0

        # Avoid division by zero
        scale = {
            'x': avg / delta['x'] if delta['x'] else 1.0,
            'y': avg / delta['y'] if delta['y'] else 1.0,
            'z': avg / delta['z'] if delta['z'] else 1.0,
        }

        self.offset = offset
        self.scale = scale
        self.calib_done = True

    def tilt_fix_read(self, mag_xyz, acc_xyz):
        """
        Port of JS tiltfixread(O,S).
        Inputs:
          mag_xyz: (mx,my,mz)
          acc_xyz: (ax,ay,az)
        Returns heading 0..360
        """
        if mag_xyz is None or acc_xyz is None:
            return None

        mx, my, mz = mag_xyz
        ax, ay, az = acc_xyz

        dx = (mx - self.offset['x']) * self.scale['x']
        dy = (my - self.offset['y']) * self.scale['y']
        dz = (mz - self.offset['z']) * self.scale['z']

        # JS:
        # phi = atan(-g.x/-g.z)
        # theta = atan(-g.y/(-g.x*sinphi-g.z*cosphi))
        # ...
        # psi = atan2(yh,xh)
        #
        # Keep the same structure.

        # Avoid pathological az=0
        if az == 0:
            az = 1e-9

        phi = math.atan((-ax) / (-az))
        cosphi = math.cos(phi)
        sinphi = math.sin(phi)

        denom = (-ax * sinphi - az * cosphi)
        if denom == 0:
            denom = 1e-9

        theta = math.atan((-ay) / denom)
        costheta = math.cos(theta)
        sintheta = math.sin(theta)

        xh = dy * costheta + dx * sinphi * sintheta + dz * cosphi * sintheta
        yh = dz * sinphi - dx * cosphi

        psi = to_deg(math.atan2(yh, xh))
        if psi < 0:
            psi += 360.0
        return psi

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

        # Bottom button bar
        self.margin = 2
        self.bar_h = 26

        # Canvas drawing area (everything above button bar)
        self.draw_w = self.W
        self.draw_h = self.H - (self.bar_h + self.margin * 2)

        self.canvas = canvas

        # Background: white (change if you want dark theme)
        self.canvas.set_style_bg_color(lv.color_white(), lv.PART.MAIN)

        # Buffer: your working example uses 4 bytes/pixel
        # Reality filter: this depends on LV_COLOR_DEPTH; but your example proves it works.
        self.buf = bytearray(self.draw_w * self.draw_h * 4)
        self.canvas.set_buffer(self.buf, self.draw_w, self.draw_h, lv.COLOR_FORMAT.NATIVE)

        # Layer used for draw engine
        self.layer = lv.layer_t()
        self.canvas.init_layer(self.layer)

        # Persistent draw descriptors (avoid allocations)
        self._line_dsc = lv.draw_line_dsc_t()
        lv.draw_line_dsc_t.init(self._line_dsc)
        self._line_dsc.width = 1
        self._line_dsc.color = lv.color_black()
        self._line_dsc.round_end = 1
        self._line_dsc.round_start = 1

        self._label_dsc = lv.draw_label_dsc_t()
        lv.draw_label_dsc_t.init(self._label_dsc)
        self._label_dsc.color = lv.color_black()
        self._label_dsc.font = lv.font_montserrat_14

        self._rect_dsc = lv.draw_rect_dsc_t()
        lv.draw_rect_dsc_t.init(self._rect_dsc)
        self._rect_dsc.bg_opa = lv.OPA.TRANSP
        self._rect_dsc.border_opa = lv.OPA.COVER
        self._rect_dsc.border_width = 1
        self._rect_dsc.border_color = lv.color_black()

        self._fill_dsc = lv.draw_rect_dsc_t()
        lv.draw_rect_dsc_t.init(self._fill_dsc)
        self._fill_dsc.bg_opa = lv.OPA.COVER
        self._fill_dsc.bg_color = lv.color_black()
        self._fill_dsc.border_width = 1

        # Clear once
        self.clear()

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

    def clear(self):
        # Clear the canvas background
        self.canvas.fill_bg(lv.color_white(), lv.OPA.COVER)

    def text(self, x, y, s, fg = lv.color_black()):
        self._begin()

        dsc = lv.draw_label_dsc_t()
        lv.draw_label_dsc_t.init(dsc)
        dsc.text = str(s)
        dsc.font = lv.font_montserrat_14
        dsc.color = lv.color_black()

        area = lv.area_t()
        area.x1 = x
        area.y1 = y
        area.x2 = x + 300
        area.y2 = y + 30

        lv.draw_label(self.layer, dsc, area)

        self._end()

    def line(self, x1, y1, x2, y2, fg = lv.color_black()):
        self._begin()

        dsc = self._line_dsc
        dsc.p1 = lv.point_precise_t()
        dsc.p2 = lv.point_precise_t()
        dsc.p1.x = int(x1)
        dsc.p1.y = int(y1)
        dsc.p2.x = int(x2)
        dsc.p2.y = int(y2)

        lv.draw_line(self.layer, dsc)

        self._end()

    def circle(self, x, y, r, fg = lv.color_black()):
        # Rounded rectangle trick (works everywhere)
        self._begin()

        a = lv.area_t()
        a.x1 = int(x - r)
        a.y1 = int(y - r)
        a.x2 = int(x + r)
        a.y2 = int(y + r)

        dsc = self._rect_dsc
        dsc.radius = lv.RADIUS_CIRCLE
        dsc.border_color = fg

        lv.draw_rect(self.layer, dsc, a)

        self._end()

    def fill_circle(self, x, y, r, fg = lv.color_black(), bg = lv.color_white()):
        self._begin()

        a = lv.area_t()
        a.x1 = int(x - r)
        a.y1 = int(y - r)
        a.x2 = int(x + r)
        a.y2 = int(y + r)

        dsc = self._rect_dsc
        dsc.radius = lv.RADIUS_CIRCLE
        dsc.border_color = fg
        dsc.bg_color = bg

        lv.draw_rect(self.layer, dsc, a)

        self._end()

    def fill_rect(self, x, y, sx, sy, fg = lv.color_black(), bg = lv.color_white()):
        self._begin()

        a = lv.area_t()
        a.x1 = x
        a.y1 = y
        a.x2 = x+sx
        a.y2 = y+sy

        dsc = self._fill_dsc
        dsc.border_color = fg
        dsc.bg_color = bg

        lv.draw_rect(self.layer, dsc, a)

        self._end()

    def update(self):
        # Nothing needed; drawing is committed per primitive.
        # If you want, you can change the implementation so that:
        # - draw ops happen between clear() and update()
        # But then you must ensure the app calls update() once per frame.
        pass

# ----------------------------
# App logic
# ----------------------------

class PagedCanvas(Activity):
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

        # Bottom button bar
        self.margin = 2
        self.bar_h = 26

        # Canvas drawing area (everything above button bar)
        self.draw_w = self.W
        self.draw_h = self.H - (self.bar_h + self.margin * 2)

        # Canvas
        self.canvas = lv.canvas(self.scr)
        self.canvas.set_size(self.draw_w, self.draw_h)
        self.canvas.align(lv.ALIGN.TOP_LEFT, 0, 0)
        self.canvas.set_style_border_width(0, 0)
        
        self.c = Canvas(self.scr, self.canvas)
        self.setContentView(self.c.scr)

        # Build buttons
        self._build_buttons()

    # ----------------------------
    # Button bar
    # ----------------------------

    def _make_btn(self, parent, x, y, w, h, label):
        b = lv.button(parent)
        b.set_pos(x, y)
        b.set_size(w, h)

        l = lv.label(b)
        l.set_text(label)
        l.center()

        return b

    def _btn_cb(self, evt, tag):
        self.page = tag

    def _build_buttons(self):
        margin = self.margin
        y = self.H - self.bar_h - margin

        w = (self.W - margin * 5) // 4
        h = self.bar_h
        x0 = margin

        self.btn_0 = self._make_btn(self.scr, x0 + (w + margin) * 0, y, w, h, "Pg0")
        self.btn_1 = self._make_btn(self.scr, x0 + (w + margin) * 1, y, w, h, "Pg1")
        self.btn_2 = self._make_btn(self.scr, x0 + (w + margin) * 2, y, w, h, "Pg2")
        self.btn_3 = self._make_btn(self.scr, x0 + (w + margin) * 3, y, w, h, "Pg3")

        self.btn_0.add_event_cb(lambda evt: self._btn_cb(evt, 0), lv.EVENT.CLICKED, None)
        self.btn_1.add_event_cb(lambda evt: self._btn_cb(evt, 1), lv.EVENT.CLICKED, None)
        self.btn_2.add_event_cb(lambda evt: self._btn_cb(evt, 2), lv.EVENT.CLICKED, None)
        self.btn_3.add_event_cb(lambda evt: self._btn_cb(evt, 3), lv.EVENT.CLICKED, None)

    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, 50, None)

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
        ui = self.c
        ui.clear()

        st = 14
        y = 2*st
        ui.text(0, y, "Hello world, page is %d" % self.page)
        y += st

    def draw(self):
        self.draw_page_example()

    def handle_buttons(self):
        ui = self.c

class Main(PagedCanvas):
    def __init__(self):
        super().__init__()

        self.accel = SensorManager.get_default_sensor(SensorManager.TYPE_ACCELEROMETER)
        self.magn = SensorManager.get_default_sensor(SensorManager.TYPE_MAGNETIC_FIELD)

        self.cal = CompassCalibrator()
        self.tilt = TiltCompensatedCompass()

        self.v = None
        self.vfirst = None
        self.bad = False

        self.heading = 0.0
        self.heading2 = None

        self.Ypos = 40
        self.brg = None  # bearing target, degrees or None

    def reset_calib(self):
        self.cal.reset()

    def draw(self):
        pass

    def update(self):
        ui = self.c
        ui.clear()
        st = 14
        y = 2*st
        
        v = SensorManager.read_sensor_once(self.magn)
        if v is None:
            ui.text(0, y, f"No compass data")
            y += st
            return
        sc = 1000
        v = [float(v[1]) * sc, -float(v[0]) * sc, float(v[2]) * sc]

        self.v = v

        if self.vfirst is None:
            self.vfirst = self.v[:]

        self.bad = self.cal.step(self.v)

        vh, sc = self.cal.compensated(self.v)
        self.heading = self.cal.heading_flat(sc)

        acc = SensorManager.read_sensor_once(self.accel)
        acc = ( -acc[1], -acc[0], acc[2] )

        ui.text(0, y, f"Compass, raw is {self.v}, bad is {self.bad}, acc is {acc}")
        y += st

        if self.tilt.calib_done:
            self.heading2 = self.tilt.tilt_fix_read(self.v, acc)

        if self.page == 0:
            self.draw_top(
                heading=self.heading,
                heading2=self.heading2,
                calib_done=self.tilt.calib_done,
                vmin=self.cal.vmin,
                vmax=self.cal.vmax,
                vfirst=self.vfirst,
                v=self.v,
                bad=self.bad,
                acc=acc,
            )
        else:
            h = self.heading2 if (self.tilt.calib_done and self.heading2 is not None) else self.heading
            self.draw_side(h)

    LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    def _px_per_deg(self):
        # JS used deg->px: (deg/90)*(width/2.1)
        return (self.c.W / 2.1) / 90.0

    def _degrees_to_pixels(self, deg):
        return deg * self._px_per_deg()

    # ---- TOP VIEW ----

    def draw_top(self, heading, heading2, calib_done, vmin, vmax, vfirst, v, bad, acc):
        self.c.clear()

        cx = self.c.W // 2
        cy = self.c.H // 2

        # Crosshair
        self.c.line(0, cy, self.c.W, cy)
        self.c.line(cx, 0, cx, self.c.H)

        # Circles (30/60/90 deg)
        for rdeg in (30, 60, 90):
            r = int(self._degrees_to_pixels(rdeg))
            self.c.circle(cx, cy, r)

        # Calibration box + current point
        self._draw_calib_box(vmin, vmax, vfirst, v, bad)

        # Accel circle
        if acc is not None:
            self._draw_accel(acc)

        # Heading arrow(s)
        self._draw_heading_arrow(heading, color=lv.color_make(255, 0, 0))
        if calib_done and heading2 is not None:
            self._draw_heading_arrow(heading2, color=lv.color_make(255, 255, 255))
            self.c.text(10, 10, "%d°" % int(heading2))

    def _draw_heading_arrow(self, heading, color):
        cx = self.c.W / 2.0
        cy = self.c.H / 2.0

        rad = -to_rad(heading)
        x2 = cx + math.sin(rad - 0.1) * 80.0
        y2 = cy - math.cos(rad - 0.1) * 80.0
        x3 = cx + math.sin(rad + 0.1) * 80.0
        y3 = cy - math.cos(rad + 0.1) * 80.0

        poly = [
            int(cx), int(cy),
            int(x2), int(y2),
            int(x3), int(y3),
        ]

        self.c.line(poly[0], poly[1], poly[2], poly[3])
        self.c.line(poly[2], poly[3], poly[4], poly[5])
        self.c.line(poly[4], poly[5], poly[0], poly[1])

    def _draw_accel(self, acc):
        ax, ay, az = acc
        cx = self.c.W / 2.0
        cy = self.c.H / 2.0

        x2 = cx + ax * self.c.W
        y2 = cy + ay * self.c.W

        self.c.circle(int(x2), int(y2), int(self.c.W / 8))

    def _draw_calib_box(self, vmin, vmax, vfirst, v, bad):
        if v is None or vfirst is None:
            return

        scale = 0.15

        boxW = (vmax[0] - vmin[0]) * scale
        boxH = -(vmax[1] - vmin[1]) * scale
        boxX = (vmin[0] - vfirst[0]) * scale + self.c.W / 2.0
        boxY = -(vmin[1] - vfirst[1]) * scale + self.c.H / 2.0

        x = (v[0] - vfirst[0]) * scale + self.c.W / 2.0
        y = -(v[1] - vfirst[1]) * scale + self.c.H / 2.0

        # box rect
        if bad:
            bg = lv.color_make(255, 0, 0)
        else:
            bg = lv.color_make(0, 150, 0)

        x1 = int(boxX)
        y1 = int(boxY)
        x2 = int(boxX + boxW)
        y2 = int(boxY + boxH)

        # normalize coords
        xa = min(x1, x2)
        xb = max(x1, x2)
        ya = min(y1, y2)
        yb = max(y1, y2)

        self.c.fill_rect(xa, ya, xb - xa, yb - ya, bg = bg)

        # point
        self.c.fill_circle(int(x), int(y), 3, bg = lv.color_make(255, 255, 0))

    # ---- SIDE VIEW ----

    def draw_side(self, course_deg):
        self.c.clear()
        return

        course = int(round(course_deg)) % 360
        ypos = self.Ypos

        # Compass ribbon baseline
        rect = lv.draw_rect_dsc_t()
        rect.bg_color = lv.color_white()
        rect.bg_opa = lv.OPA.COVER
        self.canvas.draw_rect(16, ypos + 45, 144, 4, rect)

        start = course - 90
        if start < 0:
            start += 360

        xpos = 16
        frag = 15 - (start % 15)
        if frag < 15:
            xpos += int((frag * 4) / 5)
        else:
            frag = 0

        # ticks
        for i in range(int(frag), int(180 - frag) + 1, 15):
            res = start + i
            x = xpos

            if res % 90 == 0:
                self._tick_label(x, ypos, self.LABELS[(res // 45) % 8], major=True)
            elif res % 45 == 0:
                self._tick_label(x, ypos, self.LABELS[(res // 45) % 8], major=False)
            else:
                self._tick_minor(x, ypos)

            xpos += 12

        # Bearing dot (optional)
        if self.brg is not None:
            bpos = self.brg - course
            if bpos > 180:
                bpos -= 360
            if bpos < -180:
                bpos += 360

            bpos = int((bpos * 4) / 5) + 88
            if bpos < 16:
                bpos = 8
            if bpos > 160:
                bpos = 170

            c = lv.draw_arc_dsc_t()
            c.color = lv.color_make(0, 255, 255)
            self.canvas.draw_circle(bpos, ypos + 45, 6, c)

        # Course numeric
        txt = "%03d" % course
        self._draw_big_centered(txt, ypos + 90)

        # Triangle marker
        self._draw_triangle_marker(88, ypos + 60)

    def _tick_label(self, x, ypos, label, major):
        # tick
        r = lv.draw_rect_dsc_t()
        r.bg_color = lv.color_white()
        r.bg_opa = lv.OPA.COVER

        if major:
            self.canvas.draw_rect(x - 2, ypos + 25, 4, 20, r)
        else:
            self.canvas.draw_rect(x - 2, ypos + 30, 4, 15, r)

        # label
        lab = lv.label(self.scr)
        lab.set_text(label)
        lab.set_style_text_color(lv.color_white(), 0)
        lab.set_pos(x - (9 if not major else 6), ypos + 6)

    def _tick_minor(self, x, ypos):
        r = lv.draw_rect_dsc_t()
        r.bg_color = lv.color_white()
        r.bg_opa = lv.OPA.COVER
        self.canvas.draw_rect(x, ypos + 35, 2, 10, r)

    def _draw_triangle_marker(self, x, y):
        dsc = lv.draw_rect_dsc_t()
        dsc.bg_color = lv.color_white()
        dsc.bg_opa = lv.OPA.COVER

        poly = [
            x, y,
            x - 10, y + 20,
            x + 10, y + 20,
        ]
        try:
            self.canvas.draw_polygon(poly, dsc)
        except Exception:
            ld = lv.draw_line_dsc_t()
            ld.color = lv.color_white()
            self.canvas.draw_line(poly[0], poly[1], poly[2], poly[3], ld)
            self.canvas.draw_line(poly[2], poly[3], poly[4], poly[5], ld)
            self.canvas.draw_line(poly[4], poly[5], poly[0], poly[1], ld)

    def _draw_big_centered(self, text, y):
        lab = lv.label(self.scr)
        lab.set_text(text)
        lab.set_style_text_color(lv.color_white(), 0)
        # If you have a font configured, set it here:
        # lab.set_style_text_font(my_big_font, 0)
        lab.align(lv.ALIGN.TOP_MID, 0, y)
