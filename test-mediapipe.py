import cv2
import mediapipe as mp
import time
import math

# Start face mesh and UI tools
meshface = mp.solutions.face_mesh
mp_ui = mp.solutions.drawing_utils

# Variables for storage logic
saved_face_ratios = None
start_time = time.time()
status_message = "analyzing face..."
current_color = (0, 255, 0)  # green


def distance(p1, p2):
      #calculate the 3d distance
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)


def get_face_fingerprint(landmarks):
    """
    3 identifire distanceL
    1. Eye distance to Nose length
    2. Mouth width to Face width
    3. Eye distance to Mouth width
    """
    d_eyes = distance(landmarks[33], landmarks[263])  # Eye corners
    d_nose = distance(landmarks[1], landmarks[152])  # Nose to Chin
    d_mouth = distance(landmarks[61], landmarks[291])  # Mouth corners
    d_face = distance(landmarks[234], landmarks[454])  # Face width

    # Ratios - avoiding by 0
    return [
        d_eyes / (d_nose + 0.001),
        d_mouth / (d_face + 0.001),
        d_eyes / (d_mouth + 0.001)
    ]


webcam = cv2.VideoCapture(0)
with meshface.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.75,
        min_tracking_confidence=0.5) as face_mesh:
    while webcam.isOpened():
        works, frame = webcam.read()
        if not works: continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        elapsed = time.time() - start_time

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                current_fingerprint = get_face_fingerprint(face_landmarks.landmark)
                if saved_face_ratios is None:
                    if elapsed < 5:
                        status_message = f"recording in {int(5 - elapsed)}s..."
                        current_color = (0, 255, 255)  # Yellow while waiting
                    else:
                        saved_face_ratios = current_fingerprint
                        status_message = "face has been recorded"

                # compare
                else:
                    # average of the distances
                    diffs = [abs(c - s) for c, s in zip(current_fingerprint, saved_face_ratios)]
                    avg_diff = sum(diffs) / len(diffs)

                    # smaller - more strict for the
                    if avg_diff < 0.05:
                        status_message = "recognized person"
                        current_color = (0, 255, 0)  # Green
                    else:
                        status_message = "new person"
                        current_color = (0, 0, 255)  # Red

                # 4. drawing
                mp_ui.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=None,
                    landmark_drawing_spec=mp_ui.DrawingSpec(
                        color=current_color,
                        thickness=1,
                        circle_radius=1
                    )
                )
        cv2.putText(frame, status_message, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow('dot person', frame)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

webcam.release()
cv2.destroyAllWindows()
