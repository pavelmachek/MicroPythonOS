import time
import math

from pcanvas import *
from mpos import SensorManager

# -----------------------------
# Step counter (improved)
# -----------------------------
class StepCounter:
    def __init__(self):
        self.accel = SensorManager.get_default_sensor(
            SensorManager.TYPE_ACCELEROMETER
        )

        self.g_est = 9.81
        self.alpha = 0.92

        self.prev = 0
        self.prev2 = 0

        self.last_step = 0
        self.steps = 0

        self.threshold = 1.0
        self.min_interval = 0.28  # ~ walking cadence

        self.filtered = 0

    def update(self):
        raw = SensorManager.read_sensor_once(self.accel)
        x, y, z = raw

        mag = math.sqrt(x*x + y*y + z*z)

        # --- remove gravity ---
        self.g_est = self.alpha * self.g_est + (1-self.alpha) * mag
        f = mag - self.g_est

        # --- smooth ---
        f = 0.6 * f + 0.4 * self.prev

        now = time.time()

        # --- peak detection (better: local max) ---
        is_peak = (
            self.prev > self.prev2 and
            self.prev > f and
            self.prev > self.threshold
        )

        if is_peak and (now - self.last_step > self.min_interval):
            self.steps += 1
            self.last_step = now

        self.prev2 = self.prev
        self.prev = f
        self.filtered = f

        return f

    def reset(self):
        self.steps = 0
        self.last_step = 0

# -----------------------------
# Main App
# -----------------------------
class Main(PagedCanvas):

    def __init__(self):
        super().__init__()

        self.counter = StepCounter()

        # history buffer
        self.hist = [0] * 200
        self.hist_len = len(self.hist)

        self.stride_len = 0.75  # meters per step (avg human)

    # -------------------------
    def build_buttons(self):
        self.template_buttons(["Graph", "Stats", "Reset"])

    # -------------------------
    def onResume(self, screen):
        self.timer = lv.timer_create(self.tick, 50, None)

    # -------------------------
    def update(self):
        self.c.clear()

        val = self.counter.update()

        # update history
        self.hist.pop(0)
        self.hist.append(val)

        if self.page == 0:
            self.draw_graph()
        elif self.page == 1:
            self.draw_stats()
        elif self.page == 2:
            self.counter.reset()
            self.hist = [0] * self.hist_len
            self.page = 0

    # -------------------------
    # GRAPH
    # -------------------------
    def draw_graph(self):
        w = self.c.W
        h = self.c.H

        mid = h // 2

        # axis
        self.c.line(0, mid, w, mid)

        scale = 40  # pixels per accel unit

        # draw waveform
        for i in range(len(self.hist)-1):
            x1 = int(i * w / self.hist_len)
            x2 = int((i+1) * w / self.hist_len)

            y1 = int(mid - self.hist[i] * scale)
            y2 = int(mid - self.hist[i+1] * scale)

            self.c.line(x1, y1, x2, y2)

        # threshold line
        thr = int(mid - self.counter.threshold * scale)
        self.c.line(0, thr, w, thr)

        self.c.text(5, 5, f"Steps: {self.counter.steps}")

    # -------------------------
    # STATS
    # -------------------------
    def draw_stats(self):
        steps = self.counter.steps

        distance_m = steps * self.stride_len
        distance_km = distance_m / 1000.0

        self.c.text(0, 10, f"""
Steps: {steps}

Distance:
{distance_m:.1f} m
{distance_km:.3f} km

Stride:
{self.stride_len:.2f} m
""")
