"""
tests/test_recruit_panel_faction_names.py — RecruitPanel resolves faction friendly-names.

`RecruitPanel._load_faction_names` must key the friendly-name map by the JSON key
`"faction_id"` (data/factions.json). A wrong key (`"id"`) leaves the map empty and
`_get_faction_name` falls back to the raw faction_id — recruits then show, e.g.,
`Faction: forest_villagers` instead of `Faction: Forest Villagers`.

This test exercises REAL behavior: it constructs a genuine `RecruitPanel`, whose
`__init__` runs `_load_faction_names()` against the real data/factions.json, then reads
the resolved name through the real `_get_faction_name`. No mocks, no stat harness, no
`IntelligenceSkill` construction.
"""
import pygame


def test_recruit_panel_loads_faction_friendly_names():
    """The friendly-name map is keyed by data/factions.json's `faction_id`."""
    pygame.init()
    from ui.recruit_panel import RecruitPanel

    panel = RecruitPanel()  # __init__ runs _load_faction_names() against real data/factions.json

    # data/factions.json uses key "faction_id": "forest_villagers" -> "Forest Villagers"
    assert panel._get_faction_name("forest_villagers") == "Forest Villagers"
    assert panel._get_faction_name("goblins") == "Goblin Tribes"
    # Unknown faction falls back to the raw id: proves the map is *read*, not hard-coded.
    assert panel._get_faction_name("no_such_faction") == "no_such_faction"


def test_recruit_and_diplomacy_panels_instantiate_and_handle_key():
    """Regression smoke: panels import + construct cleanly; unopened-session behavior unchanged."""
    pygame.init()
    from ui.recruit_panel import RecruitPanel
    from ui.diplomacy_panel import DiplomacyPanel

    recruit = RecruitPanel()
    diplomacy = DiplomacyPanel()

    # RecruitPanel has no open session -> handle_key(K_RETURN) returns None (no tuple).
    assert recruit.handle_key(pygame.K_RETURN) is None
    # DiplomacyPanel has no open session -> handle_key(K_RETURN) returns ("negotiate",).
    assert diplomacy.handle_key(pygame.K_RETURN) == ("negotiate",)
