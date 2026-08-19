# Don't Starve RuneScape

A Python + pygame survival game.

## Requirements

- Python 3.10+

Third-party runtime dependencies (`noise`, `pygame`):

```bash
pip install -r requirements.txt
```

`noise` is used by `world/world_gen.py` to generate terrain with simplex noise.
`pygame` is the game engine. Both are pinned to tested versions in `requirements.txt`.

## Running

```bash
python main.py --seed 42
```

## Testing

The suite runs without a display (no pygame window):

```bash
python -m pytest -q
```
