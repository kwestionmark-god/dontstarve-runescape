"""world/erosion_ti.py — Taichi port of the hydraulic erosion pass.

The Python implementation in world_gen._simulate_erosion is strictly
Gauss-Seidel ordered (x-major scan with in-place neighbor updates), which
blocks numpy vectorization. This module runs the same update order inside
Taichi kernels (serialized flow loop, elementwise rain/evaporation), which is
bit-exact because all arithmetic stays float64 in the same op order.

Falls back to the pure-Python loop when Taichi is unavailable.

NOTE: this module must NOT use `from __future__ import annotations` — Taichi
parses kernel parameter annotations at decoration time, and stringified
annotations fail.
"""

import numpy as np

_TI_READY: "bool | None" = None
_KERNELS: tuple | None = None


def taichi_erosion_available() -> bool:
    """True when Taichi imported and initialized (CPU arch) without error."""
    global _TI_READY, _KERNELS
    if _TI_READY is not None:
        return _TI_READY
    try:
        import taichi as ti

        # advanced_optimization=False: keep LLVM from fusing mul+add into FMA,
        # which changes float64 rounding vs the (unfused) Python reference ops.
        ti.init(arch=ti.cpu, default_fp=ti.f64, random_seed=0,
                offline_cache=False, log_level=ti.ERROR, advanced_optimization=False)
        _KERNELS = _build_kernels()
        _TI_READY = True
    except Exception:
        _TI_READY = False
    return _TI_READY


def _build_kernels():
    import taichi as ti

    @ti.kernel
    def _rain(water: ti.types.ndarray(), rain: ti.f64, w: ti.i32, h: ti.i32):
        for i, j in ti.ndrange(w, h):
            water[i, j] += rain

    # Neighbor directions in the exact order of the Python loop — flow
    # subtraction accumulates per tile in this order.
    DIRS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))

    @ti.kernel
    def _flow(elev: ti.types.ndarray(),
              water: ti.types.ndarray(),
              sediment: ti.types.ndarray(),
              w: ti.i32, h: ti.i32,
              sed_cap_factor: ti.f64, gravity: ti.f64, solubility: ti.f64):
        # Serialized x-major scan: the algorithm's in-place updates make each
        # tile's result depend on earlier tiles in this same pass.
        ti.loop_config(serialize=True)
        for i in range(w):
            ti.loop_config(serialize=True)
            for j in range(h):
                w_xy = water[i, j]
                if w_xy > 0:
                    current_height = elev[i, j]
                    # Gather downhill neighbor slopes (contribution order
                    # significant for float rounding).
                    slopes_n = 0
                    sx = ti.Vector.zero(ti.i32, 8)
                    sy = ti.Vector.zero(ti.i32, 8)
                    ss = ti.Vector.zero(ti.f64, 8)
                    total_slope = 0.0
                    for k in ti.static(range(8)):
                        dx = DIRS[k][0]
                        dy = DIRS[k][1]
                        nx = i + dx
                        ny = j + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            slope = current_height - elev[nx, ny]
                            if slope > 0:
                                dist = 1.414
                                if dx == 0 or dy == 0:
                                    dist = 1.0
                                slope = slope / dist
                                sx[slopes_n] = nx
                                sy[slopes_n] = ny
                                ss[slopes_n] = slope
                                slopes_n += 1
                                total_slope += slope
                    if total_slope > 0:
                        for t in range(slopes_n):
                            nx = sx[t]
                            ny = sy[t]
                            slope = ss[t]
                            flow = w_xy * (slope / total_slope)
                            sediment_capacity = flow * slope * sed_cap_factor * gravity
                            if sediment[i, j] > sediment_capacity:
                                deposit = ti.min(sediment[i, j] - sediment_capacity, sediment[i, j])
                                elev[i, j] += deposit
                                sediment[i, j] -= deposit
                            elif sediment[i, j] < sediment_capacity:
                                erode = ti.min(sediment_capacity - sediment[i, j], current_height * solubility)
                                elev[i, j] -= erode
                                sediment[i, j] += erode
                            water[nx, ny] += flow
                            w_xy -= flow
                        water[i, j] = w_xy

    @ti.kernel
    def _evaporate(elev: ti.types.ndarray(),
                   water: ti.types.ndarray(),
                   sediment: ti.types.ndarray(),
                   w: ti.i32, h: ti.i32, evap_keep: ti.f64):
        for i, j in ti.ndrange(w, h):
            w_xy = water[i, j] * evap_keep
            if w_xy < 0.001:
                water[i, j] = 0.0
                if sediment[i, j] > 0:
                    elev[i, j] += sediment[i, j]
                    sediment[i, j] = 0.0
            else:
                water[i, j] = w_xy

    return _rain, _flow, _evaporate


def simulate_erosion_ti(elev_arr: np.ndarray, iterations: int, rain: float,
                        evaporation: float, gravity: float, sed_cap_factor: float,
                        solubility: float) -> np.ndarray:
    """Run the erosion simulation via Taichi kernels.

    Args:
        elev_arr: (w, h) float64 elevations (modified in place semantics —
            a working copy is returned).
    Returns:
        The eroded float64 elevation array.
    """
    if not taichi_erosion_available():
        raise RuntimeError("Taichi not available")
    _rain, _flow, _evaporate = _KERNELS
    w, h = elev_arr.shape
    elev = elev_arr.astype(np.float64, copy=False)
    if not elev.flags["C_CONTIGUOUS"]:
        elev = np.ascontiguousarray(elev)
    water = np.zeros((w, h), dtype=np.float64)
    sediment = np.zeros((w, h), dtype=np.float64)
    evap_keep = 1.0 - evaporation
    for _ in range(iterations):
        _rain(water, rain, w, h)
        _flow(elev, water, sediment, w, h, sed_cap_factor, gravity, solubility)
        _evaporate(elev, water, sediment, w, h, evap_keep)
    return elev
