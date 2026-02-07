import cv2
import mediapipe as mp

# intializing mp
mp_face_detection = mp.solutions.face_detection
mp_points = mp.solutions.drawing_utils

webcam = cv2.VideoCapture(0)

# selecting model
with mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5) as face_detection:
    while webcam.isOpened():
        works, frame = webcam.read()
        if not works:
            print("none is there")
            continue

        # convert bgr to rgb
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detection.process(rgb)

        #face ui
        if results.detections:
            for detection in results.detections:
                mp_points.draw_detection(frame, detection)

        cv2.imshow('MediaPipe Face Tracking', frame)

        # Fail safe
        if cv2.waitKey(5) & 0xFF == ord('q'):
            print("break")
            break

webcam.release()
cv2.destroyAllWindows()
