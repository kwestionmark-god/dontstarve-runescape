"""actions.notifications — ActionNotification dataclass for brief player notifications."""

from dataclasses import dataclass


@dataclass
class ActionNotification:
    """
    A brief notification shown to the player.

    Used for level-ups, action results, spoilage warnings, etc.
    """
    text: str
    color: tuple[int, int, int] = (255, 255, 255)
    duration: float = 2.0
    elapsed: float = 0.0

    @property
    def is_expired(self) -> bool:
        return self.elapsed >= self.duration
