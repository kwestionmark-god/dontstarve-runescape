"""core/spatial_grid.py — uniform 2-D spatial hash for proximity queries.

Latent-scaling fix (Phase 5B): several systems scanned full entity lists per
frame/tick (monsters × structures, monsters × fires, NPCs × HUD queries).
A uniform grid buckets live objects by world position so radius queries visit
only nearby buckets; buckets preserve insertion order, so callers that sort
results see byte-identical output to a full scan.
"""

from __future__ import annotations


class UniformGrid:
    """Bucketed 2-D index; rebuilt wholesale each tick (build is O(n))."""

    __slots__ = ("cell_size", "_buckets", "_items")

    def __init__(self, cell_size: int = 128) -> None:
        self.cell_size = cell_size
        self._buckets: dict[tuple[int, int], list[int]] = {}
        self._items: list[object] = []

    def rebuild(self, items: "list", x_of, y_of) -> None:
        """Rebuild from a list of objects with position accessors."""
        self._items = items
        buckets = self._buckets
        buckets.clear()
        cell = self.cell_size
        for i, obj in enumerate(items):
            key = (int(x_of(obj)) // cell, int(y_of(obj)) // cell)
            buckets.setdefault(key, []).append(i)

    def query_indices(self, world_x: float, world_y: float, radius: float):
        """Yield item indices whose bucket overlaps the query circle.

        Callers still verify exact distance; this never misses inside-radius
        items and may return extra ones slightly outside."""
        cell = self.cell_size
        cx0 = int(world_x - radius) // cell
        cx1 = int(world_x + radius) // cell
        cy0 = int(world_y - radius) // cell
        cy1 = int(world_y + radius) // cell
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                bucket = self._buckets.get((cx, cy))
                if bucket:
                    yield from bucket
