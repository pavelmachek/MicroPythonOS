from mpos import Activity

"""
micropythonos, give me code to parse nmea data from gps, display lat/lon/speed/... display sky view, allow recording of track to egt, display current track length in kilometers, and allow navigation to a point.
￼
"""

import time
import os

try:
    import lvgl as lv
except ImportError:
    pass

from mpos import Activity, MposKeyboard



#!/usr/bin/env micropython
# upyos_gps_nav.py
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

import time
import math

try:
    from machine import UART, Pin
except ImportError:
    UART = None
    Pin = None


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
# UI / display abstraction
# ----------------------------

class UI:
    """
    Replace these stubs with upyos display primitives.
    """

    def __init__(self):
        self.page = 0
        self.pages = 3

    def clear(self):
        pass

    def text(self, x, y, s):
        # draw string
        pass

    def line(self, x1, y1, x2, y2):
        pass

    def circle(self, x, y, r):
        pass

    def fill_circle(self, x, y, r):
        pass

    def update(self):
        # flush
        pass

    def button_next_page(self):
        # Return True when "next page" pressed
        return False

    def button_toggle_record(self):
        # Return True when record toggled
        return False

    def button_set_nav_target(self):
        # Return True when user wants to set nav target
        return False

    def button_clear_track(self):
        return False


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


# ----------------------------
# App logic
# ----------------------------

class GPSApp:
    def __init__(self, uart_id=1, baud=9600, track_file="track.egt"):
        self.gps = GPSState()
        self.parser = NMEAParser(self.gps)

        self.ui = UI()

        self.track = Track()
        self.egt = EGTWriter(track_file)
        self.recording = False

        self.nav = NavTarget()

        self.last_track_write_ms = 0
        self.last_track_add_ms = 0

        self.uart = None
        if UART:
            # Adjust pins if needed for your board
            self.uart = UART(uart_id, baudrate=baud, timeout=50)

        # Default nav point (Prague center) - change as desired
        # (Reality filter: this is just a reasonable example coordinate.)
        self.nav.set(50.087465, 14.421254, "PRAGUE")

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
        if not self.gps.has_fix():
            return

        now = time.ticks_ms()

        # Add a track point at ~1 Hz
        if time.ticks_diff(now, self.last_track_add_ms) > 1000:
            self.last_track_add_ms = now
            self.track.add_point(self.gps.lat, self.gps.lon)

        # Write to file at ~1 Hz if recording
        if self.recording and time.ticks_diff(now, self.last_track_write_ms) > 1000:
            self.last_track_write_ms = now
            self.egt.write_point(self.gps)

    def draw_page_status(self):
        gps = self.gps
        ui = self.ui

        ui.clear()

        fix = "FIX" if gps.has_fix() else "NOFIX"
        rec = "REC" if self.recording else "----"
        ui.text(0, 0, "%s  %s  sats:%d" % (fix, rec, gps.sats_used))

        if gps.lat is not None and gps.lon is not None:
            ui.text(0, 12, "Lat: %.6f" % gps.lat)
            ui.text(0, 24, "Lon: %.6f" % gps.lon)
        else:
            ui.text(0, 12, "Lat: ---")
            ui.text(0, 24, "Lon: ---")

        if gps.speed_kmh is not None:
            ui.text(0, 36, "Speed: %.1f km/h" % gps.speed_kmh)
        else:
            ui.text(0, 36, "Speed: ---")

        if gps.alt_m is not None:
            ui.text(0, 48, "Alt: %.1f m" % gps.alt_m)
        else:
            ui.text(0, 48, "Alt: ---")

        if gps.course_deg is not None:
            ui.text(0, 60, "Head: %.0f deg" % gps.course_deg)
        else:
            ui.text(0, 60, "Head: ---")

        ui.text(0, 72, "Track: %.3f km" % self.track.length_km)

        if gps.hdop is not None:
            ui.text(0, 84, "HDOP: %.1f" % gps.hdop)

        if gps.time_hms:
            ui.text(0, 96, "Time: %02d:%02d:%02d" % gps.time_hms)

        ui.update()

    def draw_page_sky(self):
        gps = self.gps
        ui = self.ui

        ui.clear()
        ui.text(0, 0, "Sky view (GSV)")

        # Sky view circle
        cx = 64
        cy = 70
        R = 45

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
                rr = 2
            else:
                rr = 1 + int(clamp(snr, 0, 50) / 20)

            ui.fill_circle(x, y, rr)
            count += 1

        ui.text(0, 112, "SV: %d" % count)
        ui.update()

    def draw_page_nav(self):
        gps = self.gps
        ui = self.ui

        ui.clear()
        ui.text(0, 0, "Navigation")

        if not self.nav.enabled:
            ui.text(0, 12, "No target.")
            ui.update()
            return

        ui.text(0, 12, "To: %s" % self.nav.name)
        ui.text(0, 24, "Tlat: %.6f" % self.nav.lat)
        ui.text(0, 36, "Tlon: %.6f" % self.nav.lon)

        if gps.has_fix():
            dist = haversine_km(gps.lat, gps.lon, self.nav.lat, self.nav.lon)
            brg = bearing_deg(gps.lat, gps.lon, self.nav.lat, self.nav.lon)

            ui.text(0, 52, "Dist: %.3f km" % dist)
            ui.text(0, 64, "Bear: %.0f deg" % brg)

            if gps.course_deg is not None:
                rel = (brg - gps.course_deg + 360.0) % 360.0
                if rel > 180.0:
                    rel -= 360.0
                ui.text(0, 76, "Turn: %+d deg" % int(rel))

        else:
            ui.text(0, 52, "Waiting for fix...")

        ui.text(0, 96, "Track: %.3f km" % self.track.length_km)
        ui.update()

    def draw(self):
        if self.ui.page == 0:
            self.draw_page_status()
        elif self.ui.page == 1:
            self.draw_page_sky()
        else:
            self.draw_page_nav()

    def handle_buttons(self):
        ui = self.ui

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


#def main():
#    app = GPSApp(uart_id=1, baud=9600, track_file="track.egt")
#    app.run_forever()


#if __name__ == "__main__":
#    main()

class Main(Activity):
    def __init__(self):
        super().__init__()

    def onCreate(self):
	self.screen = lv.obj()
        self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)
        #score.set_text("Score")
        #self.lb_score = score

        vert = 30
	btn_right = lv.button(self.screen)
	btn_right.set_size(30, vert)
	btn_right.align(lv.ALIGN.BOTTOM_RIGHT, -5, -5-vert)
        btn_right.add_event_cb(lambda e: self.move(1), lv.EVENT.CLICKED, None)
        lc = lv.label(btn_right)
	lc.set_text(">")
	lc.center()

        self.setContentView(self.screen)

    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, self.FALL_INTERVAL, None)

    def onPause(self, screen):
        if self.timer:
            self.timer.delete()
            self.timer = None
            
    def tick(self, t):
	print("Tick!")
