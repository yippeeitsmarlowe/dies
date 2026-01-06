# game.py
import pygame
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Set, List

from settings import SET
from board import Board, draw_gem, Piece
from ui import draw_panel, draw_text
from utils import clamp

Pos = Tuple[int, int]

@dataclass
class Tween:
    pid: int
    start: pygame.Vector2
    end: pygame.Vector2

class Game:
    def __init__(self, upgrades_applied):
        self.time_limit = upgrades_applied["time_limit"]
        self.score_mult = upgrades_applied["score_mult"]
        self.num_types = upgrades_applied["num_types"]
        self.rerolls_left = upgrades_applied["rerolls"]

        self.board = Board(SET.GRID_SIZE, self.num_types)

        self.score = 0
        self.time_left = float(self.time_limit)
        self.over = False

        # ---- NEW: jeopardy ----
        self.doom = 0.0  # 0..1

        # selection + input lock
        self.selected: Optional[Pos] = None
        self.input_locked = False

        # animation system: per-piece render positions
        self.render_pos: Dict[int, pygame.Vector2] = {}
        self._sync_render_positions(spawn_from_above=False)


        # swap animation state
        self.swap_a: Optional[Pos] = None
        self.swap_b: Optional[Pos] = None
        self.swap_elapsed = 0.0
        self.swap_valid = False
        self.swap_reverting = False

        self.invalid_flash = 0.0

    # ----------------- coordinate helpers -----------------
    def tile_rect(self, x: int, y: int) -> pygame.Rect:
        return pygame.Rect(
            SET.BOARD_X + x * SET.TILE_SIZE + SET.BOARD_PADDING//2,
            SET.BOARD_Y + y * SET.TILE_SIZE + SET.BOARD_PADDING//2,
            SET.TILE_SIZE - SET.BOARD_PADDING,
            SET.TILE_SIZE - SET.BOARD_PADDING
        )

    def tile_center_px(self, x: int, y: int) -> pygame.Vector2:
        r = self.tile_rect(x, y)
        return pygame.Vector2(r.centerx, r.centery)

    def to_tile_at_pixel(self, mx, my):
        x0, y0 = SET.BOARD_X, SET.BOARD_Y
        size = SET.TILE_SIZE
        gx = (mx - x0) // size
        gy = (my - y0) // size
        if 0 <= gx < SET.GRID_SIZE and 0 <= gy < SET.GRID_SIZE:
            return int(gx), int(gy)
        return None

    # ----------------- scoring / doom -----------------
    def add_score_for_matches(self, cleared_count: int):
        base = cleared_count * 10
        if cleared_count >= 5:
            base += 25
        if cleared_count >= 8:
            base += 60
        gained = int(base * self.score_mult)
        self.score += gained

        # reduce doom when you clear things
        self.doom = max(0.0, self.doom - cleared_count * SET.DOOM_REDUCE_PER_CLEAR)

    def compute_coins_earned(self):
        return self.score // 100

    # ----------------- animation syncing -----------------
    def _sync_render_positions(self, spawn_from_above: bool):
        """
        Ensure every piece has a render position.
        - existing pieces keep their render position
        - new pieces (new pid) spawn above their column (for falling)
        """
        seen: Set[int] = set()
        for y in range(SET.GRID_SIZE):
            for x in range(SET.GRID_SIZE):
                p = self.board.grid[y][x]
                seen.add(p.pid)
                target = self.tile_center_px(x, y)
                if p.pid not in self.render_pos:
                    if spawn_from_above:
                        self.render_pos[p.pid] = pygame.Vector2(target.x, SET.BOARD_Y - SET.TILE_SIZE)
                    else:
                        self.render_pos[p.pid] = pygame.Vector2(target)

        # drop stale pids
        stale = [pid for pid in self.render_pos.keys() if pid not in seen]
        for pid in stale:
            del self.render_pos[pid]

    def _animate_towards_grid(self, dt: float, duration: float) -> bool:
        """
        Move all render positions towards their current grid cell centers.
        Returns True while any movement remains.
        """
        any_moving = False
        if duration <= 0:
            duration = 0.001

        for y in range(SET.GRID_SIZE):
            for x in range(SET.GRID_SIZE):
                p = self.board.grid[y][x]
                pid = p.pid
                cur = self.render_pos[pid]
                target = self.tile_center_px(x, y)
                delta = target - cur
                if delta.length_squared() > 0.25:
                    # exponential-ish smoothing using fraction per frame
                    step = min(1.0, dt / duration)
                    cur += delta * step
                    self.render_pos[pid] = cur
                    any_moving = True
                else:
                    self.render_pos[pid] = target

        return any_moving

    # ----------------- specials logic -----------------
    def _expand_by_specials(self, clear_set: Set[Pos]) -> Set[Pos]:
        """
        If a special piece is in clear_set, expand the clear_set according to its effect.
        Repeat until stable.
        """
        changed = True
        while changed:
            changed = False
            to_add: Set[Pos] = set()
            for (x, y) in list(clear_set):
                p = self.board.grid[y][x]
                if p.special == "row":
                    for cx in range(SET.GRID_SIZE):
                        to_add.add((cx, y))
                elif p.special == "col":
                    for cy in range(SET.GRID_SIZE):
                        to_add.add((x, cy))
                elif p.special == "bomb":
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < SET.GRID_SIZE and 0 <= ny < SET.GRID_SIZE:
                                to_add.add((nx, ny))
            before = len(clear_set)
            clear_set |= to_add
            if len(clear_set) != before:
                changed = True
        return clear_set

    def _choose_special_spawn(self, group_positions: List[Pos]) -> Pos:
        """
        Prefer to spawn the special where the player swapped, if possible.
        """
        if self.swap_a in group_positions:
            return self.swap_a
        if self.swap_b in group_positions:
            return self.swap_b
        return group_positions[len(group_positions)//2]

    def _resolve_once(self) -> int:
        """
        Resolve one cascade step:
        - find match groups
        - create specials for 4 and 5+
        - clear all matches (expanded by special triggers)
        - collapse + refill
        Return number of cleared tiles
        """
        groups = self.board.find_match_groups(min_len=SET.MIN_MATCH)
        if not groups:
            return 0

        # Build clear set from all match cells
        clear_set: Set[Pos] = set()
        for _, pos in groups:
            clear_set |= set(pos)

        # Decide specials to create (one per group)
        specials_to_create: List[Tuple[Pos, str]] = []
        for orient, pos in groups:
            L = len(pos)
            if L == 4:
                spawn = self._choose_special_spawn(pos)
                specials_to_create.append((spawn, "row" if orient == "h" else "col"))
            elif L >= 5:
                spawn = self._choose_special_spawn(pos)
                specials_to_create.append((spawn, "bomb"))

        # Keep the spawned special pieces instead of clearing them
        for (spawn_pos, sp) in specials_to_create:
            if spawn_pos in clear_set:
                clear_set.remove(spawn_pos)

        # Expand by special triggers if any specials are being cleared
        clear_set = self._expand_by_specials(clear_set)

        # Now apply clearing
        cleared_count = len(clear_set)
        for (x, y) in clear_set:
            self.board.grid[y][x] = None  # hole

        # Apply specials creation at their spawn positions
        for (x, y), sp in specials_to_create:
            # If that spot got cleared by expansion, re-create a piece there as special.
            # Otherwise upgrade the existing piece.
            if self.board.grid[y][x] is None:
                # create a fresh piece with a random kind for visual variety
                # (it doesn't matter too much since it's special)
                from board import Piece  # avoid circular in type checkers
                # we want to reuse board's PID generator; easiest: new normal piece then set special
                self.board.grid[y][x] = self.board._new_piece()
            self.board.grid[y][x].special = sp

        # Collapse and refill
        self.board.collapse_and_refill()
        return cleared_count

    def _resolve_all_cascades(self) -> int:
        total = 0
        while True:
            cleared = self._resolve_once()
            if cleared <= 0:
                break
            total += cleared
        if not self.board.has_any_moves():
            self.board.reroll_board()
        return total

    # ----------------- input handlers -----------------
    def handle_click(self, pos):
        if self.over or self.input_locked:
            return
        tile = self.to_tile_at_pixel(*pos)
        if tile is None:
            return

        if self.selected is None:
            self.selected = tile
            return

        sx, sy = self.selected
        tx, ty = tile
        if (abs(sx - tx) + abs(sy - ty)) != 1:
            self.selected = tile
            return

        # Start swap animation
        self.swap_a, self.swap_b = self.selected, tile
        self.selected = None
        self.swap_elapsed = 0.0
        self.swap_reverting = False
        self.input_locked = True

        # perform the logical swap immediately; animation will follow render positions
        self.board.swap(self.swap_a, self.swap_b)

        # determine validity
        self.swap_valid = len(self.board.find_match_groups(min_len=SET.MIN_MATCH)) > 0

        # ensure render positions exist for all
        self._sync_render_positions(spawn_from_above=False)

    def handle_key(self, key):
        if self.over or self.input_locked:
            return
        if key == pygame.K_r and self.rerolls_left > 0:
            self.rerolls_left -= 1
            self.board.reroll_board()
            self._sync_render_positions(spawn_from_above=True)

    # ----------------- update loop -----------------
    def update(self, dt):
        if self.over:
            return

        # doom rises over time (jeopardy)
        self.doom = min(1.0, self.doom + SET.DOOM_RATE_PER_SEC * dt)
        if self.doom >= 1.0:
            self.over = True
            self.time_left = max(0.0, self.time_left)
            return

        # time ticks down
        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0
            self.over = True
            return

        if self.invalid_flash > 0:
            self.invalid_flash = max(0.0, self.invalid_flash - dt)

        # ---- swap animation phase ----
        if self.input_locked and self.swap_a and self.swap_b and not self.swap_reverting:
            self.swap_elapsed += dt
            t = clamp(self.swap_elapsed / SET.SWAP_ANIM_TIME, 0.0, 1.0)

            ax, ay = self.swap_a
            bx, by = self.swap_b

            # identify swapped pieces in current grid positions
            pa = self.board.grid[ay][ax]  # after logical swap, this is piece that moved into A
            pb = self.board.grid[by][bx]  # moved into B

            a_center = self.tile_center_px(ax, ay)
            b_center = self.tile_center_px(bx, by)

            # render positions: interpolate between centers
            self.render_pos[pa.pid] = b_center.lerp(a_center, t)  # moving towards A
            self.render_pos[pb.pid] = a_center.lerp(b_center, t)  # moving towards B

            if t >= 1.0:
                # lock them to centers
                self.render_pos[pa.pid] = a_center
                self.render_pos[pb.pid] = b_center

                if self.swap_valid:
                    # Resolve cascades, then fall animation
                    total_cleared = self._resolve_all_cascades()
                    if total_cleared > 0:
                        self.add_score_for_matches(total_cleared)

                    # spawn new pieces above and animate falling
                    self._sync_render_positions(spawn_from_above=True)

                    # switch to falling motion (still locked)
                    self.swap_a = None
                    self.swap_b = None
                    self.swap_elapsed = 0.0
                    self.swap_valid = False
                    self.swap_reverting = True  # reuse flag to mean "fall phase"
                else:
                    # invalid: swap back logically and animate back quickly
                    self.board.swap((ax, ay), (bx, by))
                    self.invalid_flash = 0.18
                    self.time_left = max(0.0, self.time_left - SET.INVALID_SWAP_TIME_PENALTY)

                    # Now animate back: keep lock, but mark as reverting
                    self.swap_elapsed = 0.0
                    self.swap_reverting = True

        # ---- reverting swap (invalid) OR falling phase (valid) ----
        elif self.input_locked and self.swap_reverting:
            # if swap_a/swap_b still exist, it's invalid revert animation
            if self.swap_a and self.swap_b:
                self.swap_elapsed += dt
                t = clamp(self.swap_elapsed / (SET.SWAP_ANIM_TIME * 0.85), 0.0, 1.0)

                ax, ay = self.swap_a
                bx, by = self.swap_b
                pa = self.board.grid[ay][ax]
                pb = self.board.grid[by][bx]

                a_center = self.tile_center_px(ax, ay)
                b_center = self.tile_center_px(bx, by)

                self.render_pos[pa.pid] = b_center.lerp(a_center, t)
                self.render_pos[pb.pid] = a_center.lerp(b_center, t)

                if t >= 1.0:
                    self.render_pos[pa.pid] = a_center
                    self.render_pos[pb.pid] = b_center
                    self.swap_a = None
                    self.swap_b = None
                    self.swap_reverting = False
                    self.input_locked = False
                    self._sync_render_positions(spawn_from_above=False)
            else:
                # falling phase: move all pieces to their grid positions
                still_moving = self._animate_towards_grid(dt, SET.FALL_ANIM_TIME)
                if not still_moving:
                    self.swap_reverting = False
                    self.input_locked = False
                    self._sync_render_positions(spawn_from_above=False)

    # ----------------- drawing -----------------
    def draw(self, screen, fonts):
        screen.fill((18, 18, 24))
        title_font = fonts["title"]
        ui_font = fonts["ui"]
        small_font = fonts["small"]

        draw_text(screen, "Match-3 Shapes", title_font, 60, 22)

        board_px = pygame.Rect(
            SET.BOARD_X, SET.BOARD_Y,
            SET.GRID_SIZE * SET.TILE_SIZE,
            SET.GRID_SIZE * SET.TILE_SIZE
        )
        pygame.draw.rect(screen, (28, 28, 38), board_px, border_radius=14)
        pygame.draw.rect(screen, (170, 170, 190), board_px, width=2, border_radius=14)

        # draw tiles background
        for y in range(SET.GRID_SIZE):
            for x in range(SET.GRID_SIZE):
                cell = self.tile_rect(x, y)
                pygame.draw.rect(screen, (40, 40, 55), cell, border_radius=10)

        # draw pieces using render_pos (animated)
        for y in range(SET.GRID_SIZE):
            for x in range(SET.GRID_SIZE):
                p = self.board.grid[y][x]
                cell = self.tile_rect(x, y)
                # move the rect center to animated position
                rp = self.render_pos.get(p.pid, pygame.Vector2(cell.center))
                draw_rect = cell.copy()
                draw_rect.center = (int(rp.x), int(rp.y))
                draw_gem(screen, draw_rect, p)

        # selection highlight
        if self.selected is not None:
            sx, sy = self.selected
            sel = self.tile_rect(sx, sy)
            pygame.draw.rect(screen, (245, 245, 255), sel, width=4, border_radius=10)

        # invalid swap flash
        if self.invalid_flash > 0:
            alpha = int(180 * (self.invalid_flash / 0.18))
            overlay = pygame.Surface((board_px.width, board_px.height), pygame.SRCALPHA)
            overlay.fill((255, 80, 80, alpha))
            screen.blit(overlay, board_px.topleft)

        # side panel
        panel = pygame.Rect(SET.PANEL_X, SET.PANEL_Y, SET.PANEL_W, SET.PANEL_H)
        draw_panel(screen, panel)

        draw_text(screen, f"Score: {self.score}", ui_font, panel.x + 18, panel.y + 20)
        draw_text(screen, f"Time:  {int(self.time_left)}s", ui_font, panel.x + 18, panel.y + 60)
        draw_text(screen, f"Rerolls: {self.rerolls_left} (press R)", small_font, panel.x + 18, panel.y + 105)

        # Doom meter
        draw_text(screen, "Doom", ui_font, panel.x + 18, panel.y + 150)
        bar_x, bar_y = panel.x + 18, panel.y + 185
        bar_w, bar_h = panel.w - 36, 18
        pygame.draw.rect(screen, (55, 55, 70), (bar_x, bar_y, bar_w, bar_h), border_radius=10)
        pygame.draw.rect(screen, (240, 240, 250), (bar_x, bar_y, int(bar_w * self.doom), bar_h), border_radius=10)
        draw_text(screen, "Clears reduce doom; it rises over time.", small_font, panel.x + 18, panel.y + 212, (210, 210, 225))

        draw_text(screen, "Specials:", ui_font, panel.x + 18, panel.y + 255)
        draw_text(screen, "- Match 4: line clear", small_font, panel.x + 18, panel.y + 290, (210, 210, 225))
        draw_text(screen, "- Match 5+: bomb (3x3)", small_font, panel.x + 18, panel.y + 315, (210, 210, 225))
        draw_text(screen, "Tip: Invalid swaps cost time!", small_font, panel.x + 18, panel.y + 350, (210, 210, 225))

        # time bar
        tbar_x, tbar_y = panel.x + 18, panel.y + 410
        tbar_w, tbar_h = panel.w - 36, 18
        pygame.draw.rect(screen, (55, 55, 70), (tbar_x, tbar_y, tbar_w, tbar_h), border_radius=10)
        pct = 0 if self.time_limit <= 0 else self.time_left / self.time_limit
        pct = clamp(pct, 0.0, 1.0)
        pygame.draw.rect(screen, (240, 240, 250), (tbar_x, tbar_y, int(tbar_w * pct), tbar_h), border_radius=10)
        draw_text(screen, "Time remaining", small_font, tbar_x, tbar_y - 22)

        if self.over:
            earned = self.compute_coins_earned()
            if self.doom >= 1.0:
                msg1 = "YOU LOSE!"
            else:
                msg1 = "TIME UP!"
            msg2 = f"Final score: {self.score}"
            msg3 = f"Coins earned: {earned}"
            msg4 = "Press ESC to return to menu"
            cx = board_px.centerx
            cy = board_px.centery
            card = pygame.Rect(0, 0, 440, 230)
            card.center = (cx, cy)
            pygame.draw.rect(screen, (12, 12, 16), card, border_radius=16)
            pygame.draw.rect(screen, (220, 220, 235), card, width=2, border_radius=16)
            screen.blit(ui_font.render(msg1, True, (245, 245, 255)), (card.x + 24, card.y + 24))
            screen.blit(small_font.render(msg2, True, (240, 240, 250)), (card.x + 24, card.y + 80))
            screen.blit(small_font.render(msg3, True, (240, 240, 250)), (card.x + 24, card.y + 110))
            screen.blit(small_font.render(msg4, True, (210, 210, 225)), (card.x + 24, card.y + 165))