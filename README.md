# ProjectiFy

ProjectiFy is a Python desktop physics simulation application built with Tkinter. It combines numerical modelling, real-time animation, data visualisation, object-oriented programming and SQLite persistence.

## Features

- User registration and login
- SHA-256 password hashing
- SQLite database persistence
- Abstract Simulation base class using ABC
- Projectile motion with air resistance
- Pendulum motion with damping
- Spring-mass harmonic motion
- 1D wave simulation
- Circular motion
- Pause, resume, step and stop controls
- Matplotlib graphing
- Saved simulation results per user

## Tech stack

Python, Tkinter, SQLite3, NumPy, Matplotlib, JSON and object-oriented programming.

## Run locally

```bash
pip install -r requirements.txt
python projectify.py
```

The SQLite database is created automatically on first launch.

## Project structure

- `projectify.py` - main application
- `requirements.txt` - Python dependencies
- `.gitignore` - generated/local files excluded from version control

## Notes

This project was developed as a physics simulation application demonstrating mathematical modelling, numerical integration, OOP and data persistence.
