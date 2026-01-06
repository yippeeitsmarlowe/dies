# ui.py
import pygame

class Button:
    def __init__(self, rect, text, font, on_click=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.on_click = on_click
        self.hover = False

    def handle_event(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                if self.on_click:
                    self.on_click()

    def draw(self, surf):
        bg = (70, 70, 85) if not self.hover else (95, 95, 120)
        pygame.draw.rect(surf, bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, (200, 200, 220), self.rect, width=2, border_radius=10)
        txt = self.font.render(self.text, True, (240, 240, 250))
        surf.blit(txt, txt.get_rect(center=self.rect.center))

def draw_panel(surf, rect):
    pygame.draw.rect(surf, (35, 35, 45), rect, border_radius=14)
    pygame.draw.rect(surf, (180, 180, 200), rect, width=2, border_radius=14)

def draw_text(surf, text, font, x, y, color=(240, 240, 250)):
    img = font.render(text, True, color)
    surf.blit(img, (x, y))
    return img.get_rect(topleft=(x, y))
