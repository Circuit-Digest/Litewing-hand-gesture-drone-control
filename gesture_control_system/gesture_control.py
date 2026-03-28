# Required Libraries:
#   opencv-python >= 4.8.0   (pip install opencv-python)
#   mediapipe     >= 0.10.0  (pip install mediapipe)
#   cflib         >= 0.1.25  (pip install cflib)
#   litewing      >= 1.0.0   (pip install litewing)

import os, threading, msvcrt, time, urllib.request
from litewing import LiteWing
from litewing.manual_control import run_manual_control
import cv2, mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Configuration Constants
DEBUG_MODE = 0  # Set to 1 to enable debug mode (motors disabled for testing)
CAMERA_INDEX = 1  # Camera device index (0=default, 1=secondary, etc.)
DRONE_IP = "192.168.43.42"  # IP address of the LiteWing drone
DEFAULT_SENSITIVITY = 0.3  # Gesture sensitivity scale (0.0-1.0)
DEFAULT_HEIGHT = 0.3  # Default hovering height in meters
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_FILENAME = "hand_landmarker.task"

def ensure_model():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILENAME)
    if not os.path.exists(path):
        print(f"Model '{MODEL_FILENAME}' not found. Downloading...")
        try: urllib.request.urlretrieve(MODEL_URL, path); print("Download complete.")
        except Exception as e: print(f"Error downloading model: {e}"); raise SystemExit(1)

class GestureRecognizer:
    def __init__(self):
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILENAME)
        opts = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE, num_hands=1,
            min_hand_detection_confidence=0.7, min_hand_presence_confidence=0.7, min_tracking_confidence=0.7)
        self.detector = vision.HandLandmarker.create_from_options(opts)

    def get_gesture(self, frame):
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        det = self.detector.detect(mp_img)
        result = {"detected": False, "gesture": "UNKNOWN", "landmarks": None, "x": 0.5, "y": 0.5}
        if det.hand_landmarks:
            lm = det.hand_landmarks[0]
            result.update({"detected": True, "landmarks": lm, "gesture": self._classify(lm), "x": lm[9].x, "y": lm[9].y})
            self._draw(frame, lm)
        return result, frame

    def _classify(self, lm):
        def up(tip, mcp): return lm[tip].y < lm[mcp].y - 0.02
        fingers = [up(8,5), up(12,9), up(16,13), up(20,17)]
        if all(fingers): return "OPEN_PALM"
        if not any(fingers): return "CLOSED_FIST"
        return "UNKNOWN"

    def _draw(self, frame, lm):
        h, w = frame.shape[:2]
        pts = [(int(l.x*w), int(l.y*h)) for l in lm]
        for p in pts: cv2.circle(frame, p, 3, (0,255,0), -1)
        for s,e in [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(0,9),(9,10),(10,11),(11,12),(0,13),(13,14),(14,15),(15,16),(0,17),(17,18),(18,19),(19,20)]:
            cv2.line(frame, pts[s], pts[e], (0,255,0), 1)

def draw_control_hints(frame, dz):
    h, w = frame.shape[:2]
    cx, cy = w//2, h//2
    dw, dh = int(w*dz), int(h*dz)
    ov = frame.copy()
    c, al = (0,0,225), 0.8
    for (p1,p2,lbl,lx,ly) in [
        ((cx,cy-dh-10),(cx,cy-dh-50),"FORWARD",cx-35,cy-dh-55),
        ((cx,cy+dh+10),(cx,cy+dh+50),"BACKWARD",cx-40,cy+dh+65),
        ((cx-dw-10,cy),(cx-dw-50,cy),"LEFT",cx-dw-90,cy+5),
        ((cx+dw+10,cy),(cx+dw+50,cy),"RIGHT",cx+dw+55,cy+5)]:
        cv2.arrowedLine(ov, p1, p2, c, 2, tipLength=0.3)
        cv2.putText(ov, lbl, (lx,ly), cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1)
    cv2.addWeighted(ov, al, frame, 1-al, 0, frame)

def main():
    ensure_model()
    drone = LiteWing(DRONE_IP)
    drone.debug_mode = bool(DEBUG_MODE)
    drone.sensitivity = DEFAULT_SENSITIVITY
    drone.target_height = DEFAULT_HEIGHT
    drone.default_landing_duration = 0.1

    try:
        drone.connect(); drone.land(0.0, 0.1); time.sleep(1)
    except Exception as e:
        print(f"Drone Connection Status: {e}")

    recognizer = GestureRecognizer()
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"Error: Could not open camera with index {CAMERA_INDEX}.\nTry changing CAMERA_INDEX (0, 1, or 2)."); return

    print("LiteWing Gesture Control Ready!")
    if drone.debug_mode: print("--- DEBUG MODE ACTIVE (Motors Disabled) ---")
    print("Gestures: Closed Fist = Takeoff | Open Palm = Land | Position = WASD\nDrone is LANDED - Make Closed Fist gesture to take off")

    # --- Our own status state machine (independent of drone.flight_phase) ---
    # States: LANDED -> TAKING_OFF -> HOVERING -> MOVING -> LANDING -> LANDED
    ui_status = "LANDED"
    takeoff_start_time = None
    flight_thread = None  # Guard: only one flight thread at a time

    def _flight_loop():
        nonlocal ui_status
        drone._manual_active = True
        try: run_manual_control(drone)
        except Exception as e: print(f"[Gesture Control] Flight Error: {e}")
        finally:
            drone._manual_active = False
            ui_status = "LANDED"

    last_status_time = time.time()
    no_hand_since = last_valid_result = None
    gcounts = {"CLOSED_FIST": 0, "OPEN_PALM": 0}
    DEBOUNCE = 5
    dz = 0.1

    while True:
        if msvcrt.kbhit() and msvcrt.getch() in (b'q', b' '): break
        ret, frame = cap.read()
        if not ret: break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        result, frame = recognizer.get_gesture(frame)
        cv2.rectangle(frame, (int(w*(0.5-dz)),int(h*(0.5-dz))), (int(w*(0.5+dz)),int(h*(0.5+dz))), (225,0,0), 1)
        cv2.circle(frame, (w//2, h//2), 2, (0,0,255), -1)

        stable = False
        if result["detected"]:
            last_valid_result = result; no_hand_since = None; stable = True
        elif last_valid_result and no_hand_since and time.time()-no_hand_since < 0.2:
            result = last_valid_result; stable = True

        # --- Advance TAKING_OFF -> HOVERING once target height is reached ---
        if ui_status == "TAKING_OFF" and drone.height >= drone.target_height * 0.85:
            ui_status = "HOVERING"

        if stable:
            cv2.circle(frame, (int(result["landmarks"][9].x*w), int(result["landmarks"][9].y*h)), 6, (255,0,255), 2)
            gesture = result["gesture"]
            for g in gcounts: gcounts[g] = gcounts[g]+1 if gesture==g else 0

            # Takeoff: only if landed AND no flight thread is alive
            if gcounts["CLOSED_FIST"] >= DEBOUNCE and ui_status == "LANDED" and (flight_thread is None or not flight_thread.is_alive()):
                print("[Gesture Control] Closed Fist - Taking off!")
                gcounts["CLOSED_FIST"] = 0
                ui_status = "TAKING_OFF"
                takeoff_start_time = time.time()
                flight_thread = threading.Thread(target=_flight_loop, daemon=True)
                flight_thread.start()

            elif gcounts["OPEN_PALM"] >= DEBOUNCE and ui_status not in ("LANDED", "LANDING"):
                print("[Gesture Control] Open Palm - Landing!")
                gcounts["OPEN_PALM"] = 0
                ui_status = "LANDING"
                drone._manual_active = False

            # WASD mapping — only when airborne
            for k in 'wasd': drone._manual_keys[k] = False
            if ui_status not in ("LANDED", "LANDING", "TAKING_OFF"):
                dx, dy = result["x"]-0.5, result["y"]-0.5
                if dy < -dz: drone._manual_keys['w'] = True
                elif dy > dz: drone._manual_keys['s'] = True
                if dx < -dz: drone._manual_keys['a'] = True
                elif dx > dz: drone._manual_keys['d'] = True
                fwd  = drone._manual_keys['w']
                back = drone._manual_keys['s']
                left = drone._manual_keys['a']
                rght = drone._manual_keys['d']
                if fwd or back or left or rght:
                    fb = "FORWARD" if fwd else ("BACKWARD" if back else "")
                    lr = "LEFT"    if left else ("RIGHT"    if rght else "")
                    ui_status = " + ".join(filter(None, [fb, lr]))
                else:
                    ui_status = "HOVERING"

            display = ui_status
        else:
            # No hand detected
            if no_hand_since is None and ui_status not in ("LANDED", "LANDING"):
                no_hand_since = time.time()
            if no_hand_since and time.time()-no_hand_since > 1.0 and ui_status not in ("LANDED","LANDING") and not drone.debug_mode:
                print("[Gesture Control] No hand detected for 1.0s - Auto-Landing!")
                ui_status = "LANDING"
                drone._manual_active = False
                no_hand_since = time.time()
            for k in 'wasd': drone._manual_keys[k] = False
            display = f"{ui_status} (NO HAND)"

        if drone.debug_mode: display = f"[DEBUG] {display}"
        txt_color = (0,0,255) if not stable else (0,0,0)
        cv2.putText(frame, f"STATUS: {display}", (20,40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, txt_color, 2)

        draw_control_hints(frame, dz)
        cv2.putText(frame, f"Bat: {drone.battery:.1f}V | Alt: {drone.height:.2f}m", (20,65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)

        if time.time()-last_status_time >= 1.0:
            print(f"[STATUS] {ui_status} | Bat: {drone.battery:.2f}V | Height: {drone.height:.2f}m")
            last_status_time = time.time()

        cv2.imshow('LiteWing Control', frame)
        if cv2.waitKey(1) & 0xFF in (ord('q'), ord(' ')): break

    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()