# LiteWing Gesture Control 

**Hand Gesture Control for LiteWing Drones.**

This project leverages the LiteWing library to enable real-time hand gesture recognition for drone flight. Using MediaPipe and OpenCV, you can fly the LiteWing drone autonomously without a keyboard or controller.

## Key Upgrade: Gesture Control System

The `gesture_control_system` folder contains the heart of this upgrade. It allows for:
- **Autonomous Takeoff**: Give a **Closed Fist** to arm and take off.
- **Autonomous Landing**: Show an **Open Palm** to land safely.
- **Dynamic Movement**: The drone follows your hand position in the camera frame (Forward/Backward/Left/Right).

---

## Key Features

- **Powered Recognition**: Uses MediaPipe Hand Landmarker for high-speed, 21-point hand tracking.
- **Natural Gestures**:
    - **Closed Fist**: Arm and Take off.
    - **Open Palm**: Gentle Landing.
- **Precision Tracking**: Proportional movement control based on hand position relative to the camera center.
- **Safety First**:
    - **Auto-Landing**: Drone automatically lands if hand detection is lost for >0.8 seconds.
    - **Hysteresis Smoothing**: Prevents erratic behavior during temporary detection flickers.
    - **Deadzone Control**: Logic to prevent unintended movement when the hand is near the center frame.
- **Rich Visual HUD**: Real-time video overlay showing flight status, battery voltage, height, and directional hints.
- **Highly Configurable**: Easily tune sensitivity, height, and camera settings via code constants.

## How it Works

The system processes video frames in real-time to identify hand landmarks. It calculates the displacement of your hand's center (MCP of the middle finger) from the camera center to generate movement commands.

- **Vertical Displacement (Y)**: Maps to Forward/Backward movement.
- **Horizontal Displacement (X)**: Maps to Left/Right movement.
- **Gesture State Machine**: Monitors the count of specific gestures over consecutive frames to prevent "false positives" (debouncing).

---

## Installation & Setup

### 1. Library Installation
First, install the core LiteWing library from GitHub:
```bash
pip install git+https://github.com/Circuit-Digest/LiteWing-Library.git
```

### 2. Gesture Control Dependencies
The gesture system requires additional libraries (versions used in this project):
- **Python**: `3.11.9` (Recommended), `>= 3.8` (Required)
- **OpenCV**: `4.13.0.92`
- **MediaPipe**: `0.10.32`
- **Matplotlib**: `3.10.8`
- **cflib**: Latest from GitHub (included in requirements)

```bash
pip install -r gesture_control_system/requirements.txt
```

---

##  Usage in Code

The project uses the `LiteWing` class to interface with the drone. Here is the basic structure:

```python
from litewing import LiteWing

# Initialize drone
drone = LiteWing(DRONE_IP)

# Command example
drone.forward(velocity=0.2)
drone.land()
```

The `gesture_control_system/gesture_control.py` script manages the mapping between vision-detected gestures and these library commands.

---

## How to Run

### Gesture Control
Run the main gesture control script:
```bash
python gesture_control_system/gesture_control.py
```

### Configuration
You can adjust parameters at the top of `gesture_control.py`:
- `DEBUG_MODE`: Set to `1` to test gestures on-screen without spinning the motors.
- `CAMERA_INDEX`: Change if you use an external webcam (0, 1, or 2).
- `DEFAULT_SENSITIVITY`: Adjust how responsive the drone is to hand movements.
- `DEFAULT_HEIGHT`: Set the hover height (default is 0.3m).

---

## Checklist & Works to Run

Ensure all these items are checked before flight:

- [ ] **Drone IP**: Set correctly in `gesture_control.py` (Default: `192.168.43.42`).
- [ ] **Battery**: Check if LiteWing is sufficiently charged (> 3.2V).
- [ ] **Lighting**: Ensure the room is well-lit for MediaPipe to detect hand landmarks.
- [ ] **Model File**: The script will automatically download `hand_landmarker.task` on first run. Ensure you have an internet connection for this.
- [ ] **Safety**: If you are a new user, start with `DEBUG_MODE = 1` to get used to the gestures.

---

## Project Structure

```
hand-gesture-drone-control/
├── gesture_control_system/   <-- Gesture Control Project
│   ├── gesture_control.py    # Main gesture control logic
│   ├── requirements.txt      # Project-specific requirements
│   └── hand_landmarker.task  # MediaPipe model (auto-downloaded)
├── .gitignore                # Git ignore rules
├── LICENSE                   # MIT License
├── QUICK_REFERENCE.md        # Quick guide for gestures
└── README.md                 # Main documentation
```

## Credits
This project leverages the LiteWing library to provide high-level drone control integrated with MediaPipe-based gesture recognition.

## License
MIT — see [LICENSE](LICENSE) for details.
