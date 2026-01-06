# main.py
import pygame

from src.settings import SET
from src.ui import Button, draw_text, draw_panel
from src.save import load_save, write_save
from src.upgrades import UPGRADE_DEFS, upgrade_cost, buy_upgrade, apply_run_modifiers
from src.game import Game

STATE_MENU = "menu"
STATE_UPGRADES = "upgrades"
STATE_GAME = "game"


def make_fonts():
    return {
        "title": pygame.font.SysFont("arialblack", 34),
        "ui": pygame.font.SysFont("arial", 24, bold=True),
        "small": pygame.font.SysFont("arial", 18),
    }


def main():
    pygame.init()
    screen = pygame.display.set_mode((SET.WIDTH, SET.HEIGHT))
    pygame.display.set_caption(SET.TITLE)
    clock = pygame.time.Clock()
    fonts = make_fonts()

    save_data = load_save()

    state = STATE_MENU
    game = None

    CENTER_X = SET.WIDTH // 2

    # ---------- Navigation ----------
    def start_game():
        nonlocal state, game, save_data
        time_limit, score_mult, colors, rerolls = apply_run_modifiers(SET, save_data["upgrades"])
        game = Game({
            "time_limit": time_limit,
            "score_mult": score_mult,
            "num_types": colors,
            "rerolls": rerolls,
        })
        state = STATE_GAME

    def go_menu():
        nonlocal state
        state = STATE_MENU

    def go_upgrades():
        nonlocal state
        state = STATE_UPGRADES

    # ---------- Menu Buttons ----------
    menu_buttons = []

    def rebuild_menu_buttons():
        nonlocal menu_buttons
        menu_buttons = []

        bw, bh, gap = 320, 66, 18
        start_y = 265

        labels = [
            ("Play", start_game),
            ("Upgrades", go_upgrades),
            ("Quit", lambda: pygame.event.post(pygame.event.Event(pygame.QUIT))),
        ]

        for i, (text, action) in enumerate(labels):
            rect = pygame.Rect(0, 0, bw, bh)
            rect.center = (CENTER_X, start_y + i * (bh + gap))
            menu_buttons.append(Button(rect, text, fonts["ui"], on_click=action))

    rebuild_menu_buttons()

    # ---------- Screens ----------
    def draw_menu():
        screen.fill((18, 18, 24))

        # Title
        title_surf = fonts["title"].render("Match-3 Shapes", True, (245, 245, 255))
        title_rect = title_surf.get_rect(center=(CENTER_X, 150))
        screen.blit(title_surf, title_rect)

        # Coins
        coins_surf = fonts["ui"].render(f"Coins: {save_data['coins']}", True, (220, 220, 235))
        coins_rect = coins_surf.get_rect(center=(CENTER_X, 200))
        screen.blit(coins_surf, coins_rect)

        # Buttons
        for b in menu_buttons:
            b.draw(screen)

        # Tips
        tip_lines = [
            "Tip: Bigger matches award bonus score.",
            "Earn 1 coin per 100 score.",
        ]
        y = 545
        for line in tip_lines:
            tip_surf = fonts["small"].render(line, True, (200, 200, 215))
            tip_rect = tip_surf.get_rect(center=(CENTER_X, y))
            screen.blit(tip_surf, tip_rect)
            y += 26

    def draw_upgrades():
        screen.fill((18, 18, 24))

        # Title
        title_surf = fonts["title"].render("Upgrades", True, (245, 245, 255))
        title_rect = title_surf.get_rect(center=(CENTER_X, 70))
        screen.blit(title_surf, title_rect)

        # Coins
        coins_surf = fonts["ui"].render(f"Coins: {save_data['coins']}", True, (220, 220, 235))
        screen.blit(coins_surf, (60, 110))

        # Panel
        panel = pygame.Rect(50, 150, 800, 420)
        draw_panel(screen, panel)

        y = panel.y + 18
        for defn in UPGRADE_DEFS:
            lvl = int(save_data["upgrades"].get(defn.key, 0))
            maxed = lvl >= defn.max_level
            cost = upgrade_cost(defn, lvl) if not maxed else 0

            name = f"{defn.name}  (Lv {lvl}/{defn.max_level})"
            draw_text(screen, name, fonts["ui"], panel.x + 18, y)
            draw_text(screen, defn.desc, fonts["small"], panel.x + 18, y + 30, (210, 210, 225))

            if maxed:
                draw_text(screen, "MAXED", fonts["small"], panel.x + 650, y + 10, (245, 245, 255))
            else:
                draw_text(screen, f"Cost: {cost}", fonts["small"], panel.x + 650, y + 10, (245, 245, 255))

            y += 78

        footer = "Click an upgrade row to buy it. ESC to return."
        footer_surf = fonts["small"].render(footer, True, (210, 210, 225))
        footer_rect = footer_surf.get_rect(center=(CENTER_X, 610))
        screen.blit(footer_surf, footer_rect)

    def handle_upgrades_click(pos):
        panel = pygame.Rect(50, 150, 800, 420)
        if not panel.collidepoint(pos):
            return
        row_h = 78
        rel_y = pos[1] - (panel.y + 18)
        idx = rel_y // row_h
        if 0 <= idx < len(UPGRADE_DEFS):
            defn = UPGRADE_DEFS[int(idx)]
            if buy_upgrade(save_data, defn):
                write_save(save_data)

    # ---------- Main Loop ----------
    running = True
    while running:
        dt = clock.tick(SET.FPS) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            if state == STATE_MENU:
                for b in menu_buttons:
                    b.handle_event(e)

            elif state == STATE_UPGRADES:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    go_menu()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    handle_upgrades_click(e.pos)

            elif state == STATE_GAME:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        # cash out coins if game ended (or allow early exit without coins)
                        if game and game.over:
                            earned = game.compute_coins_earned()
                            save_data["coins"] += earned
                            write_save(save_data)
                        go_menu()
                    else:
                        game.handle_key(e.key)

                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    game.handle_click(e.pos)

        # update/draw
        if state == STATE_MENU:
            draw_menu()

        elif state == STATE_UPGRADES:
            draw_upgrades()

        elif state == STATE_GAME:
            game.update(dt)
            game.draw(screen, fonts)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()