import time
from geo import *

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
        print(self.sats_in_view)
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
            if best_snr > 0:
                return f"Need some sky {best_snr} dB"
            return f"Need some sky {num} sats"
                    
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
        
