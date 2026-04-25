import time

from geo import *

# ----------------------------
# Fake NMEA source
# ----------------------------

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
