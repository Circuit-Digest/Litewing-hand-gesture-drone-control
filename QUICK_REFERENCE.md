# LiteWing Gesture Control: Quick Reference

A quick lookup for gestures, controls, and system behavior.

---

## ✊ Hand Gestures (Core Commands)

| Gesture | Action | Usage Item |
|---|---|---|
| **Closed Fist** | **Takeoff / Arm** | Hold for ~5 frames to start motors and lift to 0.3m. |
| **Open Palm** | **Land** | Hold for ~5 frames to initiate a gentle descent and stop. |
| **Any Hand** | **Movement** | Movement is active only when a hand is detected in "HOVERING" phase. |

---

## 🎮 Directional Control (WASD Logic)

The drone follows your hand's position relative to the **Camera Center**.

| Hand Position | Drone Movement | On-Screen Label |
|---|---|---|
| **Higher than Center** | Pitch Forward | `FORWARD` |
| **Lower than Center** | Pitch Backward | `BACKWARD` |
| **Left of Center** | Roll Left | `LEFT` |
| **Right of Center** | Roll Right | `RIGHT` |

- **Deadzone**: Small movements near the center (10% of frame) are ignored to prevent drift.
- **Sensitivity**: Controlled by `DEFAULT_SENSITIVITY` (default `0.3`).

---

## 📊 Visual HUD (Heads-Up Display)

Information displayed on the real-time video feed:

| Element | Description |
|---|---|
| **STATUS** | Current flight phase (`LANDED`, `FORWARD`, `HOVERING`, etc.) |
| **Bat** | Battery Voltage (3.0V = Empty, 4.2V = Full) |
| **Alt** | Altitude in meters (from ground sensors) |
| **Pink Circle** | Tracking point on your hand (MCP Joint of Middle Finger) |
| **Blue Box** | The "Deadzone" boundary — keep hand here to hover in place |

---

## 🛡️ Safety & Fail-safes

| Feature | Behavior |
|---|---|
| **Auto-Landing** | If no hand is detected for **>0.8 seconds**, the drone lands automatically. |
| **Debouncing** | Gestures must be held for 5 frames to trigger to avoid "glitch" commands. |
| **Hysteresis** | Tracking persists for 0.2s after temporary loss to smooth flight. |
| **DEBUG_MODE** | Set `DEBUG_MODE = 1` to test gestures on-screen without spinning the motors. |

---

## ⚙️ Key Technical Settings

Found at the top of `gesture_control_system/gesture_control.py`:

| Constant | Default | Purpose |
|---|---|---|
| `DEBUG_MODE` | `1` | Test without flying (1=On, 0=Off). |
| `CAMERA_INDEX` | `0` | Change if using an external webcam (0, 1, or 2). |
| `DRONE_IP` | `192.168.43.42` | The IP of your LiteWing drone. |
| `DEFAULT_SENSITIVITY` | `0.3` | Speed of movement scaling. |
| `DEFAULT_HEIGHT` | `0.3` | Target hover altitude in meters. |

---

## 🚀 Speed Run (How to Start)

1. **Connect** to the LiteWing Drone Wi-Fi.
2. **Run** the control script:
   ```bash
   python gesture_control_system/gesture_control.py
   ```
3. **Stand** back, show a **Closed Fist** to take off.
4. **Navigate** with your hand.
5. **Show Palm** or press `SPACE` to land.
