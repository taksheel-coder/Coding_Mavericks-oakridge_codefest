import speech_recognition as sr
from groq import Groq
import json
import threading
import queue
import time
import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import cv2
import mediapipe as mp
import math
# Firebase setup
cred = credentials.Certificate('/Users/taksheelsubudhi/Downloads/Dementia Assistant Firebase Service Account.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://dementia-assistant-90aef-default-rtdb.asia-southeast1.firebasedatabase.app/'
})
database = db.reference('person_data')

client = Groq(api_key="")
recognizer = sr.Recognizer()

person_stuff = {
    "name": "none",
    "hobby": "none",
    "age": "none",
    "workplace": "none"
}
conversation_history = []
audio_queue = queue.Queue()
running = True
# consent
consent_given = False
pending_data = []  # Store all updates until consent is given
# speech to text settings
recognizer.energy_threshold = 100
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.pause_threshold = 0.5
recognizer.phrase_threshold = 0.1
recognizer.non_speaking_duration = 0.3
# Start face mesh and UI tools
meshface = mp.solutions.face_mesh
mp_ui = mp.solutions.drawing_utils
# Variables for storage logic
saved_face_ratios = None
start_time = time.time()
status_message = "analyzing face..."
current_color = (0, 255, 0)  # green
def distance(p1, p2):
    # calculate the 3d distance
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
def always_listening():
    global running

    with sr.Microphone(sample_rate=48000) as source:
        print("callibrating")

        recognizer.adjust_for_ambient_noise(source, duration=2)

        print("calibrating done")

        while running:
            try:
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
                audio_queue.put(audio)
            except Exception as e:
                if running:
                    print(f"try again: {e}")
                time.sleep(0.1)


def speech_to_text(audio):
    with open("temp_audio.wav", "wb") as f:
        f.write(audio.get_wav_data())

    with open("temp_audio.wav", "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=("audio.wav", audio_file.read()),
            model="whisper-large-v3",
            language="en",
            response_format="json",
            temperature=0.0
        )

    if os.path.exists("temp_audio.wav"):
        os.remove("temp_audio.wav")

    return transcription.text if transcription.text else None


def check_for_consent(text):
    """
    Check if the person has given consent to save their data.
    Looks for phrases like "yes", "okay", "sure", "consent", etc.
    """
    global consent_given, pending_data
    text_lower = text.lower()
    # Consent keywords
    consent_phrases = [
        "yes you can save",
        "yes save",
        "you can save",
        "okay save",
        "sure save",
        "i consent",
        "i give consent",
        "save my data",
        "save my information",
        "go ahead",
        "that's fine",
        "okay",
        "yes",
        "sure",
        "yep",
        "yeah",
        "consent given"
    ]
    # Check if any consent phrase is in the text
    for phrase in consent_phrases:
        if phrase in text_lower:
            if not consent_given:
                consent_given = True
                print("\n" + "=" * 50)
                print("we accept your concent, sending your data")
                print("=" * 50 + "\n")
                # remainding data will go into firebass as well
                if pending_data:
                    for data in pending_data:
                        database.push(data)
                    print(f"✓ Saved {len(pending_data)} data entries to Firebase")
                    pending_data.clear()
                return True
    return False
def convo_info(new_text):
    global conversation_history, person_stuff
    conversation_history.append(new_text)
    full_conversation = "\n".join([f"- {text}" for text in conversation_history])
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """You are an intelligent information extractor. 
Your job is to extract person information from conversations.

Rules:
1. Look at the ENTIRE conversation history, not just the latest message
2. Accumulate information across all messages
3. If someone mentions their name in message 1 and their hobby in message 3, capture BOTH
4. Keep track of everything mentioned throughout the conversation
5. If information was mentioned before, keep it (don't replace with "none")
6. Only update a field if new information is explicitly stated
7. Be smart about context - "I work there" after mentioning "Google" means workplace is Google

Return ONLY valid JSON with these fields: name, hobby, age, workplace
If a field hasn't been mentioned anywhere in the conversation, use "none"."""
            },
            {
                "role": "user",
                "content": f"""Current known information:
{json.dumps(person_stuff, indent=2)}

Full conversation history:
{full_conversation}

Extract and update information based on the ENTIRE conversation above.
Remember: Keep previously mentioned information, only add/update with new info."""
            }
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    info = json.loads(response.choices[0].message.content)
    return info
def change_person_info(new_info):
    global person_stuff, consent_given, pending_data
    if new_info is None:
        return False
    updated = False
    changes = []
    for key in ["name", "hobby", "age", "workplace"]:
        if new_info.get(key) and new_info[key] != "none":
            if person_stuff[key] != new_info[key]:
                old_value = person_stuff[key]
                person_stuff[key] = new_info[key]
                updated = True
                changes.append(f"{key.capitalize()}: '{old_value}' > '{new_info[key]}'")
    if changes:
        for change in changes:
            print(change)
        # Create data snapshot
        data_snapshot = {
            'name': person_stuff['name'],
            'hobby': person_stuff['hobby'],
            'age': person_stuff['age'],
            'workplace': person_stuff['workplace'],
            'timestamp': time.time()
        }
        # only store in firebase
        if consent_given:
            database.push(data_snapshot)
            print("✓ Data saved to Firebase (consent already given)")
        else:
            pending_data.append(data_snapshot)
            print("⏳ Data stored locally (waiting for consent)")
            print("   Say 'yes you can save' to save to database")
    return updated
def print_info():
    print("all info:")
    for key, value in person_stuff.items():
        print(f"  {key.capitalize()}: {value}")
def audio_processing_thread():
    global running, person_stuff, conversation_history
    time.sleep(2.5)
    print("speak now")
    print("why arent you speaking")

    detection_count = 0

    while running:
        try:
            audio = audio_queue.get(timeout=0.5)
            detection_count += 1

            text = speech_to_text(audio)

            if text:
                print(f"you: \"{text}\"")

                # Check for consent first
                check_for_consent(text)

                # Continue processing conversation
                new_info = convo_info(text)

                if new_info:
                    print(json.dumps(new_info, indent=2))

                    updated = change_person_info(new_info)

                    if updated:
                        print_info()

        except queue.Empty:
            continue
    for key, value in person_stuff.items():
        print(f"  {key.capitalize()}: {value}")
def main():
    global running, saved_face_ratios, start_time, status_message, current_color, consent_given

    # Start listening thread
    listener_thread = threading.Thread(target=always_listening, daemon=True)
    listener_thread.start()

    # Start audio processing thread
    audio_thread = threading.Thread(target=audio_processing_thread, daemon=True)
    audio_thread.start()
    webcam = cv2.VideoCapture(0)
    with meshface.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.5) as face_mesh:
        while webcam.isOpened():
            works, frame = webcam.read()
            if not works:
                continue
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

                    # drawing
                    if consent_given:
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
                    # Draw person info popup next to face
                    h, w, _ = frame.shape
                    nose_x = int(face_landmarks.landmark[1].x * w)
                    nose_y = int(face_landmarks.landmark[1].y * h)

                    box_x = nose_x + 50
                    box_y = nose_y - 100

                    # info box
                    overlay = frame.copy()
                    box_width = 250
                    box_height = 150  # Increased height for consent status
                    cv2.rectangle(overlay, (box_x, box_y), (box_x + box_width, box_y + box_height),
                                  (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                    # Draw person information
                    y_offset = box_y + 25
                    cv2.putText(frame, f"Name: {person_stuff['name']}", (box_x + 10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset += 25
                    cv2.putText(frame, f"Age: {person_stuff['age']}", (box_x + 10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset += 25
                    cv2.putText(frame, f"Hobby: {person_stuff['hobby']}", (box_x + 10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset += 25
                    cv2.putText(frame, f"Work: {person_stuff['workplace']}", (box_x + 10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                    # concent status
                    y_offset += 30
                    if consent_given:
                        cv2.putText(frame, "Status: SAVED", (box_x + 10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    else:
                        cv2.putText(frame, "Status: Awaiting Consent", (box_x + 10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(frame, status_message, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            # consent display
            if not consent_given:
                cv2.putText(frame, "give your consent option", (20, frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow('dot person', frame)
            if cv2.waitKey(5) & 0xFF == ord('q'):
                running = False
                break
    webcam.release()
    cv2.destroyAllWindows()
if __name__ == "__main__":
    main()
