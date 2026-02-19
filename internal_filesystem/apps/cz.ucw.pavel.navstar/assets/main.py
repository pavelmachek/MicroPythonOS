from mpos import Activity

"""
micropythonos, give me code to parse nmea data from gps, display lat/lon/speed/... display sky view, allow recording of track to egt, display current track length in kilometers, and allow navigation to a point.
￼
"""

import time
import os
import json
import time
import math

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, MposKeyboard

#
# Features:
# - NMEA parsing: RMC, GGA, GSV
# - Live data: lat/lon/speed/alt/course/time/fix/sats/hdop
# - Sky view from GSV
# - Track recording to EGT
# - Track length (km)
# - Navigation to a point: bearing + distance
#
# Reality filter:
# - Sky view uses only azimuth/elevation from GSV, which many GPS modules output,
#   but some modules omit/limit GSV. In that case the sky view will be empty.
# - EGT is a simple plaintext format defined here (not a standard).


# ----------------------------
# Small utilities
# ----------------------------

def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def nmea_checksum_ok(line):
    # line includes leading '$' and optional \r\n
    line = line.strip()
    if not line.startswith("$"):
        return False
    star = line.find("*")
    if star < 0:
        return False
    body = line[1:star]
    given = line[star + 1:]
    if len(given) < 2:
        return False
    try:
        want = int(given[:2], 16)
    except ValueError:
        return False

    c = 0
    for ch in body:
        c ^= ord(ch)
    return c == want


def safe_float(s):
    try:
        return float(s)
    except Exception:
        return None


def safe_int(s):
    try:
        return int(s)
    except Exception:
        return None


def knots_to_kmh(knots):
    return knots * 1.852


def deg_to_rad(d):
    return d * math.pi / 180.0


def rad_to_deg(r):
    return r * 180.0 / math.pi


def haversine_km(lat1, lon1, lat2, lon2):
    # Great-circle distance
    R = 6371.0088
    phi1 = deg_to_rad(lat1)
    phi2 = deg_to_rad(lat2)
    dphi = deg_to_rad(lat2 - lat1)
    dl = deg_to_rad(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def bearing_deg(lat1, lon1, lat2, lon2):
    # Initial bearing from point1 -> point2
    phi1 = deg_to_rad(lat1)
    phi2 = deg_to_rad(lat2)
    dl = deg_to_rad(lon2 - lon1)

    y = math.sin(dl) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
    br = math.atan2(y, x)
    brd = (rad_to_deg(br) + 360.0) % 360.0
    return brd


def parse_latlon(ddmm, hemi):
    # NMEA format: latitude ddmm.mmmm, longitude dddmm.mmmm
    if not ddmm or not hemi:
        return None

    v = safe_float(ddmm)
    if v is None:
        return None

    # Split degrees and minutes
    # For lat: 2 deg digits; for lon: 3 deg digits
    # We infer by length before decimal.
    s = ddmm
    dot = s.find(".")
    if dot < 0:
        dot = len(s)

    deg_digits = 2
    if dot > 4:
        deg_digits = 3

    try:
        deg = int(s[:deg_digits])
        minutes = float(s[deg_digits:])
    except Exception:
        return None

    dec = deg + (minutes / 60.0)
    if hemi in ("S", "W"):
        dec = -dec
    return dec


def parse_hhmmss(hhmmss):
    # Returns (h,m,s) or None
    if not hhmmss or len(hhmmss) < 6:
        return None
    try:
        h = int(hhmmss[0:2])
        m = int(hhmmss[2:4])
        s = int(hhmmss[4:6])
        return (h, m, s)
    except Exception:
        return None


def parse_ddmmyy(ddmmyy):
    if not ddmmyy or len(ddmmyy) != 6:
        return None
    try:
        d = int(ddmmyy[0:2])
        mo = int(ddmmyy[2:4])
        y = int(ddmmyy[4:6]) + 2000
        return (y, mo, d)
    except Exception:
        return None


# ----------------------------
# NMEA state model
# ----------------------------

class GPSState:
    def __init__(self):
        self.start = time.time()
        self.start_good = self.start

        # Position / motion
        self.lat = None
        self.lon = None
        self.alt_m = None
        self.speed_kmh = None
        self.course_deg = None

        # Fix / quality
        self.fix_quality = 0   # from GGA
        self.fix_valid = False # from RMC
        self.sats_used = 0
        self.hdop = None

        # Time
        self.time_hms = None
        self.date_ymd = None

        # Satellites in view from GSV:
        # dict prn -> {el, az, snr}
        self.sats_in_view = {}

        # For display freshness
        self.last_update_ms = 0

    def has_fix(self):
        # Require RMC valid + lat/lon present
        return self.fix_valid and (self.lat is not None) and (self.lon is not None)

    def summary(self):
        num = 0
        good = 0
        best_snr = 0
        snrlim = 25
        for prn in self.sats_in_view:
            d = self.sats_in_view[prn]
            snr = d.get("snr")
            num += 1
            if snr:
                if snr > snrlim:
                    good += 1
                if best_snr < snr:
                    best_snr = snr

        now = time.time()
        if good < 4:
            self.start_good = now

        if self.has_fix():
            if good >=4:
                return f"Have FIX, good sky, hdop {self.hdop}"

            return f"FIX, bad sky {good}/{num}"

        if best_snr < snrlim:
            return f"Need some sky {best_snr} dB"
                    
        if good < 4:
            return f"Need clear sky {good}/{num}"

        delta = now - self.start_good
        return f"Need a minute {delta:.0f}s"

        delta = now - self.start
        return f"No fix for {delta:.0f}"
    

class NMEAParser:
    def __init__(self, gps_state):
        self.gps = gps_state

        # GSV is multi-part, but we do not need to store parts,
        # we just update sats_in_view as they arrive.
        # Some modules send multiple talker IDs: GP, GN, GL, GA...
        # We'll accept any.

    def feed_line(self, line):
        line = line.strip()
        if not line.startswith("$"):
            return

        if not nmea_checksum_ok(line):
            return

        # Strip $ and checksum
        star = line.find("*")
        body = line[1:star]
        fields = body.split(",")
        if len(fields) < 1:
            return

        msg = fields[0]
        # msg like GPRMC, GNRMC, etc.
        if len(msg) < 5:
            return

        msg_type = msg[-3:]

        if msg_type == "RMC":
            self._parse_rmc(fields)
        elif msg_type == "GGA":
            self._parse_gga(fields)
        elif msg_type == "GSV":
            self._parse_gsv(fields)

        self.gps.last_update_ms = time.ticks_ms()

    def _parse_rmc(self, f):
        # $GPRMC,hhmmss.sss,A,llll.ll,a,yyyyy.yy,a,x.x,x.x,ddmmyy,x.x,a*hh
        #  0      1          2 3       4 5       6 7   8   9      ...
        if len(f) < 10:
            return

        self.gps.time_hms = parse_hhmmss(f[1])
        status = f[2]
        self.gps.fix_valid = (status == "A")

        lat = parse_latlon(f[3], f[4])
        lon = parse_latlon(f[5], f[6])

        if lat is not None and lon is not None:
            self.gps.lat = lat
            self.gps.lon = lon

        sp_kn = safe_float(f[7])
        if sp_kn is not None:
            self.gps.speed_kmh = knots_to_kmh(sp_kn)

        course = safe_float(f[8])
        if course is not None:
            self.gps.course_deg = course

        self.gps.date_ymd = parse_ddmmyy(f[9])

    def _parse_gga(self, f):
        # $GPGGA,hhmmss.sss,lat,NS,lon,EW,quality,numSV,HDOP,alt,M,...
        if len(f) < 10:
            return

        self.gps.time_hms = parse_hhmmss(f[1])

        lat = parse_latlon(f[2], f[3])
        lon = parse_latlon(f[4], f[5])
        if lat is not None and lon is not None:
            self.gps.lat = lat
            self.gps.lon = lon

        q = safe_int(f[6])
        if q is not None:
            self.gps.fix_quality = q

        sats = safe_int(f[7])
        if sats is not None:
            self.gps.sats_used = sats

        hdop = safe_float(f[8])
        if hdop is not None:
            self.gps.hdop = hdop

        alt = safe_float(f[9])
        if alt is not None:
            self.gps.alt_m = alt

    def _parse_gsv(self, f):
        # $GPGSV,total_msgs,msg_num,total_sats, [sat blocks...]
        # Each sat block: prn, elev, az, snr
        if len(f) < 4:
            return

        # total_msgs = safe_int(f[1])
        # msg_num = safe_int(f[2])
        total_sats = safe_int(f[3])
        if total_sats is not None:
            # not exactly "used", but we store it in view count indirectly
            pass

        # sat blocks start at index 4
        i = 4
        while i + 3 < len(f):
            prn = safe_int(f[i + 0])
            el = safe_int(f[i + 1])
            az = safe_int(f[i + 2])
            snr = safe_int(f[i + 3])
            i += 4

            if prn is None:
                continue

            d = self.gps.sats_in_view.get(prn)
            if d is None:
                d = {}
                self.gps.sats_in_view[prn] = d

            if el is not None:
                d["el"] = el
            if az is not None:
                d["az"] = az
            if snr is not None:
                d["snr"] = snr
        

# ----------------------------
# Track recording (EGT)
# ----------------------------

class EGTWriter:
    """
    EGT (Easy GPS Track) - a minimal plaintext format.

    FIXME

    Header:
      # EGT 1
      # units: lat_deg lon_deg alt_m speed_kmh time_hms date_ymd
      # fields: lat lon alt_m speed_kmh course_deg sats_used hdop time date

    Points:
      P <lat> <lon> <alt_m> <speed_kmh> <course_deg> <sats_used> <hdop> <hh:mm:ss> <yyyy-mm-dd>

    This is NOT a standard. It is intended to be easy to parse later.
    """

    def __init__(self, filename):
        self.filename = filename
        self.fp = None
        self.started = False

    def start(self):
        if self.fp:
            return
        self.fp = open(self.filename, "a")
        if not self.started:
            self.fp.write("# EGT 1\n")
            self.fp.write("# fields: lat lon alt_m speed_kmh course_deg sats_used hdop time date\n")
            self.started = True
        self.fp.flush()

    def stop(self):
        if self.fp:
            self.fp.flush()
            self.fp.close()
            self.fp = None

    def write_point(self, gps):
        if not self.fp:
            return
        if not gps.has_fix():
            return

        lat = gps.lat
        lon = gps.lon
        alt = gps.alt_m if gps.alt_m is not None else -9999.0
        spd = gps.speed_kmh if gps.speed_kmh is not None else 0.0
        crs = gps.course_deg if gps.course_deg is not None else 0.0
        sats = gps.sats_used
        hdop = gps.hdop if gps.hdop is not None else -1.0

        if gps.time_hms:
            t = "%02d:%02d:%02d" % gps.time_hms
        else:
            t = "--:--:--"

        if gps.date_ymd:
            y, mo, d = gps.date_ymd
            da = "%04d-%02d-%02d" % (y, mo, d)
        else:
            da = "---- -- --"

        self.fp.write("P %.7f %.7f %.1f %.2f %.1f %d %.2f %s %s\n" %
                      (lat, lon, alt, spd, crs, sats, hdop, t, da))
        self.fp.flush()


class Track:
    def __init__(self):
        self.points = []  # list of (lat, lon)
        self.length_km = 0.0

    def reset(self):
        self.points = []
        self.length_km = 0.0

    def add_point(self, lat, lon):
        if lat is None or lon is None:
            return

        if len(self.points) > 0:
            lat0, lon0 = self.points[-1]
            d = haversine_km(lat0, lon0, lat, lon)
            # Basic noise suppression: ignore jumps < 2m
            if d < 0.002:
                return
            self.length_km += d

        self.points.append((lat, lon))

# ----------------------------
# Navigation target
# ----------------------------

class NavTarget:
    def __init__(self):
        self.enabled = False
        self.lat = None
        self.lon = None
        self.name = "TARGET"

    def set(self, lat, lon, name=None):
        self.lat = lat
        self.lon = lon
        self.enabled = True
        if name:
            self.name = name

    def clear(self):
        self.enabled = False
        self.lat = None
        self.lon = None


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
        self.bar_h = 39

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
        self._label_dsc.font = lv.font_montserrat_24

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
        dsc.font = lv.font_montserrat_24
        dsc.color = lv.color_black()

        area = lv.area_t()
        area.x1 = x
        area.y1 = y
        area.x2 = x + self.W
        area.y2 = y + self.H

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
        self.bar_h = 39

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
        ui = self.c
        ui.clear()

        st = 28
        y = 2*st
        ui.text(0, y, "Hello world, page is %d" % self.page)
        y += st

    def draw(self):
        self.draw_page_example()

    def handle_buttons(self):
        ui = self.c

# ----------------------------
# App logic
# ----------------------------

class Main(PagedCanvas):
    def __init__(self):
        super().__init__()
        track_file="track.egt"
        self.gps = GPSState()
        self.parser = NMEAParser(self.gps)

        self.track = Track()
        self.egt = EGTWriter(track_file)
        self.recording = False

        self.nav = NavTarget()

        self.last_track_write_ms = 0
        self.last_track_add_ms = 0

        self.uart = None

        # Default nav point (Prague center) - change as desired
        # (Reality filter: this is just a reasonable example coordinate.)
        self.nav.set(50.087465, 14.421254, "Prague")

    def tick(self, t):
        lm.poll()
        nmea = lm.get_nmea()
        if nmea:
            lines = nmea.split('\n')
            for line in lines:
                print("line", line)
                self.parser.feed_line(line)
        self.update()
        self.draw()

    def toggle_recording(self):
        self.recording = not self.recording
        if self.recording:
            self.egt.start()
        else:
            self.egt.stop()

    def set_nav_target_here(self):
        if self.gps.has_fix():
            self.nav.set(self.gps.lat, self.gps.lon, "HERE")

    def clear_track(self):
        self.track.reset()

    def read_uart(self):
        if not self.uart:
            return

        # We read line-by-line. Many GPS modules end lines with \r\n.
        while True:
            line = self.uart.readline()
            if not line:
                break
            try:
                s = line.decode("ascii", "ignore")
            except Exception:
                continue
            self.parser.feed_line(s)

    def maybe_update_track(self):
        print("update track?")
        if not self.gps.has_fix():
            return

        now = time.ticks_ms()

        # Add a track point at ~1 Hz
        if time.ticks_diff(now, self.last_track_add_ms) > 1000:
            print("update track? ... !")
            self.last_track_add_ms = now
            self.track.add_point(self.gps.lat, self.gps.lon)

        # Write to file at ~1 Hz if recording
        if self.recording and time.ticks_diff(now, self.last_track_write_ms) > 1000:
            self.last_track_write_ms = now
            self.egt.write_point(self.gps)

    def draw_page_status(self):
        gps = self.gps
        ui = self.c

        ui.clear()

        st = 28
        y = 2*st
        fix = "FIX" if gps.has_fix() else "NOFIX"
        rec = "REC" if self.recording else "----"
        ui.text(0, y, "%s  %s  sats:%d" % (fix, rec, gps.sats_used))
        y += st
        ui.text(0, y, "%s" % gps.summary())
        y += 2*st

        if gps.lat is not None and gps.lon is not None:
            ui.text(0, y, "Lat: %.6f" % gps.lat)
            ui.text(0, y+st, "Lon: %.6f" % gps.lon)
        else:
            ui.text(0, y, "Lat: ---")
            ui.text(0, y+st, "Lon: ---")
        y += 2*st

        if gps.speed_kmh is not None:
            ui.text(0, y, "Speed: %.1f km/h" % gps.speed_kmh)
        else:
            ui.text(0, y, "Speed: ---")
        y += st
        
        if gps.alt_m is not None:
            ui.text(0, y, "Alt: %.1f m" % gps.alt_m)
        else:
            ui.text(0, y, "Alt: ---")
        y += st

        if gps.course_deg is not None:
            ui.text(0, y, "Head: %.0f deg" % gps.course_deg)
        else:
            ui.text(0, y, "Head: ---")
        y += st

        ui.text(0, y, "Track: %.3f km" % self.track.length_km)
        y += st

        if gps.hdop is not None:
            ui.text(0, y, "HDOP: %.1f" % gps.hdop)
        y += st

        if gps.time_hms:
            ui.text(0, y, "Time: %02d:%02d:%02d" % gps.time_hms)
        y += st
        print("Final size: ", y)

        ui.update()

    def draw_page_sky(self):
        gps = self.gps
        ui = self.c

        ui.clear()
        ui.text(0, 22, "Sky view")

        # Sky view circle
        cx = 160
        cy = 160
        R = 100

        ui.circle(cx, cy, R)
        ui.circle(cx, cy, int(R * 0.66))
        ui.circle(cx, cy, int(R * 0.33))
        ui.line(cx - R, cy, cx + R, cy)
        ui.line(cx, cy - R, cx, cy + R)

        # Plot satellites
        # NMEA: elevation 0..90, azimuth 0..359
        # Map elevation: 90 at center, 0 at edge
        count = 0
        for prn in gps.sats_in_view:
            d = gps.sats_in_view[prn]
            el = d.get("el")
            az = d.get("az")
            snr = d.get("snr")

            if el is None or az is None:
                continue

            # radial distance
            r = (90 - el) / 90.0
            r = clamp(r, 0.0, 1.0) * R

            a = deg_to_rad(az - 90)  # rotate so 0 deg is up
            x = int(cx + r * math.cos(a))
            y = int(cy + r * math.sin(a))

            # Dot size from SNR
            if snr is None:
                rr = 1
            else:
                rr = 1 + int(clamp(snr-10, 0, 15)) / 3

            ui.fill_circle(x, y, rr)
            count += 1

        ui.text(0, cy + R - 20, "SV: %d" % count)
        ui.update()

    def draw_page_nav(self):
        gps = self.gps
        ui = self.c
        st = 28

        ui.clear()
        y = 2*st
        ui.text(0, y, "Navigation")
        y += st

        if not self.nav.enabled:
            ui.text(0, st, "No target.")
            ui.update()
            return

        ui.text(0, y,      "To: %s" % self.nav.name)
        ui.text(0, y+st,   "Tlat: %.6f" % self.nav.lat)
        ui.text(0, y+st*2, "Tlon: %.6f" % self.nav.lon)
        y += st*3

        if gps.has_fix():
            dist = haversine_km(gps.lat, gps.lon, self.nav.lat, self.nav.lon)
            brg = bearing_deg(gps.lat, gps.lon, self.nav.lat, self.nav.lon)

            ui.text(0, y, "Dist: %.3f km" % dist)
            ui.text(0, y+st, "Bear: %.0f deg" % brg)

            if gps.course_deg is not None:
                rel = (brg - gps.course_deg + 360.0) % 360.0
                if rel > 180.0:
                    rel -= 360.0
                ui.text(0, y+2*st, "Turn: %+d deg" % int(rel))

        else:
            ui.text(0, y, "Waiting for fix...")
        y += st*3

        ui.text(0, y, "Track: %.3f km" % self.track.length_km)
        print("Final nav", y)

        draw_nav_screen(ui, self.gps, self.track.points, self.nav.lat, self.nav.lon)
        ui.update()

    def draw_page_record(self):
        gps = self.gps
        ui = self.c

        ui.clear()

        st = 28
        y = 2*st
        fix = "FIX" if gps.has_fix() else "NOFIX"
        rec = "REC" if self.recording else "----"
        ui.text(0, y, "%s  %s  sats:%d" % (fix, rec, gps.sats_used))
        y += st
        ui.text(0, y, "%s" % gps.summary())
        y += 2*st

        if gps.speed_kmh is not None:
            ui.text(0, y, "Speed: %.1f km/h" % gps.speed_kmh)
        else:
            ui.text(0, y, "Speed: ---")
        y += st
        
        if gps.alt_m is not None:
            ui.text(0, y, "Alt: %.1f m" % gps.alt_m)
        else:
            ui.text(0, y, "Alt: ---")
        y += st

        ui.text(0, y, "Track: %.3f km" % self.track.length_km)
        y += st

        print("Final size: ", y)

        ui.update()

    def update(self):
        self.maybe_update_track()

    def draw(self):
        if self.page == 0:
            self.draw_page_status()
        elif self.page == 1:
            self.draw_page_sky()
        elif self.page == 2:
            self.draw_page_nav()
        elif self.page == 3:
            self.draw_page_record()
        else:
            self.draw_page_example()

    def handle_buttons(self):
        ui = self.c

        if ui.button_next_page():
            ui.page = (ui.page + 1) % ui.pages

        if ui.button_toggle_record():
            self.toggle_recording()

        if ui.button_set_nav_target():
            # Here we implement: "set target to current position"
            # If you want manual entry, see note below.
            self.set_nav_target_here()

        if ui.button_clear_track():
            self.clear_track()

    def run_forever(self):
        while True:
            self.read_uart()
            self.maybe_update_track()
            self.handle_buttons()
            self.draw()
            time.sleep_ms(50)

TMP = "/tmp/cmd.json"

def run_cmd_json(cmd):
    rc = os.system(cmd + " > " + TMP)
    if rc != 0:
        raise RuntimeError("command failed")

    with open(TMP, "r") as f:
        data = f.read().strip()

    return json.loads(data)

def dbus_json(cmd):
    return run_cmd_json("sudo /home/mobian/g/MicroPythonOS/phone.py " + cmd)

class LocationManager:
    def poll(self):
        v = dbus_json("loc")
        print(v)
        self.loc = v
        
    def get_cellid(self):
        if "1" in self.loc:
            return self.loc["1"]
        return None

    def get_nmea(self):
        if "4" in self.loc:
            return self.loc["4"]
        return None

# --
# Fake nmea source
# --

def nmea_checksum(sentence_body):
    # sentence_body without leading '$' and without '*xx'
    c = 0
    for ch in sentence_body:
        c ^= ord(ch)
    return "%02X" % c


def nmea_wrap(sentence_body):
    return "$%s*%s" % (sentence_body, nmea_checksum(sentence_body))


def deg_to_nmea_lat(lat_deg):
    # ddmm.mmmm, N/S
    sign = "N"
    if lat_deg < 0:
        sign = "S"
        lat_deg = -lat_deg

    dd = int(lat_deg)
    mm = (lat_deg - dd) * 60.0
    return "%02d%07.4f" % (dd, mm), sign


def deg_to_nmea_lon(lon_deg):
    # dddmm.mmmm, E/W
    sign = "E"
    if lon_deg < 0:
        sign = "W"
        lon_deg = -lon_deg

    ddd = int(lon_deg)
    mm = (lon_deg - ddd) * 60.0
    return "%03d%07.4f" % (ddd, mm), sign


class FakeNMEASpiral:
    """
    Fake NMEA generator for testing.

    Simulates a spiral around a center coordinate:
      center_lat=50.0, center_lon=14.0

    Generates:
      - GGA
      - RMC
      - GSV (fake sats)

    Usage:
      sim = FakeNMEASpiral()
      lines = sim.next_sentences()   # list of NMEA lines (strings)
    """

    def __init__(self,
                 center_lat=50.0,
                 center_lon=14.0,
                 alt_m=260.0,
                 start_radius_m=0.0,
                 radius_growth_m_per_s=0.25,
                 angular_speed_deg_per_s=18.0,
                 speed_noise=0.05,
                 sat_count=10,
                 seed_time=None):
        self.center_lat = float(center_lat)
        self.center_lon = float(center_lon)
        self.alt_m = float(alt_m)

        self.r0 = float(start_radius_m)
        self.r_growth = float(radius_growth_m_per_s)
        self.w_deg = float(angular_speed_deg_per_s)

        self.speed_noise = float(speed_noise)

        self.sat_count = int(sat_count)
        self.sats = self._make_fake_sats(self.sat_count)

        if seed_time is None:
            seed_time = time.time()

        self.t0 = float(seed_time)
        self.last_t = self.t0

        self.last_lat = self.center_lat
        self.last_lon = self.center_lon
        self.last_course = 0.0
        self.last_speed_mps = 0.0

        # NMEA-ish fields
        self.hdop = 0.9
        self.fix_quality = 1  # 1=GPS fix
        self.num_sats = clamp(self.sat_count, 4, 12)

    def _make_fake_sats(self, n):
        # PRN, elevation, azimuth, snr
        sats = []
        for i in range(n):
            prn = 1 + i
            el = 15 + (i * 7) % 70
            az = (i * 360.0 / n) % 360.0
            snr = 20 + (i * 3) % 30
            sats.append((prn, el, az, snr))
        return sats

    def _spiral_position(self, t):
        # t in seconds since t0
        dt = t - self.t0

        r = self.r0 + self.r_growth * dt  # meters
        ang_deg = (self.w_deg * dt) % 360.0
        ang = math.radians(ang_deg)

        # local ENU offsets (east, north) in meters
        east = r * math.cos(ang)
        north = r * math.sin(ang)

        # convert meters -> degrees
        lat = self.center_lat + (north / 111132.0)
        lon = self.center_lon + (east / (111320.0 * math.cos(math.radians(self.center_lat))))

        return lat, lon, r, ang_deg

    def _course_and_speed(self, lat, lon, dt):
        # compute speed and course from last point (very simple)
        if dt <= 0.0:
            return self.last_course, self.last_speed_mps

        # local approx meters
        phi = math.radians(self.center_lat)
        m_per_deg_lat = 111132.0
        m_per_deg_lon = 111320.0 * math.cos(phi)

        dlat = (lat - self.last_lat) * m_per_deg_lat
        dlon = (lon - self.last_lon) * m_per_deg_lon

        # north/east
        north = dlat
        east = dlon

        dist = math.sqrt(north * north + east * east)
        speed = dist / dt

        # course: 0=north, 90=east
        course = math.degrees(math.atan2(east, north)) % 360.0

        # add tiny deterministic noise
        speed *= (1.0 + self.speed_noise * math.sin((time.time() - self.t0) * 0.7))

        return course, speed

    def _utc_hhmmss(self, t):
        #dt = datetime.datetime.utcfromtimestamp(t)
        #return dt.strftime("%H%M%S") + ".00"
        return "123456.00"

    def _utc_ddmmyy(self, t):
        #dt = datetime.datetime.utcfromtimestamp(t)
        #return dt.strftime("%d%m%y")
        return "311122"

    def next_sentences(self, t=None, include_gsv=True):
        """
        Return list of NMEA sentences (strings).
        """
        if t is None:
            t = time.time()

        dt = t - self.last_t
        lat, lon, r_m, ang_deg = self._spiral_position(t)
        course, speed_mps = self._course_and_speed(lat, lon, dt)

        # update state
        self.last_t = t
        self.last_lat = lat
        self.last_lon = lon
        self.last_course = course
        self.last_speed_mps = speed_mps

        # NMEA formatting
        hhmmss = self._utc_hhmmss(t)
        ddmmyy = self._utc_ddmmyy(t)

        lat_s, lat_hemi = deg_to_nmea_lat(lat)
        lon_s, lon_hemi = deg_to_nmea_lon(lon)

        speed_knots = speed_mps * 1.94384449

        # --- GGA
        # $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
        gga_body = "GPGGA,%s,%s,%s,%s,%s,%d,%02d,%.1f,%.1f,M,0.0,M,," % (
            hhmmss,
            lat_s, lat_hemi,
            lon_s, lon_hemi,
            self.fix_quality,
            self.num_sats,
            self.hdop,
            self.alt_m,
        )

        # --- RMC
        # $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
        # We omit magnetic variation field -> empty.
        rmc_body = "GPRMC,%s,A,%s,%s,%s,%s,%.2f,%.1f,%s,," % (
            hhmmss,
            lat_s, lat_hemi,
            lon_s, lon_hemi,
            speed_knots,
            course,
            ddmmyy,
        )

        out = [
            nmea_wrap(gga_body),
            nmea_wrap(rmc_body),
        ]

        if include_gsv:
            out.extend(self._gsv_sentences())

        return out

    def poll(self):
        self.data = '\n'.join(self.next_sentences())
        print("Data", self.data)
        
    def get_cellid(self):
        return None

    def get_nmea(self):
        return self.data
    

    def _gsv_sentences(self):
        # GSV: 4 sats per message
        sats = self.sats
        total = len(sats)
        per = 4
        msgs = (total + per - 1) // per
        out = []

        for mi in range(msgs):
            chunk = sats[mi * per:(mi + 1) * per]
            fields = ["GPGSV", str(msgs), str(mi + 1), str(total)]
            for (prn, el, az, snr) in chunk:
                fields.extend([
                    "%02d" % prn,
                    "%02d" % int(el),
                    "%03d" % int(az),
                    "%02d" % int(snr),
                ])
            body = ",".join(fields)
            out.append(nmea_wrap(body))

        return out


#lm = LocationManager()
lm = FakeNMEASpiral(center_lat=50.0, center_lon=14.0)

# -----------------------------
# Helpers
# -----------------------------

def norm_deg(d):
    # normalize to 0..360
    d = d % 360.0
    if d < 0:
        d += 360.0
    return d


def bearing_deg(lat1, lon1, lat2, lon2):
    # initial bearing (true) in degrees, 0..360
    # Inputs in degrees.
    phi1 = deg_to_rad(lat1)
    phi2 = deg_to_rad(lat2)
    dlon = deg_to_rad(lon2 - lon1)

    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    brng = rad_to_deg(math.atan2(y, x))
    return norm_deg(brng)


def haversine_m(lat1, lon1, lat2, lon2):
    return haversine_km(lat1, lon1, lat2, lon2) * 1000


def meters_to_human(m):
    if m is None:
        return "?"
    if m < 1000.0:
        return "%dm" % int(m + 0.5)
    return "%.2fkm" % (m / 1000.0)


def ms_to_kmh(v):
    if v is None:
        return None
    return v * 3.6


def kmh_to_human(kmh):
    if kmh is None:
        return "?"
    if kmh < 10:
        return "%.1f km/h" % kmh
    return "%.0f km/h" % kmh


def draw_arrow(ui, x0, y0, x1, y1, head_len=14, head_ang_deg=28):
    # main shaft
    ui.line(x0, y0, x1, y1)

    # arrow head
    ang = math.atan2(y1 - y0, x1 - x0)
    ha = deg_to_rad(head_ang_deg)

    xh1 = int(x1 - head_len * math.cos(ang - ha))
    yh1 = int(y1 - head_len * math.sin(ang - ha))

    xh2 = int(x1 - head_len * math.cos(ang + ha))
    yh2 = int(y1 - head_len * math.sin(ang + ha))

    ui.line(x1, y1, xh1, yh1)
    ui.line(x1, y1, xh2, yh2)


def polar_to_xy(cx, cy, r, angle_deg):
    # angle_deg: 0 is up, 90 is right (screen coords)
    a = deg_to_rad(angle_deg - 90.0)
    x = int(cx + r * math.cos(a))
    y = int(cy + r * math.sin(a))
    return x, y


# -----------------------------
# Main draw routine
# -----------------------------

def draw_nav_screen(ui, gps, trail,
                    dest_lat, dest_lon,
                    mag_declination_deg=None):
    """
    Expected gps fields (typical gpsd-ish):
      gps.lat, gps.lon
      gps.speed_ms   (or gps.speed)
      gps.track_deg  (COG, or gps.track)
      gps.fix_ok     (bool)

    trail: list of dicts: {"lat":..., "lon":...} newest last
    mag_declination_deg:
      If known for your region (e.g. Prague ~ 4-5 deg E in 2025-ish),
      pass it here. If unknown, pass None and M will not be drawn.
    """

    # --- Geometry
    cx = 165
    cy = 510
    R = 105

    # --- Draw compass rose
    ui.circle(cx, cy, R)
    ui.line(cx - R, cy, cx + R, cy)
    ui.line(cx, cy - R, cx, cy + R)

    # --- Require a fix
    if not getattr(gps, "fix_ok", True):
        ui.text(0, 440, "No GPS fix")
        return

    lat = getattr(gps, "lat", None)
    lon = getattr(gps, "lon", None)

    if lat is None or lon is None:
        ui.text(0, 44, "No position")
        return

    # --- Course over ground: defines "UP"
    cog = getattr(gps, "course_deg", None)
    print("Lat, lon", lat, lon, "Cog", cog, "trail", trail)

    # If no course, assume north-up
    if cog is None:
        cog = 0.0

    cog = norm_deg(cog)

    # --- Destination bearing and distance
    brng_true = bearing_deg(lat, lon, dest_lat, dest_lon)
    dist_m = haversine_m(lat, lon, dest_lat, dest_lon)

    # Arrow angle relative to UP=COG:
    # If destination is straight ahead, arrow points up.
    rel = norm_deg(brng_true - cog)
    # Convert to signed -180..180 for nicer behavior (optional)
    if rel > 180.0:
        rel -= 360.0

    # --- Draw destination arrow
    # Use a fixed length so it is always visible
    arrow_len = int(R * 0.85)
    x_tip, y_tip = polar_to_xy(cx, cy, arrow_len, rel)
    draw_arrow(ui, cx, cy, x_tip, y_tip, head_len=16, head_ang_deg=30)

    # --- Mark TRUE NORTH on the ring
    # True north is bearing 0°, relative to UP=COG => angle = 0 - COG
    ang_true_n = norm_deg(0.0 - cog)
    xn, yn = polar_to_xy(cx, cy, R, ang_true_n)
    ui.text(xn - 6, yn - 8, "N")

    # --- Mark MAGNETIC NORTH on the ring (if declination known)
    # Magnetic bearing = true - declination(E positive)
    # Magnetic north direction in true coords = -declination
    if mag_declination_deg is not None:
        ang_mag_n = norm_deg((-mag_declination_deg) - cog)
        xm, ym = polar_to_xy(cx, cy, R, ang_mag_n)
        ui.text(xm - 6, ym - 8, "M")

    # --- Draw trail of last fixes
    # Project lat/lon into local meters (simple equirectangular)
    # and rotate so UP is COG.
    if trail and len(trail) >= 2:
        lat0 = lat
        lon0 = lon
        phi = deg_to_rad(lat0)

        # meters per degree
        m_per_deg_lat = 111132.0
        m_per_deg_lon = 111320.0 * math.cos(phi)

        # max range shown in trail radius
        # (you can tune this)
        trail_range_m = 80.0

        # rotate by -COG so direction of travel is up
        rot = deg_to_rad(cog)

        prev_xy = None
        for p in trail[-12:]:
            plat, plon = p
            if plat is None or plon is None:
                continue

            dx = (plon - lon0) * m_per_deg_lon
            dy = (plat - lat0) * m_per_deg_lat

            # rotate into screen coords
            rx = dx * math.cos(rot) - dy * math.sin(rot)
            ry = dx * math.sin(rot) + dy * math.cos(rot)

            # Map meters -> pixels
            sx = int(cx + (rx / trail_range_m) * (R * 0.95))
            sy = int(cy - (ry / trail_range_m) * (R * 0.95))

            # clamp to circle-ish bounds
            sx = clamp(sx, cx - R + 2, cx + R - 2)
            sy = clamp(sy, cy - R + 2, cy + R - 2)

            # draw point (small cross)
            ui.line(sx - 1, sy, sx + 1, sy)
            ui.line(sx, sy - 1, sx, sy + 1)

            if prev_xy is not None:
                ui.line(prev_xy[0], prev_xy[1], sx, sy)

            prev_xy = (sx, sy)

    # --- Text info
    speed_ms = getattr(gps, "speed_ms", None)
    if speed_ms is None:
        speed_ms = getattr(gps, "speed", None)

    speed_kmh = ms_to_kmh(speed_ms)

    ui.text(0, 290, "Dist: " + meters_to_human(dist_m))
    ui.text(0, 312, "Speed: " + kmh_to_human(speed_kmh))

    # Optional: show bearing numbers
    ui.text(0, 334, "COG: %d deg" % int(cog + 0.5))
    ui.text(0, 356, "BRG: %d deg" % int(brng_true + 0.5))


class Fake():
    pass

