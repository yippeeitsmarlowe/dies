# board.py
import random
import pygame
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Set

SHAPES = ["circle", "square", "diamond", "triangle", "hex"]

TYPE_COLORS = [
    (231, 76, 60),    # red
    (52, 152, 219),   # blue
    (46, 204, 113),   # green
    (241, 196, 15),   # yellow
    (155, 89, 182),   # purple
    (230, 126, 34),   # orange
    (26, 188, 156),   # teal
]

Special = Optional[str]  # None | "row" | "col" | "bomb"

@dataclass
class Piece:
    pid: int
    kind: int
    special: Special = None

MatchGroup = Tuple[str, List[Tuple[int, int]]]  # ("h" or "v", positions)

class Board:
    def __init__(self, grid_size: int, num_types: int):
        self.n = grid_size
        self.num_types = num_types
        self._next_pid = 1
        self.grid: List[List[Piece]] = [[self._new_piece() for _ in range(self.n)] for _ in range(self.n)]
        self.populate_no_matches()

    def _new_piece(self, kind: Optional[int] = None, special: Special = None) -> Piece:
        if kind is None:
            kind = random.randrange(self.num_types)
        p = Piece(self._next_pid, kind, special)
        self._next_pid += 1
        return p

    def populate_no_matches(self):
        for y in range(self.n):
            for x in range(self.n):
                self.grid[y][x] = self._new_piece()
                while self.causes_match_at(x, y):
                    self.grid[y][x] = self._new_piece()

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.n and 0 <= y < self.n

    def swap(self, a: Tuple[int,int], b: Tuple[int,int]):
        ax, ay = a
        bx, by = b
        self.grid[ay][ax], self.grid[by][bx] = self.grid[by][bx], self.grid[ay][ax]

    def causes_match_at(self, x: int, y: int) -> bool:
        k = self.grid[y][x].kind
        if x >= 2 and self.grid[y][x-1].kind == k and self.grid[y][x-2].kind == k:
            return True
        if y >= 2 and self.grid[y-1][x].kind == k and self.grid[y-2][x].kind == k:
            return True
        return False

    def find_match_groups(self, min_len: int = 3) -> List[MatchGroup]:
        groups: List[MatchGroup] = []

        # horizontal
        for y in range(self.n):
            run_kind = self.grid[y][0].kind
            run_start = 0
            for x in range(1, self.n + 1):
                k = self.grid[y][x].kind if x < self.n else None
                if x < self.n and k == run_kind:
                    continue
                run_len = x - run_start
                if run_kind is not None and run_len >= min_len:
                    pos = [(rx, y) for rx in range(run_start, x)]
                    groups.append(("h", pos))
                if x < self.n:
                    run_kind = k
                    run_start = x

        # vertical
        for x in range(self.n):
            run_kind = self.grid[0][x].kind
            run_start = 0
            for y in range(1, self.n + 1):
                k = self.grid[y][x].kind if y < self.n else None
                if y < self.n and k == run_kind:
                    continue
                run_len = y - run_start
                if run_kind is not None and run_len >= min_len:
                    pos = [(x, ry) for ry in range(run_start, y)]
                    groups.append(("v", pos))
                if y < self.n:
                    run_kind = k
                    run_start = y

        return groups

    def has_any_moves(self) -> bool:
        for y in range(self.n):
            for x in range(self.n):
                for dx, dy in [(1,0), (0,1)]:
                    nx, ny = x+dx, y+dy
                    if not self.in_bounds(nx, ny):
                        continue
                    self.swap((x,y), (nx,ny))
                    g = self.find_match_groups()
                    self.swap((x,y), (nx,ny))
                    if g:
                        return True
        return False

    def reroll_board(self):
        self.populate_no_matches()

    def collapse_and_refill(self):
        # Collapse columns downward by removing "holes" (None)
        for x in range(self.n):
            col: List[Optional[Piece]] = [self.grid[y][x] for y in range(self.n)]
            col2 = [p for p in col if p is not None]
            missing = self.n - len(col2)
            new_pieces = [self._new_piece() for _ in range(missing)]
            final = new_pieces + col2
            for y in range(self.n):
                self.grid[y][x] = final[y]

        # very light re-roll of immediate matches
        groups = self.find_match_groups()
        if groups:
            touched = set()
            for _, pos in groups:
                touched.update(pos)
            for (x, y) in touched:
                self.grid[y][x] = self._new_piece()

def draw_gem(surface: pygame.Surface, rect: pygame.Rect, piece: Piece):
    color = TYPE_COLORS[piece.kind % len(TYPE_COLORS)]
    shape = SHAPES[piece.kind % len(SHAPES)]

    cx, cy = rect.center
    s = min(rect.width, rect.height)
    pad = int(s * 0.16)
    r = s // 2 - pad

    # --- base gem ---
    if shape == "circle":
        pygame.draw.circle(surface, color, (cx, cy), r)
    elif shape == "square":
        pygame.draw.rect(surface, color, rect.inflate(-2 * pad, -2 * pad), border_radius=8)
    elif shape == "diamond":
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surface, color, pts)
    elif shape == "triangle":
        pts = [(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        pygame.draw.polygon(surface, color, pts)
    elif shape == "hex":
        pts = []
        for i in range(6):
            v = pygame.Vector2(r, 0).rotate(i * 60)
            pts.append((cx + v.x, cy + v.y))
        pygame.draw.polygon(surface, color, pts)

    # border
    pygame.draw.rect(surface, (20, 20, 25), rect, width=2, border_radius=10)

    # --- SPECIAL VISUALS ---
    # Use bright "ink" plus a dark backing so it reads on any color.
    INK = (245, 245, 255)
    SHADOW = (15, 15, 20)

    inner = rect.inflate(-int(s * 0.22), -int(s * 0.22))
    inner_radius = 10

    def thick_line(p1, p2, w):
        # shadow first
        pygame.draw.line(surface, SHADOW, p1, p2, w + 3)
        pygame.draw.line(surface, INK, p1, p2, w)

    def arrow_head(tip, left, right):
        # shadow then ink
        pygame.draw.polygon(surface, SHADOW, [tip, left, right])
        pygame.draw.polygon(surface, INK, [tip, left, right])

    if piece.special in ("row", "col"):
        # A bold stripe motif + arrows to indicate direction.
        pygame.draw.rect(surface, SHADOW, inner, border_radius=inner_radius)
        pygame.draw.rect(surface, INK, inner, width=2, border_radius=inner_radius)

        if piece.special == "row":
            y_mid = cy
            # stripes
            for off in (-10, 0, 10):
                thick_line((inner.left + 6, y_mid + off), (inner.right - 6, y_mid + off), 3)

            # arrows at ends
            tip_l = (inner.left + 6, y_mid)
            tip_r = (inner.right - 6, y_mid)
            arrow_head(tip_l, (tip_l[0] + 10, y_mid - 8), (tip_l[0] + 10, y_mid + 8))
            arrow_head(tip_r, (tip_r[0] - 10, y_mid - 8), (tip_r[0] - 10, y_mid + 8))

        else:  # "col"
            x_mid = cx
            for off in (-10, 0, 10):
                thick_line((x_mid + off, inner.top + 6), (x_mid + off, inner.bottom - 6), 3)

            tip_t = (x_mid, inner.top + 6)
            tip_b = (x_mid, inner.bottom - 6)
            arrow_head(tip_t, (x_mid - 8, tip_t[1] + 10), (x_mid + 8, tip_t[1] + 10))
            arrow_head(tip_b, (x_mid - 8, tip_b[1] - 10), (x_mid + 8, tip_b[1] - 10))

    elif piece.special == "bomb":
        # Bomb: starburst + fuse. Really hard to confuse with line clears.
        # backing disc
        pygame.draw.circle(surface, SHADOW, (cx, cy), int(r * 0.78))
        pygame.draw.circle(surface, INK, (cx, cy), int(r * 0.78), 2)

        # starburst spikes
        spikes = 10
        outer = int(r * 0.82)
        inner_r = int(r * 0.45)
        pts = []
        for i in range(spikes * 2):
            ang = i * (360 / (spikes * 2))
            rr = outer if i % 2 == 0 else inner_r
            v = pygame.Vector2(rr, 0).rotate(ang)
            pts.append((cx + v.x, cy + v.y))

        pygame.draw.polygon(surface, SHADOW, pts)
        pygame.draw.polygon(surface, INK, pts, 2)

        # center dot
        pygame.draw.circle(surface, INK, (cx, cy), 5)

        # fuse on top-right
        fuse_start = (cx + int(r * 0.35), cy - int(r * 0.35))
        fuse_end = (cx + int(r * 0.65), cy - int(r * 0.65))
        thick_line(fuse_start, fuse_end, 3)
        # spark
        pygame.draw.circle(surface, INK, fuse_end, 4)
        pygame.draw.circle(surface, SHADOW, fuse_end, 4, 2)
