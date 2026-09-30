"""Keep window coordinates separate from physical display pixels.

pygame.display's software window does not request SDL_WINDOW_ALLOW_HIGHDPI.
The SDL2 window API does, so Retina can receive a full-resolution frame.
"""

from __future__ import annotations

import pygame


class GameDisplay:
    def __init__(self, size):
        self.size = tuple(size)
        self.window = None
        self.renderer = None
        self.texture = None
        self.surface = None
        # SDL's dummy driver has no physical display or high-DPI framebuffer.
        self.headless = pygame.display.get_driver() == "dummy"
        if self.headless:
            self.surface = pygame.display.set_mode(self.size)
        else:
            from pygame._sdl2.video import Renderer, Window

            class HighDPIWindow(Window):
                # Some pygame 2.6 wheels compile this SDL enum as zero in
                # their compatibility table. SDL2's flag is 0x00002000.
                # Override only our subclass, not pygame's global table.
                _kwarg_to_flag = {**Window._kwarg_to_flag,
                                  "allow_highdpi": 0x00002000}

            self.window = HighDPIWindow("Snake", size=self.size, allow_highdpi=True)
            self.renderer = Renderer(self.window, accelerated=-1, vsync=False)
            self.sync()

    @property
    def pixel_scale(self):
        pixels = self.surface.get_size()
        return (pixels[0] / self.size[0], pixels[1] / self.size[1])

    def sync(self):
        if self.headless:
            return self.surface
        # With no logical scaling or custom viewport, this is the renderer's
        # physical output size, including any Retina backing scale.
        self.size = tuple(self.window.size)
        self.renderer.set_viewport(None)
        pixels = self.renderer.get_viewport().size
        if self.surface is None or self.surface.get_size() != pixels:
            from pygame._sdl2.video import Texture

            self.surface = pygame.Surface(pixels, depth=32)
            self.texture = Texture.from_surface(self.renderer, self.surface)
        return self.surface

    def resize(self, size):
        self.size = tuple(size)
        if self.headless:
            self.surface = pygame.display.set_mode(self.size)
        else:
            self.window.size = self.size
        return self.sync()

    def set_icon(self, icon):
        if self.headless:
            pygame.display.set_icon(icon)
        else:
            self.window.set_icon(icon)

    def present(self):
        if self.headless:
            pygame.display.flip()
        else:
            self.texture.update(self.surface)
            self.renderer.clear()
            # Texture pixels map 1:1 to output pixels, never to window points.
            self.texture.draw(dstrect=self.surface.get_rect())
            self.renderer.present()

    def close(self):
        # Release textures/renderers before destroying their owning window.
        self.texture = None
        self.renderer = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
