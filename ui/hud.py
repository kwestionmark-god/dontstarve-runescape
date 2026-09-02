"""
hud.py — Minimalist HUD (hunger + HP bars + notifications).

Always-visible hunger bar and HP bar at the top-left of the screen.
Updates each frame based on survival system state.
Also renders action notifications (level-ups, resource yields, etc.)
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from survival.survival_system import SurvivalSystem
    from actions import ActionNotification
    from render.sprite_renderer import SpriteRenderer


class HUD:
    """
    Always-visible hunger and HP bars at the top-left of the screen.

    Layout:
    ┌──────────────────────────────────────────────────────┐
    │ [████████████████░░░░░░░░░░░░░░░] Hunger 65%         │
    │ [██████████████████████░░░░░░░░] HP 75%              │
    └──────────────────────────────────────────────────────┘

    Bars: 200px wide, 16px tall each, spaced 4px apart.
    """

    BAR_WIDTH = 200
    BAR_HEIGHT = 16
    BAR_SPACING = 4
    MARGIN_X = 10
    MARGIN_Y = 10

    # Colors
    BG_COLOR = (24, 26, 32)        # Bar background
    BORDER_COLOR = (70, 74, 86)    # Bar border
    PANEL_COLOR = (14, 16, 20, 190)      # Translucent backing panel fill
    PANEL_BORDER_COLOR = (64, 68, 80, 200)  # Panel border

    # Notification fade timings (seconds)
    NOTIF_FADE_IN = 0.15
    NOTIF_FADE_OUT = 0.40

    # ── Action / stamina references (set via setters) ─────────────────
    _action_system: object | None = None  # player.action_system
    _seasonal_hud: object | None = None   # SeasonalHUD instance (optional)
    _season_system: object | None = None  # SeasonSystem reference (for season/progress)
    _weather_system: object | None = None  # WeatherSystem reference (for weather/forecast)

    def __init__(
        self,
        screen: pygame.Surface,
        survival: "SurvivalSystem | None" = None,
        inventory: object | None = None,
        faction_system: object | None = None,
        npc_system: object | None = None,
        sprite_renderer: "SpriteRenderer | None" = None,
    ) -> None:
        """
        Initialize the HUD.

        Args:
            screen: The pygame display surface (for font creation).
            survival: Optional survival system reference for rendering.
            inventory: Optional inventory reference (for gold display).
            faction_system: Optional faction system reference (for status bar).
            npc_system: Optional NPC system reference (for alert icon).
            sprite_renderer: Optional sprite renderer for rendering item icons.
        """
        self.screen = screen
        self.survival = survival
        self.inventory = inventory
        self.faction_system = faction_system
        self.npc_system = npc_system
        self.sprite_renderer: "SpriteRenderer | None" = sprite_renderer
        self.player: object | None = None  # Set via set_player()
        from render.font_cache import get_monospace, get_monospace_bold
        self.font = get_monospace(12)
        self.font_bold = get_monospace_bold(14)
        self._notifications: list[ActionNotification] = []
        self._active_action_progress: float = 0.0
        self._active_action_skill: str = ""
        # Combat damage flash overlay
        self._damage_flash: float = 0.0  # 0.0 = no flash, 1.0 = full red
        # NPC alert blink timer (10Hz pulse)
        self._npc_alert_timer: float = 0.0
        # Hotbar
        self._hotbar_selected: int = -1  # 0-7 slot index, -1 = none
        self._hotbar_hover: int = -1
        self._hotbar_rects: list[pygame.Rect] = []
        self._hotbar_mouse_x: int = 0
        self._hotbar_mouse_y: int = 0

    def set_survival(self, survival: "SurvivalSystem") -> None:
        """Update the survival system reference after initialization."""
        self.survival = survival

    def set_player(self, player: object) -> None:
        """Update the player reference for HUD proximity checks."""
        self.player = player
        # The action system is accessible via the player's action_system attribute.
        # We set it lazily here so the HUD can draw the stamina bar and action
        # progress without the game needing to pass it explicitly each frame.
        self._action_system = getattr(player, "action_system", None)

    def set_action_system(self, action_system: object) -> None:
        """Explicitly set the action system reference (used if set_player misses it)."""
        self._action_system = action_system

    def set_seasonal_hud(self, seasonal_hud: object) -> None:
        """Set the SeasonalHUD instance for season/weather display."""
        self._seasonal_hud = seasonal_hud

    def set_season_system(self, season_system: object) -> None:
        """Set the SeasonSystem reference for season/progress/weather data."""
        self._season_system = season_system

    def set_weather_system(self, weather_system: object) -> None:
        """Set the WeatherSystem reference for weather/forecast data."""
        self._weather_system = weather_system

    def set_faction_system(self, faction_system: object) -> None:
        """Update the faction system reference (wired after NPC system is built)."""
        self.faction_system = faction_system

    def set_npc_system(self, npc_system: object) -> None:
        """Update the NPC system reference (wired after NPC system is built)."""
        self.npc_system = npc_system

    def set_sprite_renderer(self, sprite_renderer: "SpriteRenderer") -> None:
        """Update the sprite renderer reference (wired after the real renderer is built)."""
        self.sprite_renderer = sprite_renderer

    def get_action_system(self) -> object | None:
        """Return the action system, for convenience."""
        if self._action_system is None and self.player is not None:
            self._action_system = getattr(self.player, "action_system", None)
        return self._action_system

    def set_hotbar_hover(self, slot: int, x: int = 0, y: int = 0) -> None:
        """
        Update the hotbar hover slot index (called from InputRouter).

        Args:
            slot: Hovered slot index (-1 = none).
            x: Mouse X coordinate (for tooltip positioning).
            y: Mouse Y coordinate (for tooltip positioning).
        """
        self._hotbar_hover = slot
        if slot >= 0:
            self._hotbar_mouse_x = x
            self._hotbar_mouse_y = y

    def set_hotbar_selected(self, slot: int) -> None:
        """Update the hotbar selected slot index."""
        self._hotbar_selected = slot

    def set_notifications(
        self, notifications: list[ActionNotification],
    ) -> None:
        """
        Update the notification queue from the action system.

        Args:
            notifications: List of active notifications to display.
        """
        self._notifications = notifications

    def tick_notifications(self, dt: float) -> None:
        """
        Tick notification lifetimes. Removes expired notifications,
        keeping them alive through the fade-out period so they fully
        disappear before being removed.
        Also ticks damage flash overlay and NPC alert blink timer.

        Args:
            dt: Delta time in seconds.
        """
        # Keep notifications alive until they have fully faded out
        fade_buffer = self.NOTIF_FADE_OUT
        self._notifications = [
            n for n in self._notifications
            if n.elapsed < n.duration + fade_buffer
        ]
        # Decay damage flash
        if self._damage_flash > 0:
            self._damage_flash -= dt * 2.0  # Fade out over ~0.5s
            self._damage_flash = max(0.0, self._damage_flash)

        # NPC alert blink timer (10Hz pulse)
        if self.npc_system is not None and self.player is not None:
            is_nearby = self.npc_system.is_any_npc_nearby(
                self.player.world_x, self.player.world_y,
            )
            if is_nearby:
                self._npc_alert_timer += dt

    def trigger_damage_flash(self) -> None:
        """Trigger a red damage flash overlay (called on player take damage)."""
        self._damage_flash = 1.0

    def set_action_progress(
        self, progress: float, skill: str,
    ) -> None:
        """
        Set contextual XP display info for active actions.

        Args:
            progress: Action progress 0.0–1.0.
            skill: Skill name (e.g. "Woodcutting", "Mining").
        """
        self._active_action_progress = progress
        self._active_action_skill = skill

    def _get_hunger_color(self, percent: float) -> tuple[int, int, int]:
        """
        Return hunger bar color based on depletion level.

        Green (full) → Yellow (50%) → Red (0%).

        Args:
            percent: Hunger as 0–1 ratio.

        Returns:
            RGB color tuple.
        """
        if percent > 0.5:
            # Green to yellow: (0, 200, 0) → (200, 200, 0)
            t = (percent - 0.5) * 2  # 0→1
            r = int(200 * (1 - t))
            g = 200
            b = 0
        else:
            # Yellow to red: (200, 200, 0) → (200, 0, 0)
            t = percent * 2  # 1→0
            r = 200
            g = int(200 * t)
            b = 0
        return (r, g, b)

    def _get_hp_color(self, percent: float) -> tuple[int, int, int]:
        """
        Return HP bar color based on depletion level.

        Bright red (full) → Dark red (0%).

        Args:
            percent: HP as 0–1 ratio.

        Returns:
            RGB color tuple.
        """
        if percent > 0.5:
            # Bright red to medium red
            t = (percent - 0.5) * 2
            r = int(180 + 75 * (1 - t))
            g = int(50 * (1 - t))
            b = int(50 * (1 - t))
        else:
            # Medium red to dark red
            t = percent * 2
            r = int(180 * t + 80 * (1 - t))
            g = int(50 * t)
            b = int(50 * t)
        return (r, g, b)

    def _draw_bar(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        fill_percent: float,
        bar_color: tuple[int, int, int],
        label: str,
    ) -> None:
        """
        Draw a single bar with background, fill, border, and label.

        Args:
            screen: The display surface.
            x: Top-left X coordinate.
            y: Top-left Y coordinate.
            width: Bar width in pixels.
            height: Bar height in pixels.
            fill_percent: Fill ratio (0.0–1.0).
            bar_color: Fill color (RGB).
            label: Text label (e.g. "Hunger 65%").
        """
        # Background
        pygame.draw.rect(screen, self.BG_COLOR, (x, y, width, height), border_radius=3)

        # Fill (with a one-pixel lighter highlight along the top edge)
        fill_width = int(width * max(0.0, min(1.0, fill_percent)))
        if fill_width > 0:
            pygame.draw.rect(screen, bar_color, (x, y, fill_width, height), border_radius=3)
            hi = tuple(min(255, c + 40) for c in bar_color)
            pygame.draw.rect(screen, hi, (x, y, fill_width, max(2, height // 4)), border_radius=3)

        # Border
        pygame.draw.rect(screen, self.BORDER_COLOR, (x, y, width, height), 1, border_radius=3)

        # Label, centred inside the bar so it doesn't float over the world
        text_surf = self.font.render(label, True, (255, 255, 255))
        text_x = x + (width - text_surf.get_width()) // 2
        text_y = y + (height - text_surf.get_height()) // 2
        # Drop shadow for readability over bright fills
        shadow = self.font.render(label, True, (0, 0, 0))
        screen.blit(shadow, (text_x + 1, text_y + 1))
        screen.blit(text_surf, (text_x, text_y))

    def _draw_stamina_bar(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        action_sys: object,
    ) -> None:
        """
        Draw the stamina bar below the faction bar.

        Shows current/max stamina with a color gradient
        (green = full → yellow = 50% → red = exhausted).

        Args:
            screen: The display surface.
            x: Top-left X coordinate.
            y: Top-left Y coordinate.
            action_sys: The ActionSystem with a StaminaPool.
        """
        pool = action_sys.stamina
        max_stamina = pool.max_stamina
        current = pool.current
        percent = current / max_stamina if max_stamina > 0 else 0.0
        percent = max(0.0, min(1.0, percent))

        # Color gradient: green (full) → yellow (50%) → red (0%)
        if percent > 0.5:
            # Green to yellow
            t = (percent - 0.5) * 2.0  # 0→1
            r = int(200 * (1 - t))
            g = 200
            b = 0
        else:
            # Yellow to red
            t = percent * 2.0  # 1→0
            r = 200
            g = int(200 * t)
            b = 0
        stamina_color = (r, g, b)

        # Background
        pygame.draw.rect(screen, self.BG_COLOR, (x, y, self.BAR_WIDTH, self.BAR_HEIGHT), border_radius=3)
        # Fill
        fill_width = int(self.BAR_WIDTH * percent)
        if fill_width > 0:
            pygame.draw.rect(screen, stamina_color, (x, y, fill_width, self.BAR_HEIGHT), border_radius=3)
            hi = tuple(min(255, c + 40) for c in stamina_color)
            pygame.draw.rect(screen, hi, (x, y, fill_width, max(2, self.BAR_HEIGHT // 4)), border_radius=3)
        # Border
        pygame.draw.rect(screen, self.BORDER_COLOR, (x, y, self.BAR_WIDTH, self.BAR_HEIGHT), 1, border_radius=3)

        # Label centred inside the bar (with drop shadow)
        label = f"Stamina {int(current):.0f}/{int(max_stamina):.0f}"
        label_surf = self.font.render(label, True, (255, 255, 255))
        lx = x + (self.BAR_WIDTH - label_surf.get_width()) // 2
        ly = y + (self.BAR_HEIGHT - label_surf.get_height()) // 2
        shadow = self.font.render(label, True, (0, 0, 0))
        screen.blit(shadow, (lx + 1, ly + 1))
        screen.blit(label_surf, (lx, ly))

    def _get_notification_alpha(self, notif: object) -> float:
        """
        Compute fade alpha for a notification based on elapsed time.

        Fades in over NOTIF_FADE_IN seconds, stays fully visible,
        then fades out over NOTIF_FADE_OUT seconds before removal.

        Args:
            notif: The ActionNotification to compute alpha for.

        Returns:
            Alpha value in [0.0, 1.0].
        """
        elapsed = notif.elapsed
        duration = notif.duration
        if duration <= 0:
            return 0.0

        # Fade in
        if elapsed < self.NOTIF_FADE_IN:
            return elapsed / self.NOTIF_FADE_IN
        # Fade out
        fade_out_start = duration - self.NOTIF_FADE_OUT
        if elapsed > fade_out_start:
            remaining = duration - elapsed
            alpha = remaining / self.NOTIF_FADE_OUT
            return max(0.0, min(1.0, alpha))
        # Fully visible
        return 1.0

    def _render_hotbar(self, screen: pygame.Surface) -> None:
        """Render the 8-slot hotbar at the bottom-center of the screen."""
        from data import load_json_list

        SLOT_COUNT = 8
        CELL_W = 56
        CELL_H = 44
        GAP = 4
        BAR_H = CELL_H + 8
        total_w = SLOT_COUNT * (CELL_W + GAP) - GAP
        bar_x = (screen.get_width() - total_w) // 2
        bar_y = screen.get_height() - BAR_H - 10

        # Background
        pygame.draw.rect(screen, (30, 30, 40), (bar_x - 4, bar_y - 4, total_w + 8, BAR_H + 8))
        pygame.draw.rect(screen, (80, 80, 100), (bar_x - 4, bar_y - 4, total_w + 8, BAR_H + 8), 1)

        # Build hotbar item list (first 8 non-empty inventory slots)
        items = []
        for slot in self.inventory.slots:
            if slot is not None and slot.item_id is not None and slot.quantity > 0:
                items.append(slot)
            if len(items) >= SLOT_COUNT:
                break

        # Fallback color map by item type (used when no sprite available)
        items_data = load_json_list("items.json", "items")
        _item_colors: dict[str, tuple[int, int, int]] = {}
        for d in items_data:
            iid = d.get("id", "")
            if d.get("is_food", False):
                _item_colors[iid] = (200, 80, 80)
            elif d.get("is_equippable", False):
                _item_colors[iid] = (100, 120, 200)
            elif d.get("is_currency", False):
                _item_colors[iid] = (255, 215, 0)
        default_color = (120, 120, 140)

        self._hotbar_rects = []
        self._hotbar_item_ids: list[str | None] = []
        for i in range(SLOT_COUNT):
            cell_x = bar_x + i * (CELL_W + GAP)
            cell_y = bar_y
            rect = pygame.Rect(cell_x, cell_y, CELL_W, CELL_H)
            self._hotbar_rects.append(rect)
            self._hotbar_item_ids.append(items[i].item_id if i < len(items) else None)

            # Cell background
            is_selected = (i == self._hotbar_selected)
            is_hovered = (i == self._hotbar_hover)
            if is_selected:
                cell_color = (60, 60, 80)
            elif is_hovered:
                cell_color = (50, 50, 70)
            else:
                cell_color = (40, 40, 55)
            pygame.draw.rect(screen, cell_color, rect)

            # Border
            border_color = (140, 140, 170) if is_selected else (80, 80, 100)
            pygame.draw.rect(screen, border_color, rect, 2 if is_selected else 1)

            # Slot number
            num_surf = self.font.render(str(i + 1), True, (100, 100, 120))
            screen.blit(num_surf, (cell_x + 2, cell_y + 2))

            if i < len(items):
                slot = items[i]
                color = _item_colors.get(slot.item_id, default_color)

                # Render item sprite if available, otherwise fall back to colored icon
                if self.sprite_renderer is not None:
                    sprite_key = None
                    for d in items_data:
                        if d.get("id") == slot.item_id:
                            sprite_key = d.get("sprite_key")
                            break
                    if sprite_key:
                        sprite = self.sprite_renderer._get_base_sprite(sprite_key)
                        if sprite is not None:
                            # Scale sprite to fit within cell
                            icon_size = 28
                            icon_x = cell_x + (CELL_W - icon_size) // 2
                            icon_y = cell_y + 10
                            sw = sprite.get_width()
                            sh = sprite.get_height()
                            scale = min(icon_size / sw, icon_size / sh) if sw > 0 and sh > 0 else 1.0
                            new_w = max(1, int(sw * scale))
                            new_h = max(1, int(sh * scale))
                            sprite = pygame.transform.scale(sprite, (new_w, new_h))
                            screen.blit(sprite, (icon_x + (icon_size - new_w) // 2, icon_y + (icon_size - new_h) // 2))
                        else:
                            # Fallback colored square
                            pygame.draw.rect(screen, color, (icon_x, icon_y, icon_size, icon_size))
                            pygame.draw.rect(screen, (200, 200, 220), (icon_x, icon_y, icon_size, icon_size), 1)
                    else:
                        pygame.draw.rect(screen, color, (icon_x, icon_y, icon_size, icon_size))
                        pygame.draw.rect(screen, (200, 200, 220), (icon_x, icon_y, icon_size, icon_size), 1)
                else:
                    # Fallback colored square
                    icon_size = 28
                    icon_x = cell_x + (CELL_W - icon_size) // 2
                    icon_y = cell_y + 10
                    pygame.draw.rect(screen, color, (icon_x, icon_y, icon_size, icon_size))
                    pygame.draw.rect(screen, (200, 200, 220), (icon_x, icon_y, icon_size, icon_size), 1)

                # Item name (truncated)
                name = slot.item_id.replace("_", " ")
                if len(name) > 10:
                    name = name[:9] + "…"
                name_surf = self.font.render(name, True, (200, 200, 210))
                screen.blit(name_surf, (cell_x + 2, cell_y + 40))

                # Quantity
                qty_surf = self.font.render(str(slot.quantity), True, (255, 255, 150))
                screen.blit(qty_surf, (cell_x + CELL_W - qty_surf.get_width() - 2, cell_y + 2))
            else:
                # Empty slot hint
                empty_surf = self.font.render("—", True, (60, 60, 80))
                empty_rect = empty_surf.get_rect(center=(cell_x + CELL_W // 2, cell_y + CELL_H // 2 + 4))
                screen.blit(empty_surf, empty_rect)

    def render(self, screen: pygame.Surface | None = None) -> None:
        """
        Render the hunger and HP bars.

        Args:
            screen: Optional surface to render on (defaults to self.screen).
        """
        if screen is None:
            screen = self.screen

        if self.screen is None:
            return

        if self.survival is None:
            return

        # Calculate positions. The left column stacks downward with a
        # running cursor so no two elements share the same rows.
        x = self.MARGIN_X
        y = self.MARGIN_Y

        # Translucent backing panel sized to the column's elements, so the
        # HUD reads as one unit against the bright terrain behind it.
        panel_h = 0
        if self._seasonal_hud is not None and self._season_system is not None:
            panel_h += 62
        panel_h += (self.BAR_HEIGHT + self.BAR_SPACING) * 2  # hunger + HP
        if self.faction_system is not None:
            panel_h += self.BAR_HEIGHT + self.BAR_SPACING
        _panel_action_sys = self.get_action_system()
        if _panel_action_sys is not None and hasattr(_panel_action_sys, "stamina"):
            panel_h += self.BAR_HEIGHT + self.BAR_SPACING
        if self._active_action_progress > 0 and self._active_action_skill:
            panel_h += 10 + 12 + self.font.get_height()
        panel_w = self.BAR_WIDTH
        overlay = pygame.Surface((panel_w + 12, panel_h + 12), pygame.SRCALPHA)
        pygame.draw.rect(overlay, self.PANEL_COLOR, overlay.get_rect(), border_radius=6)
        pygame.draw.rect(overlay, self.PANEL_BORDER_COLOR, overlay.get_rect(), 1, border_radius=6)
        screen.blit(overlay, (x - 6, y - 6))

        # ── Seasonal HUD (season bar + weather icon + forecast) ─────
        if self._seasonal_hud is not None and self._season_system is not None:
            self._seasonal_hud.render_season_bar(
                screen,
                self._season_system.current_season,
                self._season_system.season_progress,
                x, y,
            )
            weather = self._weather_system.current_weather if self._weather_system else "clear"
            self._seasonal_hud.render_weather_icon(
                screen,
                weather,
                x, y + 22,
            )
            forecast = (
                self._weather_system.get_forecast(3) if self._weather_system else []
            )
            self._seasonal_hud.render_forecast_tooltip(
                screen,
                forecast,
                x, y + 42,
            )
            y += 62

        # Hunger bar
        hunger_color = self._get_hunger_color(self.survival.get_hunger_percent())
        hunger_label = f"Hunger {int(self.survival.hunger):.0f}"
        self._draw_bar(
            screen, x, y,
            self.BAR_WIDTH, self.BAR_HEIGHT,
            self.survival.get_hunger_percent(),
            hunger_color,
            hunger_label,
        )

        # HP bar (below hunger, with spacing)
        hp_y = y + self.BAR_HEIGHT + self.BAR_SPACING
        hp_color = self._get_hp_color(self.survival.get_hp_percent())
        hp_label = f"HP {int(self.survival.hp):.0f}"
        self._draw_bar(
            screen, x, hp_y,
            self.BAR_WIDTH, self.BAR_HEIGHT,
            self.survival.get_hp_percent(),
            hp_color,
            hp_label,
        )

        # ── Gold counter (top-right) ────────────────────────────────
        if self.inventory is not None:
            gold_text = f"🪙 {self.inventory.gold}"
            gold_surf = self.font_bold.render(gold_text, True, (255, 215, 0))
            gold_x = screen.get_width() - gold_surf.get_width() - 10
            gold_y = 24
            screen.blit(gold_surf, (gold_x, gold_y))

        # ── Faction status bar (below HP bar) ───────────────────────
        faction_y = hp_y + self.BAR_HEIGHT + self.BAR_SPACING
        if self.faction_system is not None:
            best_status, faction_name, standing = self.faction_system.get_best_faction_status()
            faction_color = self.faction_system.get_faction_color(best_status)

            # Background, fill, border
            pygame.draw.rect(screen, self.BG_COLOR, (self.MARGIN_X, faction_y, self.BAR_WIDTH, self.BAR_HEIGHT), border_radius=3)
            fill_w = int(self.BAR_WIDTH * standing)
            if fill_w > 0:
                pygame.draw.rect(screen, faction_color, (self.MARGIN_X, faction_y, fill_w, self.BAR_HEIGHT), border_radius=3)
                hi = tuple(min(255, c + 40) for c in faction_color)
                pygame.draw.rect(screen, hi, (self.MARGIN_X, faction_y, fill_w, max(2, self.BAR_HEIGHT // 4)), border_radius=3)
            pygame.draw.rect(screen, self.BORDER_COLOR, (self.MARGIN_X, faction_y, self.BAR_WIDTH, self.BAR_HEIGHT), 1, border_radius=3)

            # Label centred inside the bar (with drop shadow)
            faction_label = f"{faction_name} ({best_status})"
            faction_label_surf = self.font.render(faction_label, True, (255, 255, 255))
            lx = self.MARGIN_X + (self.BAR_WIDTH - faction_label_surf.get_width()) // 2
            ly = faction_y + (self.BAR_HEIGHT - faction_label_surf.get_height()) // 2
            shadow = self.font.render(faction_label, True, (0, 0, 0))
            screen.blit(shadow, (lx + 1, ly + 1))
            screen.blit(faction_label_surf, (lx, ly))

        # ── Stamina bar (below faction bar, when action system active) ─
        action_sys = self.get_action_system()
        if action_sys is not None and hasattr(action_sys, "stamina"):
            self._draw_stamina_bar(screen, x, faction_y + self.BAR_HEIGHT + self.BAR_SPACING, action_sys)

        # ── Contextual XP display (action progress bar) ────────────
        if self._active_action_progress > 0 and self._active_action_skill:
            bar_x = x
            bar_y = faction_y + (self.BAR_HEIGHT + self.BAR_SPACING) * (
                2 if (action_sys is not None and hasattr(action_sys, "stamina")) else 1
            )
            bar_w = self.BAR_WIDTH
            bar_h = 10
            # Background
            pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
            # Fill
            fill_w = int(bar_w * self._active_action_progress)
            if fill_w > 0:
                pygame.draw.rect(screen, (100, 180, 255), (bar_x, bar_y, fill_w, bar_h))
            # Border
            pygame.draw.rect(screen, self.BORDER_COLOR, (bar_x, bar_y, bar_w, bar_h), 1)
            # Label
            label = f"{self._active_action_skill}"
            label_surf = self.font.render(label, True, (200, 200, 220))
            screen.blit(label_surf, (bar_x, bar_y + 12))

        # ── Notifications (level-ups, action results) ─────────────
        notif_top = faction_y + self.BAR_HEIGHT + self.BAR_SPACING
        if action_sys is not None and hasattr(action_sys, "stamina"):
            notif_top += self.BAR_HEIGHT + self.BAR_SPACING
        if self._active_action_progress > 0 and self._active_action_skill:
            notif_top += 10 + 12 + self.font.get_height()
        notif_y = notif_top + 10
        for notif in self._notifications:
            color = notif.color
            alpha = self._get_notification_alpha(notif)
            text_surf = self.font_bold.render(notif.text, True, color)
            if alpha < 1.0:
                text_surf.set_alpha(int(alpha * 255))
            screen.blit(text_surf, (x, notif_y))
            notif_y += 20

        # ── NPC alert icon (top-right corner, blinking) ─────────────
        if self.npc_system is not None and self.player is not None:
            is_nearby = self.npc_system.is_any_npc_nearby(
                self.player.world_x, self.player.world_y,
            )
            if is_nearby and (self._npc_alert_timer % 0.2) < 0.1:
                bell_surf = self.font.render("🔔", True, (255, 215, 0))
                bell_x = screen.get_width() - bell_surf.get_width() - 10
                bell_y = 10
                screen.blit(bell_surf, (bell_x, bell_y))

        # ── Hotbar (bottom-center) ─────────────────────────────────
        if self.inventory is not None:
            self._render_hotbar(screen)

        # ── Hotbar tooltip (near cursor when hovering) ──────────────
        if (
            self.inventory is not None
            and self._hotbar_hover >= 0
            and self._hotbar_hover < len(self._hotbar_item_ids)
        ):
            item_id = self._hotbar_item_ids[self._hotbar_hover]
            if item_id is not None:
                name = item_id.replace("_", " ")
                if len(name) > 20:
                    name = name[:19] + "…"
                tooltip_surf = self.font_bold.render(name, True, (255, 255, 200))
                tooltip_x = self._hotbar_mouse_x + 8
                tooltip_y = self._hotbar_mouse_y - tooltip_surf.get_height() - 4
                # Clamp to screen bounds
                tooltip_x = max(0, min(screen.get_width() - tooltip_surf.get_width(), tooltip_x))
                tooltip_y = max(0, min(screen.get_height() - tooltip_surf.get_height(), tooltip_y))
                # Background
                bg_rect = pygame.Rect(tooltip_x - 3, tooltip_y - 2, tooltip_surf.get_width() + 6, tooltip_surf.get_height() + 4)
                pygame.draw.rect(screen, (50, 50, 60), bg_rect)
                pygame.draw.rect(screen, (120, 120, 140), bg_rect, 1)
                screen.blit(tooltip_surf, (tooltip_x, tooltip_y))

        # ── Combat Damage Flash Overlay ────────────────────────────
        if self._damage_flash > 0:
            # Semi-transparent red overlay
            flash_surf = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            alpha = int(60 * self._damage_flash)
            flash_surf.fill((255, 0, 0, alpha))
            screen.blit(flash_surf, (0, 0))
