# settings.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    TITLE: str = "Match-3 Shapes"
    WIDTH: int = 900
    HEIGHT: int = 650
    FPS: int = 60

    GRID_SIZE: int = 8
    TILE_SIZE: int = 60
    BOARD_X: int = 60
    BOARD_Y: int = 90
    BOARD_PADDING: int = 6

    BASE_TIME_SECONDS: int = 90
    BASE_COLORS: int = 5
    MIN_MATCH: int = 3

    PANEL_X: int = 600
    PANEL_Y: int = 90
    PANEL_W: int = 270
    PANEL_H: int = 480

    COINS_PER_100_SCORE: int = 1

    # ---- NEW: animations ----
    SWAP_ANIM_TIME: float = 0.12
    FALL_ANIM_TIME: float = 0.16

    # ---- NEW: jeopardy ----
    DOOM_RATE_PER_SEC: float = 0.055  # fills at ~5.5% per second
    DOOM_REDUCE_PER_CLEAR: float = 0.018  # reduce Doom per cleared tile
    INVALID_SWAP_TIME_PENALTY: float = 2.0  # seconds removed

SET = Settings()