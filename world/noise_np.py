"""world/noise_np.py — NumPy-vectorized replica of `noise.pnoise2` (octaves=1).

The `noise` C extension (`_perlin.c`) uses a STATIC 512-byte PERM table and
offsets indices by `base`. Bases used by world_gen (seed+1000, seed+2000)
index beyond PERM[512], reading bytes that follow the table in the compiled
binary's rodata — deterministic for a given installed build. To replicate
the C function exactly (required for CPU/GPU world parity), we extract the
effective extended table from the installed `.so` at runtime by locating the
known PERM signature and reading the bytes that follow it.

All arithmetic here is done in float32 in the same operation order as the C
code so results match the C extension exactly (verified by tests).
"""

from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

# C GRAD3 table from _noise.h (note: reordered vs. the classic Perlin set).
_GRAD_X = np.array([1, -1, 1, -1, 1, -1, 1, -1, 0, 0, 0, 0, 1, -1, 0, 0], dtype=np.float32)
_GRAD_Y = np.array([1, 1, -1, -1, 0, 0, 0, 0, 1, -1, 1, -1, 0, 0, -1, 1], dtype=np.float32)

# The canonical 512-byte PERM signature from _noise.h (first 32 bytes are
# enough to locate the table inside the extension module).
_PERM_HEAD = bytes([
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
])


def _perm_table_path() -> str:
    """Filesystem path of the installed _perlin extension module."""
    import importlib.util

    spec = importlib.util.find_spec("noise._perlin")
    if spec is None or spec.origin is None:
        raise RuntimeError("noise._perlin extension not found")
    return spec.origin


def _perm_region_from_memory() -> "tuple[bytes, int]":
    """Read the (possibly relocated) bytes that follow PERM in the *loaded*
    _perlin module. Large bases index past PERM's 512 entries into whatever
    the loader placed after it in memory; file bytes can disagree with memory
    past section boundaries (e.g. .data.rel.ro is copied/relocated), so we
    must read the live mapping, not the .so file."""
    import ctypes
    import noise._perlin  # ensure loaded

    path = _perm_table_path()
    base = None
    end = None
    with open("/proc/self/maps") as f:
        for line in f:
            if path in line:
                rng = line.split()[0]
                lo_s, hi_s = rng.split("-")
                lo, hi = int(lo_s, 16), int(hi_s, 16)
                if base is None:
                    base, end = lo, hi
                elif lo == end:  # contiguous mapping of the same module
                    end = hi
    if base is None:
        raise RuntimeError("could not locate _perlin module mapping")
    window = ctypes.string_at(base, end - base)
    pos = window.find(_PERM_HEAD)
    if pos < 0:
        raise RuntimeError("PERM signature not found in _perlin memory mapping")
    return window[pos:], pos


@lru_cache(maxsize=1)
def extended_perm_table(extra: int = 8192) -> np.ndarray:
    """Effective PERM table: the 512-byte table plus the bytes that follow
    it in the *loaded* extension (which C reads for large bases — an
    out-of-bounds but build-deterministic region).

    Args:
        extra: how many bytes past the 512-byte table to include. Capped by
            the module's mapped region. Indices reach up to 510 + max(base);
            our bases reach seed+5000, so any in-game seed below ~2600 is
            covered. Larger seeds take a per-call C fallback in
            pnoise2_grid instead.
    """
    region, pos = _perm_region_from_memory()
    table = region[: 512 + extra]
    return np.frombuffer(table, dtype=np.uint8).astype(np.int64)  # bytes as 0..255


def pnoise2_grid(
    xs: np.ndarray,
    ys: np.ndarray,
    repeatx: float,
    repeaty: float,
    base: int,
    perm: np.ndarray | None = None,
) -> np.ndarray:
    """Vectorized replica of `noise.pnoise2(x, y, octaves=1, repeatx=…, repeaty=…, base=…)`.

    Args:
        xs, ys: coordinate arrays (any dtype; truncated to float32 exactly as
            the C parser's 'f' format does).
        repeatx, repeaty: repeat intervals (floats in the C signature).
        base: base offset added to permutation indices.
        perm: extended permutation table (defaults to the runtime-extracted one).

    Returns:
        float32 array of noise values, bitwise-comparable to the C output.
    """
    if perm is None:
        perm = extended_perm_table()
    if base + 510 >= len(perm):
        # Base beyond the extractable window: fall back to the C extension
        # (slow but exact) rather than reading garbage.
        import noise as _noise

        flat_x = np.ravel(np.ascontiguousarray(xs, dtype=np.float64))
        flat_y = np.ravel(np.ascontiguousarray(ys, dtype=np.float64))
        out = np.array(
            [_noise.pnoise2(float(a), float(b), octaves=1, repeatx=repeatx, repeaty=repeaty, base=base)
             for a, b in zip(flat_x, flat_y)],
            dtype=np.float32,
        )
        return out.reshape(xs.shape)

    x = np.ascontiguousarray(xs, dtype=np.float32)
    y = np.ascontiguousarray(ys, dtype=np.float32)
    rx = np.float32(repeatx)
    ry = np.float32(repeaty)

    # C: i = (int)floorf(fmodf(x, repeatx)); ii = (int)fmodf(i + 1, repeatx)
    i = np.floor(np.fmod(x, rx)).astype(np.int64)
    j = np.floor(np.fmod(y, ry)).astype(np.int64)
    ii = np.fmod(i + 1, rx).astype(np.int64)
    jj = np.fmod(j + 1, ry).astype(np.int64)

    # C: (i & 255) + base — '&' on the C int (two's complement); numpy int64
    # '&' matches for the values we produce.
    i = (i & 255) + base
    j = (j & 255) + base
    ii = (ii & 255) + base
    jj = (jj & 255) + base

    xf = x - np.floor(x)
    yf = y - np.floor(y)
    fx = xf * xf * xf * (xf * (xf * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))
    fy = yf * yf * yf * (yf * (yf * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))

    A = perm[i]
    AA = perm[A + j]
    AB = perm[A + jj]
    B = perm[ii]
    BA = perm[B + j]
    BB = perm[B + jj]

    def grad(h_hash: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
        h = (h_hash & 15).astype(np.int64)
        gx = _GRAD_X[h]
        gy = _GRAD_Y[h]
        return dx * gx + dy * gy

    n00 = grad(perm[AA], xf, yf)
    n10 = grad(perm[BA], xf - np.float32(1.0), yf)
    n01 = grad(perm[AB], xf, yf - np.float32(1.0))
    n11 = grad(perm[BB], xf - np.float32(1.0), yf - np.float32(1.0))

    # lerp(t, a, b) = a + t * (b - a)
    u = n00 + fx * (n10 - n00)
    v = n01 + fx * (n11 - n01)
    return u + fy * (v - u)
