import random
import math

from mpos import Activity
from pcanvas import *

try:
    import lvgl as lv
except ImportError:
    pass


class Main(PagedCanvas):

    WIDTH = 240
    HEIGHT = 240

    BRICK_ROWS = 5
    BRICK_COLS = 8

    PADDLE_W = 50
    PADDLE_H = 8

    BALL_R = 4

    TICK = 16  # ~60 FPS

    COLORS = [
        0xE74C3C,
        0xF1C40F,
        0x2ECC71,
        0x3498DB,
        0x9B59B6,
    ]

    def __init__(self):
        super().__init__()

        self.canvas = None
        self.buf = None

        self.timer = None

        self.bricks = []

    # -----------------------------------------------------------------

    def onCreate(self):

        super().onCreate()
        
        self.scr.add_event_cb(self.on_touch, lv.EVENT.PRESSING, None)
        self.scr.add_event_cb(self.on_key, lv.EVENT.KEY, None)

        focusgroup = lv.group_get_default()
        if focusgroup:
            focusgroup.add_obj(self.screen)


    # -----------------------------------------------------------------

    def new_game(self):

        self.score = 0

        self.paddle_x = self.WIDTH // 2 - self.PADDLE_W // 2
        self.paddle_y = self.HEIGHT - 20

        self.ball_x = self.WIDTH // 2
        self.ball_y = self.HEIGHT // 2

        angle = random.uniform(-0.6, 0.6)

        self.ball_dx = math.sin(angle) * 4
        self.ball_dy = -4

        self.create_bricks()

        self.redraw()

    # -----------------------------------------------------------------

    def create_bricks(self):

        self.bricks = []

        bw = self.WIDTH // self.BRICK_COLS
        bh = 14

        for r in range(self.BRICK_ROWS):
            for c in range(self.BRICK_COLS):

                self.bricks.append({
                    "x": c * bw,
                    "y": 40 + r * bh,
                    "w": bw - 2,
                    "h": bh - 2,
                    "color": self.COLORS[r % len(self.COLORS)],
                    "alive": True
                })

    # -----------------------------------------------------------------

    def onResume(self, screen):
        self.new_game()
        
        self.timer = lv.timer_create(self.tick, self.TICK, None)

    def onPause(self, screen):
        if self.timer:
            self.timer.delete()
            self.timer = None

    # -----------------------------------------------------------------

    def tick(self, t):

        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        # wall bounce
        if self.ball_x < self.BALL_R or self.ball_x > self.WIDTH - self.BALL_R:
            self.ball_dx *= -1

        if self.ball_y < self.BALL_R:
            self.ball_dy *= -1

        # paddle bounce
        if (
            self.paddle_y <= self.ball_y + self.BALL_R <= self.paddle_y + self.PADDLE_H
            and self.paddle_x <= self.ball_x <= self.paddle_x + self.PADDLE_W
        ):

            rel = (self.ball_x - self.paddle_x) / self.PADDLE_W - 0.5
            self.ball_dx = rel * 8
            self.ball_dy = -abs(self.ball_dy)

        # brick collision
        for b in self.bricks:

            if not b["alive"]:
                continue

            if (
                b["x"] <= self.ball_x <= b["x"] + b["w"]
                and b["y"] <= self.ball_y <= b["y"] + b["h"]
            ):

                b["alive"] = False
                self.ball_dy *= -1
                self.score += 1
                break

        # lose
        if self.ball_y > self.HEIGHT:
            self.new_game()
            return

        self.redraw()

    # -----------------------------------------------------------------

    def redraw(self):
        self.c.clear()

        draw = lv.draw_rect_dsc_t()

        # bricks
        for b in self.bricks:

            if not b["alive"]:
                continue

            draw.bg_color = lv.color_hex(b["color"])

            self.c.fill_rect(
                b["x"],
                b["y"],
                b["w"],
                b["h"]
            )

        # paddle
        draw.bg_color = lv.color_hex(0xFFFFFF)

        self.c.fill_rect(
            int(self.paddle_x),
            int(self.paddle_y),
            self.PADDLE_W,
            self.PADDLE_H
        )

        # ball
        circle = lv.draw_rect_dsc_t()
        circle.bg_color = lv.color_hex(0xFFFFFF)
        #circle.radius = lv.RADIUS.CIRCLE

        self.c.circle(
            int(self.ball_x - self.BALL_R),
            int(self.ball_y - self.BALL_R),
            self.BALL_R
        )

    # -----------------------------------------------------------------

    def move_paddle(self, x):

        self.paddle_x = x - self.PADDLE_W // 2

        if self.paddle_x < 0:
            self.paddle_x = 0

        if self.paddle_x > self.WIDTH - self.PADDLE_W:
            self.paddle_x = self.WIDTH - self.PADDLE_W

    # -----------------------------------------------------------------

    def on_touch(self, e):

        p = lv.indev_get_act().get_point()
        self.move_paddle(p.x)

    def on_key(self, event):

        key = event.get_key()

        if key == ord("a"):
            self.move_paddle(self.paddle_x - 20)

        elif key == ord("d"):
            self.move_paddle(self.paddle_x + 20)
