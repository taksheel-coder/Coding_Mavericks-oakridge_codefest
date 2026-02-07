#commit 2

import cv2
import mediapipe as mp

# start face mesh
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

webcam = cv2.VideoCapture(0)

with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5) as face_mesh:
    while webcam.isOpened():
        works, frame = webcam.read()
        if not works:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                #place in spot
                mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=None,  #no triangle connection
                    landmark_drawing_spec=mp_drawing.DrawingSpec(
                        color=(0, 255, 255),
                        thickness=1,
                        circle_radius=1
                    )
                )

        cv2.imshow('dot person', frame)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

webcam.release()
cv2.destroyAllWindows()
