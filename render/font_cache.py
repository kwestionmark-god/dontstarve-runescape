"""
font_cache.py — Module-level font cache for pygame fonts.

Provides a single shared cache for pygame.font.SysFont instances to avoid
repeatedly creating the same fonts across the codebase.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygame.font import Font


# Cache keyed by (name, size, bold, italic)
_cache: dict[tuple[str, int, bool, bool], Font] = {}


def get_font(name: str, size: int, bold: bool = False, italic: bool = False) -> Font:
    """
    Get a cached pygame font instance.

    Args:
        name: Font family name (e.g., "monospace").
        size: Font size in points.
        bold: Whether the font should be bold.
        italic: Whether the font should be italic.

    Returns:
        A cached pygame.font.Font instance.
    """
    key = (name, size, bold, italic)
    font = _cache.get(key)
    if font is None:
        font = pygame.font.SysFont(name, size, bold=bold, italic=italic)
        _cache[key] = font
    return font


def clear_cache() -> None:
    """Clear the font cache (useful for testing or shutdown)."""
    _cache.clear()


# Convenience functions for common font configurations
def get_monospace(size: int, bold: bool = False, italic: bool = False) -> Font:
    """Get a monospace font at the given size."""
    return get_font("monospace", size, bold=bold, italic=italic)


def get_monospace_bold(size: int) -> Font:
    """Get a bold monospace font at the given size."""
    return get_font("monospace", size, bold=True)


def get_monospace_italic(size: int) -> Font:
    """Get an italic monospace font at the given size."""
    return get_font("monospace", size, italic=True)