# 🧟 Surviving Zombie — 3D Top-Down Action Shooter

> **A wave-based zombie survival game built entirely with legacy OpenGL (PyOpenGL) and GLUT — no game engine required.**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![OpenGL](https://img.shields.io/badge/OpenGL-Legacy-green?logo=opengl)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Playable-brightgreen)

---

## 📖 Overview

**Surviving Zombie** is a 3D top-down action shooter where you fight through three increasingly difficult waves of zombies. Built from scratch using **PyOpenGL** and **GLUT**, the game features fully procedural 3D models (no external assets), multiple camera modes, a weapon upgrade system, placeable auto-turret cannons, and a between-wave item shop — all in a single Python file.

---

## 🎮 Gameplay

### Waves

| Wave | Enemies | Description |
|------|---------|-------------|
| **Wave 1** | 8 Regular Zombies | Slow green-ish zombies — ease into the fight |
| **Wave 2** | 6 Regular + 6 Mutant Zombies | Faster purple mutants join the horde |
| **Wave 3** | 9 Mutants + 1 Boss | A massive red boss with 25 HP and minion escorts |

Between waves, a **Shop** phase lets you spend earned cash on upgrades before the next onslaught.

### Weapons

| Weapon | Unlock | Fire Rate | Behavior |
|--------|--------|-----------|----------|
| 🔫 **Pistol** | Default | Slow (0.35s) | Single accurate shot |
| 🔫 **Machine Gun** | Shop ($80) | Rapid (0.08s) | Fast single-bullet stream |
| 🔫 **Shotgun** | Shop ($120) | Slow (0.45s) | 3-bullet spread per shot |

### Cannons (Placeable Turrets)

Buy cannons from the shop ($100 each), then press **F** during gameplay to place one at your current position. Cannons **auto-target** the nearest enemy, rotate to aim, and fire explosive rounds with **area-of-effect splash damage**.

### Economy

- Killing zombies drops spinning **golden cash cubes** on the ground
- Walk over them to collect (auto-collect in cheat mode)
- Cash drops expire after **5 seconds** — stay alert!
- Spend cash in the shop on weapons, HP upgrades, and cannons

---

## 🕹️ Controls

### Movement & Combat

| Key | Action |
|-----|--------|
| `W` `A` `S` `D` | Move player (camera-relative) |
| **Mouse Move** | Aim — player faces the cursor |
| **Left Click** | Shoot toward cursor |
| `Q` / `E` | Cycle weapons backward / forward |
| `F` | Place a cannon at current position |

### Camera

| Key | Action |
|-----|--------|
| **Right Click** | Toggle 3rd-person ↔ 1st-person camera |
| `T` | Toggle top-down (bird's-eye) view |
| **Arrow Keys ←→** | Orbit camera left / right |
| **Arrow Keys ↑↓** | Raise / lower camera angle |
| **Scroll Wheel** | Zoom in / out |

### Game

| Key | Action |
|-----|--------|
| `R` | Restart the game |
| `Space` | Advance from wave-clear screen → shop → next wave |
| `1` `2` `3` `4` | Buy items in Shop |
| `C` | Toggle cheat mode (auto-aim turret) |
| `V` | Toggle cheat vision (1st-person follows turret) |

---

## 🏗️ Architecture

The entire game is contained in a single file — [`SurvivingZombie.py`](SurvivingZombie.py) (~1,536 lines) — structured into clear sections:

```
SurvivingZombie.py
├── Constants & Global State       # Window, grid, player, camera, economy
├── 3D Math Helpers                # Ray-casting (mouse → world coords)
├── Enemy System                   # Zombie types, spawning, wave management
├── Drawing Functions              # Procedural 3D models for all entities
│   ├── Grid & Boundaries
│   ├── Player (humanoid model with weapon visuals)
│   ├── Zombies (regular, mutant, boss with HP bar)
│   ├── Bullets, Cash Drops, Cannons, Splash FX
│   ├── Crosshair (2D screen-space & 3D first-person)
│   ├── HP Bar (screen-space overlay)
│   └── Shop UI (full-screen 2D overlay)
├── Weapon & Firing System         # Rate limiting, spread, weapon switching
├── Input Callbacks                # Keyboard, mouse, special keys
├── Camera System                  # 3rd-person orbit, 1st-person, top-down
├── Game Loop (idle)               # Physics, AI, collision, wave logic
├── Display (showScreen)           # Render pipeline orchestration
└── Entry Point (main)             # GLUT initialization & main loop
```

### Key Technical Highlights

- **Mouse Ray-Casting**: Custom implementation that projects the mouse position through the camera frustum and intersects with the Z=0 ground plane for accurate aiming across all camera modes.
- **Procedural 3D Models**: Every entity (player, zombies, weapons, cannons) is built from OpenGL primitives — spheres, cylinders, and cubes — with no external model files.
- **Camera System**: Three fully functional camera modes with smooth transitions:
  - **3rd-Person Orbit**: Orbitable camera with adjustable height and zoom
  - **1st-Person**: Warp-based mouse look with center-locked cursor
  - **Top-Down**: Bird's-eye view with rotatable orientation
- **Cannon AI**: Autonomous turrets with target acquisition, smooth rotation, rate-limited firing, and area-of-effect splash damage with visual ring effects.
- **60 FPS Frame Limiter**: Time-delta gated game loop ensuring consistent gameplay speed.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **PyOpenGL** with GLUT support

### Installation

```bash
# Clone the repository
git clone https://github.com/pota2dev/ZombieSurvival3D.git
cd ZombieSurvival3D

# Install the dependency
pip install PyOpenGL PyOpenGL_accelerate

# On Linux, you may also need freeglut:
# sudo apt install freeglut3-dev
```

### Run

```bash
python SurvivingZombie.py
```

The game window (1000×800) will open immediately — **Wave 1 starts automatically**.

---

## 📸 Game Features at a Glance

- 🧟 **3 enemy types** — Regular, Mutant, and Boss zombies with distinct visuals and stats
- 🔫 **3 weapons** — Pistol, Machine Gun, and Shotgun with unique fire patterns
- 🏪 **Between-wave shop** — Spend earned cash on upgrades and equipment
- 🗼 **Placeable auto-turrets** — Cannons with AOE splash damage
- 🎥 **3 camera modes** — Third-person orbit, first-person, and top-down
- 💰 **Cash economy** — Kill zombies → collect drops → buy upgrades
- 🎯 **Precision aiming** — Ray-cast mouse targeting across all camera modes
- 💀 **Boss fights** — Wave 3 boss with 25 HP and overhead health bar
- 🤖 **Cheat mode** — Auto-aim turret with optional cheat-vision camera

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
