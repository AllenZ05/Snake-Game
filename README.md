# Snake Game 

Inspired by the classic Snake Game. Navigate the snake using WASD or arrow keys to consume food and grow while avoiding collisions with the walls or yourself. Enjoy the retro feel with added sound effects and smooth animations for an engaging gaming experience 

## Features

- **Smooth Snake Movement:** Fluid 60 FPS animation with responsive WASD or arrow key inputs
- **Game Options:** Pick from 3 map sizes (12x12, 16x16, 20x20), 3 speeds, and 1, 3, or 5 apples on screen at once, with a separate high score tracked for each combination
- **Collision Detection:** Game-over triggers when the snake hits a wall or its own body
- **Sound Effects:** Immersive sounds to enhance the gameplay experience
- **Score Tracking:** Dynamic game-over screen displays your score and high score after each round
- **Engaging Graphics:** Fluid animations and attractive snake graphics for a user-friendly interface

## Tech Stack and tools used 

- **Programming Language:** Python
- **Game Library:** PyGame

## Getting Started

1. **Clone** the repository
2. **Create and activate** a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
   > pygame doesn't ship wheels for Python 3.14 yet — if the install fails, create the venv with an older Python, e.g. `python3.11 -m venv .venv`
3. **Install** dependencies: `pip install -r requirements.txt`
4. **Run** the game: `python snake.py`

## Timeline

- **Main Development:** Oct 2023
- **New Features Added:** Jan 2024

## Video Demo 

https://github.com/AllenZ05/Python-Games/assets/124856383/2bca3b01-fde5-4ffe-9b3e-ca0c30c525be