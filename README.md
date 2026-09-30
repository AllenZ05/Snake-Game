# Snake

A desktop Snake game built with Python and Pygame, preserving the original bright-green checkerboard and blue snake artwork with subtle interface improvements.

https://github.com/user-attachments/assets/ace73ade-3ee0-4d42-868a-ffef13b5f889

## Features

- **Smooth movement:** 60 FPS rendering, curved turns, and a two-turn input buffer.
- **72 ways to play:** three board sizes (12×12, 16×16, 20×20), three speeds, 1/3/5/7 apples, and solid or wraparound walls. Each combination keeps its own record.
- **Original artwork at its original size:** the original blue snake and 40-unit cells keep their on-screen size. The window fits the selected map.
- **Crisp Retina rendering:** text and controls render at the display's full pixel density. Sprite pixels are replicated without blur filters, and pause/results panels preserve the surrounding board's colors.
- **Subtle UI polish:** consistently sized buttons, hover/pressed/focus feedback, a start hint, and pause/results panels over the board.
- **Bite feedback:** crunch audio timed to the visible apple pickup, with optional small particles. Choose Reduced effects to turn the particles off.
- **Comfort controls:** keyboard-accessible menus, Off/Quiet/On sound, a mute shortcut, and automatic pause when the window loses focus.
- **Saved preferences and records:** settings persist between sessions, and new records save during play. Invalid save data or unavailable audio won't stop the game.

## Run locally

Tested with Python 3.11 and Pygame 2.6.1.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python snake.py
```

On Windows, activate the environment with `.venv\Scripts\activate`.

If this checkout already has its virtual environment, run:

```bash
.venv/bin/python snake.py
```

## Controls

| Where | Control | Action |
| --- | --- | --- |
| Menu | Click | Select options or play |
| Menu | Tab / Shift+Tab, or Up / Down | Move between settings |
| Menu | Left / Right | Change the focused setting |
| Menu | Enter | Start a round |
| Ready / playing | WASD or arrow keys | Start moving / steer; reversing into yourself is blocked |
| Playing / paused | Space or P | Pause / resume |
| Results | Space | Play again |
| Pause / results | Tab or arrow keys, then Enter | Choose a button |
| Any screen | M | Mute / restore sound |
| In a round | Esc | Return to the menu |

The game stays paused after you return from another window. Resume when you're ready.

## Project structure

- `snake.py` — movement, collision and scoring rules, input, sound, and persistence.
- `ui.py` — controls and text at the display's pixel density, the original board colors, and pause/results panels.
- `display.py` — SDL2 window creation and presentation at full Retina resolution.
- `Graphics/`, `Sound/` — original artwork and crunch sound.
- `tests/test_snake.py` — headless gameplay, persistence, input, and rendering regressions.

`high_scores.json` and `settings.json` are local runtime files, excluded from Git. Existing per-mode high-score keys remain compatible. Saves replace files atomically; if saving fails, the interface shows a message and keeps the values in memory.

## Checks

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The suite uses SDL's dummy video and audio drivers, so it doesn't open a window or play sound. It covers all 72 modes, full-board wins, startup continuity, bite timing, turns and wrapping, record persistence, focus-loss pause, keyboard controls, mouse controls, original sprite preservation, 2× text rendering, and unchanged sprite colors under pause/results panels. Physical Retina output also needs a native-window check; the dummy driver cannot verify it.
