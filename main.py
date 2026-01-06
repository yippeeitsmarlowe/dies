# main.py
import pygame

from settings import SET
from ui import Button, draw_text, draw_panel
from save import load_save, write_save
from upgrades import UPGRADE_DEFS, upgrade_cost, buy_upgrade, apply_run_modifiers
from game import Game

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

    # Buttons for menu
    menu_buttons = []
    def rebuild_menu_buttons():
        nonlocal menu_buttons
        menu_buttons = []
        bx, by, bw, bh, gap = 330, 240, 240, 58, 16
        menu_buttons.append(Button((bx, by, bw, bh), "Play", fonts["ui"], on_click=start_game))
        menu_buttons.append(Button((bx, by + (bh+gap), bw, bh), "Upgrades", fonts["ui"], on_click=go_upgrades))
        menu_buttons.append(Button((bx, by + 2*(bh+gap), bw, bh), "Quit", fonts["ui"], on_click=lambda: pygame.event.post(pygame.event.Event(pygame.QUIT))))

    rebuild_menu_buttons()

    def draw_menu():
        screen.fill((18, 18, 24))
        draw_text(screen, "Match-3 Shapes", fonts["title"], 270, 120)
        draw_text(screen, f"Coins: {save_data['coins']}", fonts["ui"], 380, 175)
        for b in menu_buttons:
            b.draw(screen)
        draw_text(screen, "Tip: Bigger matches award bonus score.", fonts["small"], 305, 470, (210, 210, 225))
        draw_text(screen, "Earn 1 coin per 100 score.", fonts["small"], 328, 495, (210, 210, 225))

    def draw_upgrades():
        screen.fill((18, 18, 24))
        draw_text(screen, "Upgrades", fonts["title"], 360, 40)
        draw_text(screen, f"Coins: {save_data['coins']}", fonts["ui"], 60, 100)

        panel = pygame.Rect(50, 140, 800, 430)
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
                draw_text(screen, "MAXED", fonts["small"], panel.x + 640, y + 10, (245, 245, 255))
            else:
                draw_text(screen, f"Cost: {cost}", fonts["small"], panel.x + 640, y + 10, (245, 245, 255))
            y += 78

        draw_text(screen, "Click an upgrade row to buy it. ESC to return.", fonts["small"], 60, 590, (210, 210, 225))

    def handle_upgrades_click(pos):
        panel = pygame.Rect(50, 140, 800, 430)
        if not panel.collidepoint(pos):
            return
        row_h = 78
        rel_y = pos[1] - (panel.y + 18)
        idx = rel_y // row_h
        if 0 <= idx < len(UPGRADE_DEFS):
            defn = UPGRADE_DEFS[int(idx)]
            if buy_upgrade(save_data, defn):
                write_save(save_data)

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
