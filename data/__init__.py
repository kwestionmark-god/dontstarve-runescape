"""
data/__init__.py — JSON data loader.

Provides a simple loader utility for reading game data from JSON files.
All data files live in the `data/` directory and are loaded via load_json().
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent


def load_json(filename: str) -> dict:
    """
    Load and return the JSON data from a file in the data/ directory.

    Args:
        filename: Relative path within data/ (e.g. "biomes.json").

    Returns:
        Parsed dict from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    filepath = DATA_DIR / filename
    with open(filepath, "r") as f:
        return json.load(f)


def load_json_list(filename: str, key: str = "") -> list:
    """
    Load a JSON file and return the list stored under a specific key,
    or the top-level list if key is empty.

    Args:
        filename: Relative path within data/.
        key: If the JSON is a dict, load this key's value (which should be a list).

    Returns:
        The list from the JSON file.
    """
    data = load_json(filename)
    if key:
        return data.get(key, [])
    return data if isinstance(data, list) else []
