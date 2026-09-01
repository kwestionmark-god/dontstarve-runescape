"""Shared pytest configuration and fixtures."""

import pytest
import pygame


@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    """Initialize pygame once for the entire test session."""
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()