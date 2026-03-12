import os
import sys
import threading
import msvcrt
import time
import math
import urllib.request

# --- Dependency Checks ---
def check_dependencies():
    missing = []
    try:
        import cv2
    except ImportError: missing.append("opencv-python")
    try:
        import mediapipe
    except ImportError: missing.append("mediapipe")
    try:
        # Check for cflib which is a dependency of litewing
        import cflib
    except ImportError: missing.append("cflib (Crazyflie library)")
    
    if missing:
        print("\n" + "!"*60)
        print(" ERROR: MISSING DEPENDENCIES")
        print(" " + ", ".join(missing))
        print("\n TO FIX THIS:")
        print(" 1. Ensure you have Git installed (https://git-scm.com/)")
        print(" 2. Run 'start_control.bat'")
        print("    OR manually run: pip install -r requirements.txt")
        print("!"*60 + "\n")
        # Wait for user to read before closing if run via double-click
        print("Press any key to exit...")
        msvcrt.getch()
        sys.exit(1)

# Run dependency check BEFORE importing litewing or mediapipe tasks
check_dependencies()

# --- Now safe to import internal and external dependencies ---
try:
    from litewing import LiteWing
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except ImportError as e:
    print(f"Unexpected error during import: {e}")
    sys.exit(1)

# --- Configuration ---
DEBUG_MODE = 1   # Set to 1 to test without flying, 0 for normal flight
CAMERA_INDEX = 0 # 0 = Internal, 1 or 2 = External/Virtual Camera
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_FILENAME = "hand_landmarker.task"
DRONE_IP = "192.168.43.42" # Default IP
DEFAULT_SENSITIVITY = 0.3
DEFAULT_HEIGHT = 0.3 # 30cm hover height

def ensure_model():
    """Ensures the hand_landmarker model is present."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, MODEL_FILENAME)
    
    if not os.path.exists(model_path):
        print(f"Model '{MODEL_FILENAME}' not found. Downloading...")
        try:
            urllib.request.urlretrieve(MODEL_URL, model_path)
            print("Download complete.")
        except Exception as e:
            print(f"Error downloading model: {e}")
            sys.exit(1)

class GestureRecognizer:
    def __init__(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, MODEL_FILENAME)
        
        # Configure the HandLandmarker with higher confidence thresholds
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

    def get_gesture(self, frame):
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        detection_result = self.detector.detect(mp_image)
        
        result = {"detected": False, "gesture": "UNKNOWN", "landmarks": None, "x": 0.5, "y": 0.5}

        if detection_result.hand_landmarks:
            landmarks = detection_result.hand_landmarks[0]
            result.update({
                "detected": True,
                "landmarks": landmarks,
                "gesture": self._classify_gesture(landmarks),
                "x": landmarks[9].x,
                "y": landmarks[9].y
            })
            self._draw_landmarks(frame, landmarks, (0, 255, 0))

        return result, frame

    def _classify_gesture(self, landmarks):
        # A more robust check: a finger is "UP" if the tip is higher than the MCP (knuckle)
        # We use relative Y coordinates (lower Y means higher in the image)
        
        def is_finger_up(tip_idx, mcp_idx):
            # Tip (e.g. 8) should be significantly "higher" (smaller Y) than MCP (e.g. 5)
            # We add a small buffer to prevent flickering when the hand is flat
            return landmarks[tip_idx].y < landmarks[mcp_idx].y - 0.02

        index_up = is_finger_up(8, 5)
        middle_up = is_finger_up(12, 9)
        ring_up = is_finger_up(16, 13)
        pinky_up = is_finger_up(20, 17)
        
        # Extended Palm: All fingers up
        if index_up and middle_up and ring_up and pinky_up:
            return "OPEN_PALM"
        
        # Closed Fist: All fingers down
        if not index_up and not middle_up and not ring_up and not pinky_up:
            # Additional check: thumb tip should also be close to other fingers or folded
            return "CLOSED_FIST"
            
        return "UNKNOWN"

    def _draw_landmarks(self, frame, landmarks, color):
        h, w, _ = frame.shape
        for lm in landmarks:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 3, color, -1)
        
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20)
        ]
        for start_idx, end_idx in connections:
            p1 = (int(landmarks[start_idx].x * w), int(landmarks[start_idx].y * h))
            p2 = (int(landmarks[end_idx].x * w), int(landmarks[end_idx].y * h))
            cv2.line(frame, p1, p2, color, 1)

def draw_control_hints(frame, deadzone):
    """Draws low-transparency directional arrows and text cues."""
    h, w, _ = frame.shape
    cx, cy = int(w * 0.5), int(h * 0.5)
    dw, dh = int(w * deadzone), int(h * deadzone)
    
    overlay = frame.copy()
    color = (0, 0, 225) # black
    alpha = 0.8 # transparency

    # Arrows (Line with arrowhead)
    arrow_len = 40
    # Forward (Up)
    cv2.arrowedLine(overlay, (cx, cy - dh - 10), (cx, cy - dh - 10 - arrow_len), color, 2, tipLength=0.3)
    cv2.putText(overlay, "FORWARD", (cx - 35, cy - dh - 10 - arrow_len - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # Backward (Down)
    cv2.arrowedLine(overlay, (cx, cy + dh + 10), (cx, cy + dh + 10 + arrow_len), color, 2, tipLength=0.3)
    cv2.putText(overlay, "BACKWARD", (cx - 40, cy + dh + 10 + arrow_len + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # Left (Actually Right in mirrored view, but we are flipping frame so Left is Left)
    cv2.arrowedLine(overlay, (cx - dw - 10, cy), (cx - dw - 10 - arrow_len, cy), color, 2, tipLength=0.3)
    cv2.putText(overlay, "LEFT", (cx - dw - 10 - arrow_len - 40, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # Right
    cv2.arrowedLine(overlay, (cx + dw + 10, cy), (cx + dw + 10 + arrow_len, cy), color, 2, tipLength=0.3)
    cv2.putText(overlay, "RIGHT", (cx + dw + 10 + arrow_len + 5, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # Apply transparency
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

def main():
    ensure_model()
    drone = LiteWing(DRONE_IP)
    drone.debug_mode = bool(DEBUG_MODE)
    drone.sensitivity = DEFAULT_SENSITIVITY
    drone.target_height = DEFAULT_HEIGHT
    
    try:
        drone.connect()
        # Ensure drone is in landed state on startup
        drone.land()
        time.sleep(1)  # Allow time for landing command to register
    except Exception as e:
        print(f"Drone Connection Status: {e}")

    recognizer = GestureRecognizer()
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print(f"Error: Could not open camera with index {CAMERA_INDEX}.")
        print("Try changing CAMERA_INDEX at the top of the script (0, 1, or 2).")
        return

    print("LiteWing Gesture Control Ready!")
    if drone.debug_mode:
        print("--- DEBUG MODE ACTIVE (Motors Disabled) ---")
    print("Gestures: Closed Fist = Takeoff/Arm | Open Palm = Land | Position = WASD")
    print("Drone is LANDED - Make Closed Fist gesture to take off")
    
    last_time = time.time()
    last_status_time = time.time()
    no_hand_since = None
    last_valid_result = None
    
    # Gesture debouncing
    gesture_counts = {"CLOSED_FIST": 0, "OPEN_PALM": 0}
    DEBOUNCE_THRESHOLD = 5 # Frames required to trigger takeoff/land
    
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'q' or key == b' ': break

        ret, frame = cap.read()
        if not ret: break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        dt = time.time() - last_time
        last_time = time.time()

        result, frame = recognizer.get_gesture(frame)
        deadzone = 0.1
        # Draw control zone
        cv2.rectangle(frame, (int(w*(0.5-deadzone)), int(h*(0.5-deadzone))), 
                      (int(w*(0.5+deadzone)), int(h*(0.5+deadzone))), (225, 0, 0), 1)
        # Draw center point
        cv2.circle(frame, (int(w*0.5), int(h*0.5)), 2, (0, 0, 255), -1)

        # Hysteresis smoothing: Ignore detection loss for up to 0.2s to prevent flickering
        is_hand_stable = False
        if result["detected"]:
            last_valid_result = result
            no_hand_since = None
            is_hand_stable = True
        elif last_valid_result and no_hand_since is not None:
            if time.time() - no_hand_since < 0.2:
                result = last_valid_result
                is_hand_stable = True

        if is_hand_stable:
            # Highlight tracking point
            lm_ctrl = result["landmarks"][9]
            cv2.circle(frame, (int(lm_ctrl.x * w), int(lm_ctrl.y * h)), 6, (255, 0, 255), 2)
            
            gesture = result["gesture"]
            
            # Update debounce counters
            for g in gesture_counts:
                if gesture == g:
                    gesture_counts[g] += 1
                else:
                    gesture_counts[g] = 0

            # Only takeoff if drone is landed and gesture is SUSTAINED
            if gesture_counts["CLOSED_FIST"] >= DEBOUNCE_THRESHOLD and drone.flight_phase in ["CONNECTED", "IDLE"]:
                print("Confirmed Gesture: Closed Fist - Taking off!")
                gesture_counts["CLOSED_FIST"] = 0 # Reset
                threading.Thread(target=lambda: (drone.arm(), drone.takeoff()), daemon=True).start()
            
            elif gesture_counts["OPEN_PALM"] >= DEBOUNCE_THRESHOLD and drone.flight_phase == "HOVERING":
                print("Confirmed Gesture: Open Palm - Landing!")
                gesture_counts["OPEN_PALM"] = 0 # Reset
                threading.Thread(target=drone.land, daemon=True).start()

            dx, dy = result["x"] - 0.5, result["y"] - 0.5
            vx = -drone.sensitivity if dx > deadzone else (drone.sensitivity if dx < -deadzone else 0)
            vy = drone.sensitivity if dy < -deadzone else (-drone.sensitivity if dy > deadzone else 0)

            # Determine movement labels for display
            active_labels = []
            if vx > 0: active_labels.append("LEFT")
            elif vx < 0: active_labels.append("RIGHT")
            if vy > 0: active_labels.append("FORWARD")
            elif vy < 0: active_labels.append("BACKWARD")
            movement_status = " | ".join(active_labels) if active_labels else "HOVERING"

            if drone.flight_phase == "HOVERING" and not drone.debug_mode:
                drone._position_hold.target_x += vx * dt
                drone._position_hold.target_y += vy * dt

                # Target clamping (prevents runaway target position)
                max_err = drone.max_position_error
                p_err_x = drone._position_hold.target_x - drone._position_engine.x
                p_err_y = drone._position_hold.target_y - drone._position_engine.y
                if abs(p_err_x) > max_err:
                    drone._position_hold.target_x = drone._position_engine.x + (max_err if p_err_x > 0 else -max_err)
                if abs(p_err_y) > max_err:
                    drone._position_hold.target_y = drone._position_engine.y + (max_err if p_err_y > 0 else -max_err)

                mvx, mvy = drone._position_hold.calculate_corrections(
                    drone._position_engine.x, drone._position_engine.y,
                    drone._position_engine.vx, drone._position_engine.vy,
                    drone._sensors.height, True, dt=dt
                )
                drone._cf_instance.commander.send_hover_setpoint(drone.trim_forward + mvy + vy, 
                                                               drone.trim_right + mvx + vx, 0, drone.target_height)

            # Status logic for video overlay
            status_display = drone.flight_phase
            if status_display in ["CONNECTED", "IDLE"]:
                status_display = "LANDED"
            elif status_display == "HOVERING":
                status_display = movement_status

            if drone.debug_mode:
                status_display = f"[DEBUG] {status_display}"
            
            cv2.putText(frame, f"STATUS: {status_display}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            #cv2.putText(frame, f"Y-Pos: {result['y']:.2f} | dy: {dy:.2f} | VY: {vy:.1f}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        else:
            # Landing logic when no hand is detected
            if drone.flight_phase == "HOVERING" and not drone.debug_mode:
                if no_hand_since is None:
                    no_hand_since = time.time()
                
                elapsed = time.time() - no_hand_since
                if elapsed > 0.8:
                    print("No hand detected for 0.8s - Auto-Landing!")
                    threading.Thread(target=drone.land, daemon=True).start()
                    no_hand_since = time.time() # Reset to avoid repeated calls
                
                # Keep holding position while waiting
                mvx, mvy = drone._position_hold.calculate_corrections(
                    drone._position_engine.x, drone._position_engine.y,
                    drone._position_engine.vx, drone._position_engine.vy,
                    drone._sensors.height, True, dt=dt
                )
                drone._cf_instance.commander.send_hover_setpoint(drone.trim_forward + mvy, drone.trim_right + mvx, 0, drone.target_height)
            
            # Show LANDED instead of IDLE/CONNECTED when no hand
            idle_status = "LANDED" if drone.flight_phase in ["CONNECTED", "IDLE"] else drone.flight_phase
            if drone.debug_mode:
                idle_status = f"[DEBUG] {idle_status}"
            cv2.putText(frame, f"STATUS: {idle_status} (NO HAND)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Draw transparent control hints
        draw_control_hints(frame, deadzone)

        # Display control instructions on video (Removed exit instructions)
        #cv2.putText(frame, "FIST=Takeoff | PALM=Land | POSITION=Move", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(frame, f"Bat: {drone.battery:.1f}V | Alt: {drone.height:.2f}m", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # Print status to terminal every second
        if time.time() - last_status_time >= 1.0:
            pos_x, pos_y = drone.position
            print(f"[STATUS] Phase: {drone.flight_phase} | Bat: {drone.battery:.2f}V | Height: {drone.height:.2f}m | Pos: ({pos_x:.2f}, {pos_y:.2f})")
            last_status_time = time.time()

        cv2.imshow('LiteWing Control', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord(' '): break
 
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
