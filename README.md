# TubeMeasurementTimer

**Author:** Hemy Gulati  
**GitHub:** https://github.com/HemyGulati/TubeMeasurementTimer  
**Version:** 1.0.0 — 16 April 2026  
**Licence:** MIT

A desktop GUI tool for managing multiple production timers simultaneously and capturing checkpoint measurements at configurable elapsed times.

Designed for manufacturing and process-monitoring workflows where multiple parts are measured after process steps.

---

## Features

- **Unlimited named timers** — add as many timers as needed
- **Independent start / stop / reset** for each timer
- **Compact operator layout** — checkpoint editor on the left, timer rows on the right
- **Checkpoint editor** — add, edit, remove, and sort checkpoint values
- **Units support** — interpret checkpoint values as seconds, minutes, or hours
- **Checkpoint queue system** — oldest due hit is active by default
- **Manual override** — click a different due timer to enter out of order, then return to the queue
- **Priority visuals**
  - active due timer = blinking red
  - queued due timers = solid red
  - next upcoming timer = yellow
- **Inline data entry** beside each timer
- **CSV autosave after every entry** so data is preserved even if the app closes unexpectedly
- **Save / load config files**
- **Auto-load last used config on startup**
- **Choose CSV save location**
- **Dark mode / light mode** with improved panel contrast
- **Mouse wheel scrolling** in the timer area
- **Duplicate timer-name warning**
- **Fullscreen production mode**

---

## Project Structure

```text
TubeMeasurementTimer/
├── main.py
├── requirements.txt
├── build_windows.bat
├── LICENSE.txt
├── README.md
├── .gitignore
├── assets/
│   └── icon.ico
└── configs/
    └── .gitkeep
```

---

## Quick Start — Run from Source

Works best on Windows. It may also run on macOS or Linux where `tkinter` is available.

### 1 — Prerequisites

- **Python 3.10 or newer** — https://www.python.org/downloads/
  - On Windows: tick ✅ **"Add Python to PATH"** during install
  - Make sure your Python installation includes **tkinter**

### 2 — Install dependencies

```bash
pip install -r requirements.txt
```

`tkinter` is normally bundled with Python, so there are no extra runtime packages for the app itself. The requirements file mainly includes **PyInstaller** for building the Windows executable.

### 3 — Run

```bash
python main.py
```

---

## Building the Windows EXE

Double-click `build_windows.bat` or run:

```cmd
build_windows.bat
```

This will:
1. Locate Python automatically
2. Install / update build dependencies
3. Bundle the app with PyInstaller
4. Create `dist\TubeMeasurementTimer.exe`

No Python is required on the end-user machine once the EXE has been built.

### App icon

The `assets/icon.ico` file is applied to the built EXE if present.

---

## Using the App

### 1. Set checkpoint values

Use the checkpoint editor on the left to add or edit elapsed-time checkpoints.

Example:

```text
5,10,15,25,27,30,32,35,40
```

Choose whether those values represent:
- **seconds**
- **minutes**
- **hours**

### 2. Add timers

Examples:
- `R1T1`
- `R1T6`
- `R3T6`

Each timer has its own **Start**, **Stop**, and **Reset** controls.

### 3. Choose CSV save location

Pick where readings should be written. The CSV is saved after **every** submitted value.

### 4. Start timers as parts come out

Start each timer when its corresponding part is ready.

### 5. Enter readings when prompted

When a timer reaches a checkpoint, the app enables inline input beside that timer.

### Queue behaviour

When multiple checkpoint hits occur close together:
- the **oldest due hit** becomes active by default
- later due hits wait in queue order
- you can still **manually override** by clicking another due timer
- after saving a manual override entry, the app returns to the **oldest remaining queue item**

---

## CSV Output

The CSV file uses these columns:

| timer name | time | duration since start | user input value |
|-----------|------|----------------------|------------------|
| R1T1 | 12:32 | 5 | 1404 |
| R3T6 | 12:35 | 5 | 1045 |

- **timer name** — the timer label in the app
- **time** — current local time when the value was submitted
- **duration since start** — elapsed checkpoint value in the selected unit
- **user input value** — the value entered by the operator

---

## Config Files

The app can save and load configuration files.

A saved config includes:
- checkpoint values
- selected unit (seconds / minutes / hours)
- timer names
- CSV save path
- theme
- fullscreen preference

The app also auto-loads the **last successfully used config** on startup when available.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named tkinter` | Reinstall Python and ensure **tcl/tk and IDLE** are included |
| EXE build fails | Run `pip install -r requirements.txt` first |
| Icon not showing on EXE | Make sure `assets/icon.ico` exists before running the build script |
| Mouse wheel does not scroll | Click inside the timer area first, then scroll |
| CSV won’t save | Confirm the chosen folder is writable and the CSV is not locked by another program |

---

## Editing in VS Code

Open the project folder:

```bash
code .
```

Recommended extensions:
- **Python** — `ms-python.python`
- **Pylance** — `ms-python.vscode-pylance`

Select your interpreter (`Ctrl+Shift+P` → **Python: Select Interpreter**) and run `main.py`.

---

## Licence

MIT — see LICENSE.txt  
Copyright © 2026 Hemy Gulati
