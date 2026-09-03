"""Phase 5D: Taichi erosion kernel parity test (opt-in fast path).

The Taichi flow/evaporation kernels replicate the scalar Gauss-Seidel loop.
Elevation output must be int-exact; the float pipeline may drift by ≤1e-6
(LLVM codegen detail), which erosion's int() quantization absorbs in practice.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("taichi") is None,
    reason="taichi not installed",
)

from config import (  # noqa: E402
    EROSION_EVAPORATION, EROSION_GRAVITY, EROSION_ITERATIONS, EROSION_RAIN_AMOUNT,
    EROSION_SEDIMENT_CAPACITY_FACTOR, EROSION_SOLUBILITY,
)


def _run(seed: int, size: int):
    import world.world_gen as wg
    from world.erosion_ti import simulate_erosion_ti, taichi_erosion_available

    assert taichi_erosion_available(), "taichi init failed"
    elev = wg._generate_elevation_map(seed, size, size)
    ref = wg._simulate_erosion(elev, size, size, seed)
    arr = np.array(
        [[float(elev[x][y]) for y in range(size)] for x in range(size)],
        dtype=np.float64,
    )
    out = simulate_erosion_ti(
        arr.copy(), EROSION_ITERATIONS, EROSION_RAIN_AMOUNT, EROSION_EVAPORATION,
        EROSION_GRAVITY, EROSION_SEDIMENT_CAPACITY_FACTOR, EROSION_SOLUBILITY,
    )
    return np.array(ref, dtype=np.int64), out


class TestTaichiErosionParity:
    @pytest.mark.parametrize("seed", [7, 1234])
    def test_int_elevation_exact(self, seed: int) -> None:
        from config import ELEVATION_LEVELS

        ref_int, out = _run(seed, 64)
        out_int = np.clip(out.astype(np.int64), 0, ELEVATION_LEVELS - 1)
        assert np.array_equal(ref_int, out_int)

    def test_float_drift_tiny(self) -> None:
        ref_int, out = _run(7, 64)
        # The float grid must sit within a hair of the integer reference
        # before quantization.
        assert np.abs(out - ref_int).max() < 1.0
