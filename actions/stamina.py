"""actions.stamina — StaminaPool dataclass for woodcutting/mining stamina tracking."""

from __future__ import annotations

from config import MAX_STAMINA_BASE
from dataclasses import dataclass


@dataclass(slots=True)
class StaminaPool:
    """
    Tracks stamina for woodcutting/mining actions.

    Fields:
        current: Current stamina (0 = exhausted)
        max_stamina: Maximum stamina (from config)
        exhaustion_timer: Cooldown when exhausted (seconds remaining)
        is_exhausted: True when stamina is 0 and resting
    """
    current: float = MAX_STAMINA_BASE
    max_stamina: float = MAX_STAMINA_BASE
    exhaustion_timer: float = 0.0
    is_exhausted: bool = False

    def consume(self, amount: float) -> bool:
        """
        Try to consume stamina. Returns False if exhausted.

        Args:
            amount: Stamina to consume.

        Returns:
            True if stamina was consumed, False if exhausted.
        """
        if self.is_exhausted:
            return False
        if self.current <= amount:
            self.current = 0.0
            self.is_exhausted = True
            self.exhaustion_timer = 5.0  # 5s rest when exhausted
            return False
        self.current -= amount
        return True

    def tick(self, dt: float) -> None:
        """
        Update stamina pool each frame.

        Regenerates stamina when not exhausted. Rests when exhausted.

        Args:
            dt: Delta time in seconds.
        """
        if self.is_exhausted:
            self.exhaustion_timer -= dt
            if self.exhaustion_timer <= 0:
                self.is_exhausted = False
                self.current = self.max_stamina
        else:
            # Regenerate stamina slowly
            self.current = min(self.max_stamina, self.current + dt * 2.0)