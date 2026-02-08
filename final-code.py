import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
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
from dotenv import load_dotenv

load_dotenv()  # loads .env file

API_KEY = os.getenv("MY_API_KEY")

if not API_KEY:
    raise Exception("MY_API_KEY is not set")

# Firebase setup
cred = credentials.Certificate('/Users/taksheelsubudhi/Downloads/Dementia Assistant Firebase Service Account.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://dementia-assistant-90aef-default-rtdb.asia-southeast1.firebasedatabase.app/'
})
database = db.reference('person_data')
client = Groq(api_key="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")
recognizer = sr.Recognizer()
person_stuff = {
    "name": "none",
    "hobby": "none",
    "age": "none",
    "workplace": "none",
    "last_conversation_summary": "none"
}
conversation_history = []
full_conversation_text = []  # Store complete conversation for summary
audio_queue = queue.Queue()
running = False
consent_given = False
pending_data = []
current_person_key = None  # Track the database key for the current person
# speech to text settings
recognizer.energy_threshold = 100
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.pause_threshold = 0.5
recognizer.phrase_threshold = 0.1
recognizer.non_speaking_duration = 0.3
meshface = mp.solutions.face_mesh
mp_ui = mp.solutions.drawing_utils
saved_face_ratios = None
start_time = time.time()
status_message = "analyzing face..."
current_color = (0, 255, 0)


def distance(p1, p2):
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)


def get_face_fingerprint(landmarks):
    d_eyes = distance(landmarks[33], landmarks[263])
    d_nose = distance(landmarks[1], landmarks[152])
    d_mouth = distance(landmarks[61], landmarks[291])
    d_face = distance(landmarks[234], landmarks[454])
    return [
        d_eyes / (d_nose + 0.001),
        d_mouth / (d_face + 0.001),
        d_eyes / (d_mouth + 0.001)
    ]


def generate_conversation_summary():
    """Generate a 2-line summary of the conversation"""
    global full_conversation_text

    if len(full_conversation_text) < 2:
        return "none"

    try:
        conversation = "\n".join(full_conversation_text)
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a conversation summarizer. Create a brief 2-line summary of the conversation.
The summary should capture the main topics discussed and key points.
Each line should be a complete sentence.
Keep it concise and informative.
Format: Two sentences separated by a period and space."""
                },
                {
                    "role": "user",
                    "content": f"""Summarize this conversation in exactly 2 lines:

{conversation}

Return ONLY the 2-line summary, nothing else."""
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3
        )

        summary = response.choices[0].message.content.strip()
        # Ensure it's roughly 2 lines by taking first two sentences
        sentences = summary.split('. ')
        if len(sentences) >= 2:
            summary = sentences[0] + '. ' + sentences[1]
            if not summary.endswith('.'):
                summary += '.'

        print(f"\n📝 Conversation Summary Generated:\n{summary}\n")
        return summary

    except Exception as e:
        print(f"Error generating summary: {e}")
        return "none"


def find_person_in_database(name):
    """Search database for a person with matching name (case-insensitive)"""
    global current_person_key
    if name == "none" or not name:
        return None

    try:
        all_data = database.get()
        if all_data:
            name_lower = name.lower().strip()
            # Search through all entries for matching name
            for key, person_data in all_data.items():
                if person_data.get('name', '').lower().strip() == name_lower:
                    print(f"\n✓ Found existing person in database: {person_data.get('name')}")
                    current_person_key = key
                    return person_data
    except Exception as e:
        print(f"Error searching database: {e}")

    current_person_key = None
    return None


def load_person_data(person_data):
    """Load person data from database into person_stuff"""
    global person_stuff
    if person_data:
        for key in ["name", "hobby", "age", "workplace", "last_conversation_summary"]:
            if key in person_data and person_data[key] != "none":
                person_stuff[key] = person_data[key]

        print("Loaded data from database:")
        print_info()

        # Display previous conversation summary if it exists
        if person_stuff.get("last_conversation_summary") != "none":
            print("\n" + "=" * 60)
            print("📖 PREVIOUS CONVERSATION SUMMARY:")
            print(person_stuff["last_conversation_summary"])
            print("=" * 60 + "\n")
        else:
            print("(No previous conversation summary found)")


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
    global consent_given, pending_data
    text_lower = text.lower()
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
    for phrase in consent_phrases:
        if phrase in text_lower:
            if not consent_given:
                consent_given = True
                print("\n" + "=" * 50)
                print("we accept your concent, sending your data")
                print("=" * 50 + "\n")
                if pending_data:
                    for data in pending_data:
                        save_to_database(data)
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


def save_to_database(data_snapshot):
    """Save or update person data in database"""
    global current_person_key

    if current_person_key:
        # Update existing person's data
        database.child(current_person_key).update(data_snapshot)
        print(f"✓ Updated existing person data in Firebase (key: {current_person_key})")
    else:
        # Create new entry
        new_ref = database.push(data_snapshot)
        current_person_key = new_ref.key
        print(f"✓ Created new person entry in Firebase (key: {current_person_key})")


def change_person_info(new_info):
    global person_stuff, consent_given, pending_data
    if new_info is None:
        return False
    updated = False
    changes = []

    # Check if name was just discovered and search database
    if new_info.get('name') and new_info['name'] != "none" and person_stuff['name'] == "none":
        existing_person = find_person_in_database(new_info['name'])
        if existing_person:
            load_person_data(existing_person)
            # After loading, we still want to process any new info from this message

    for key in ["name", "hobby", "age", "workplace"]:
        if new_info.get(key) and new_info[key] != "none":
            if person_stuff[key] != new_info[key]:
                old_value = person_stuff[key]
                person_stuff[key] = new_info[key]
                updated = True
                changes.append(f"{key.capitalize()}: '{old_value}' → '{new_info[key]}'")

    if changes:
        for change in changes:
            print(change)
        data_snapshot = {
            'name': person_stuff['name'],
            'hobby': person_stuff['hobby'],
            'age': person_stuff['age'],
            'workplace': person_stuff['workplace'],
            'last_conversation_summary': person_stuff.get('last_conversation_summary', 'none'),
            'timestamp': time.time()
        }
        if consent_given:
            save_to_database(data_snapshot)
        else:
            pending_data.append(data_snapshot)
            print("⏳ Data stored locally (waiting for consent)")
            print("   Say 'yes you can save' to save to database")
    return updated


def save_conversation_summary():
    """Generate and save conversation summary to database"""
    global person_stuff, consent_given, full_conversation_text

    if len(full_conversation_text) < 2:
        print("Not enough conversation to summarize")
        return

    # Generate summary
    summary = generate_conversation_summary()

    if summary != "none":
        person_stuff['last_conversation_summary'] = summary

        data_snapshot = {
            'name': person_stuff['name'],
            'hobby': person_stuff['hobby'],
            'age': person_stuff['age'],
            'workplace': person_stuff['workplace'],
            'last_conversation_summary': summary,
            'timestamp': time.time()
        }

        if consent_given:
            save_to_database(data_snapshot)
            print("✓ Conversation summary saved to database")
        else:
            pending_data.append(data_snapshot)
            print("⏳ Conversation summary stored locally (waiting for consent)")


def print_info():
    print("all info:")
    for key, value in person_stuff.items():
        if key != "last_conversation_summary":
            print(f"  {key.capitalize()}: {value}")


def audio_processing_thread():
    global running, person_stuff, conversation_history, full_conversation_text
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

                # Store full conversation for summary
                full_conversation_text.append(text)

                check_for_consent(text)
                new_info = convo_info(text)
                if new_info:
                    print(json.dumps(new_info, indent=2))
                    updated = change_person_info(new_info)
                    if updated:
                        print_info()
        except queue.Empty:
            continue

    # When conversation ends, save summary
    if person_stuff['name'] != "none":
        print("\n🔄 Generating conversation summary...")
        save_conversation_summary()

    for key, value in person_stuff.items():
        if key != "last_conversation_summary":
            print(f"  {key.capitalize()}: {value}")


def run_detection():
    global running, saved_face_ratios, start_time, status_message, current_color, consent_given
    listener_thread = threading.Thread(target=always_listening, daemon=True)
    listener_thread.start()
    audio_thread = threading.Thread(target=audio_processing_thread, daemon=True)
    audio_thread.start()
    webcam = cv2.VideoCapture(0)
    with meshface.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.5) as face_mesh:
        while webcam.isOpened() and running:
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
                            current_color = (0, 255, 255)
                        else:
                            saved_face_ratios = current_fingerprint
                            status_message = "face has been recorded"
                    else:
                        diffs = [abs(c - s) for c, s in zip(current_fingerprint, saved_face_ratios)]
                        avg_diff = sum(diffs) / len(diffs)
                        if avg_diff < 0.05:
                            status_message = "recognized person"
                            current_color = (0, 255, 0)
                        else:
                            status_message = "new person"
                            current_color = (0, 0, 255)
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
                    h, w, _ = frame.shape
                    nose_x = int(face_landmarks.landmark[1].x * w)
                    nose_y = int(face_landmarks.landmark[1].y * h)
                    box_x = nose_x + 50
                    box_y = nose_y - 100
                    overlay = frame.copy()
                    box_width = 250
                    box_height = 250  # Increased height for summary display
                    cv2.rectangle(overlay, (box_x, box_y), (box_x + box_width, box_y + box_height),
                                  (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
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
                    y_offset += 30

                    # Display conversation summary if available
                    summary = person_stuff.get('last_conversation_summary', 'none')
                    if summary != 'none' and summary:
                        # Draw separator line
                        cv2.line(frame, (box_x + 10, y_offset - 5), (box_x + box_width - 10, y_offset - 5),
                                 (100, 100, 100), 1)
                        y_offset += 10

                        cv2.putText(frame, "Last Conversation:", (box_x + 10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 200, 255), 1)
                        y_offset += 20

                        # Split into sentences (2 lines)
                        sentences = summary.split('. ')
                        for i, sentence in enumerate(sentences[:2]):  # Only show first 2 sentences
                            if sentence.strip():
                                # Wrap long sentences
                                if len(sentence) > 35:
                                    words = sentence.split()
                                    line1 = ""
                                    line2 = ""
                                    for word in words:
                                        if len(line1 + word) < 35:
                                            line1 += word + " "
                                        else:
                                            line2 += word + " "

                                    cv2.putText(frame, line1.strip(), (box_x + 10, y_offset),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1)
                                    y_offset += 15
                                    if line2.strip():
                                        cv2.putText(frame, line2.strip(), (box_x + 10, y_offset),
                                                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1)
                                        y_offset += 15
                                else:
                                    cv2.putText(frame, sentence.strip(), (box_x + 10, y_offset),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1)
                                    y_offset += 15
                        y_offset += 10

                    if consent_given:
                        status_text = "SAVED" if current_person_key else "SAVED (NEW)"
                        cv2.putText(frame, f"Status: {status_text}", (box_x + 10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    else:
                        cv2.putText(frame, "Status: Awaiting Consent", (box_x + 10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(frame, status_message, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            if not consent_given:
                cv2.putText(frame, "give your consent option", (20, frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow('dot person', frame)
            if cv2.waitKey(5) & 0xFF == ord('q'):
                running = False
                break
    webcam.release()
    cv2.destroyAllWindows()


def detectPerson():
    global running
    status_label.config(text="Starting detection...")
    running = True
    # Run detection directly (not in thread) so camera opens immediately
    run_detection()


def close():
    global running
    running = False
    time.sleep(0.5)
    window.destroy()


def on_enter(e, button, style_name):
    button.configure(style=f"{style_name}.Hover.TButton")


def on_leave(e, button, style_name):
    button.configure(style=f"{style_name}.TButton")


def on_click(e, button, style_name):
    button.configure(style=f"{style_name}.Active.TButton")
    window.after(100, lambda: button.configure(style=f"{style_name}.TButton"))


window = tk.Tk()
window.title("Dementia Assistant")
window.geometry("500x430")
window.resizable(width=False, height=False)
window.attributes('-alpha', 0.0)
try:
    window.iconbitmap('Icon.ico')
except:
    try:
        icon = tk.PhotoImage(file='Icon.png')
        window.iconphoto(True, icon)
    except:
        pass
try:
    bg_image = Image.open('background.png')
    bg_image = bg_image.resize((500, 430), Image.Resampling.LANCZOS)
    bg_photo = ImageTk.PhotoImage(bg_image)
    bg_label = tk.Label(window, image=bg_photo)
    bg_label.image = bg_photo
    bg_label.place(x=0, y=0, relwidth=1, relheight=1)
except Exception as e:
    window.configure(bg="#0f172a")
    print(f"Could not load background: {e}")
style = ttk.Style()
style.theme_use("clam")
style.configure("Card.TFrame", background="#020617", relief="flat", borderwidth=0)
style.configure(
    "Title.TLabel",
    background="#020617",
    foreground="#e5e7eb",
    font=("Berlin Sans FB Demi", 24, "bold")
)
style.configure(
    "Sub.TLabel",
    background="#020617",
    foreground="#9ca3af",
    font=("Berlin Sans FB Demi", 12)
)
style.configure(
    "Main.TButton",
    font=("Berlin Sans FB Demi", 13, "bold"),
    foreground="#020617",
    background="#38bdf8",
    padding=15,
    borderwidth=0,
    relief="flat",
    focuscolor="#22c55e"
)
style.map(
    "Main.TButton",
    background=[("active", "#38bdf8")],
    foreground=[("active", "#020617")]
)
style.configure(
    "Main.Hover.TButton",
    font=("Berlin Sans FB Demi", 14, "bold"),
    foreground="#ffffff",
    background="#22c55e",
    padding=18,
    borderwidth=0,
    relief="flat"
)
style.map(
    "Main.Hover.TButton",
    background=[("active", "#22c55e")],
    foreground=[("active", "#ffffff")]
)
style.configure(
    "Main.Active.TButton",
    font=("Berlin Sans FB Demi", 14, "bold"),
    foreground="#ffffff",
    background="#0ea5e9",
    padding=18,
    borderwidth=0,
    relief="flat"
)
style.configure(
    "Quit.TButton",
    font=("Berlin Sans FB Demi", 13),
    foreground="#e5e7eb",
    background="#475569",
    padding=15,
    borderwidth=0,
    relief="flat",
    focuscolor="#ef4444"
)
style.map(
    "Quit.TButton",
    background=[("active", "#475569")],
    foreground=[("active", "#e5e7eb")]
)
style.configure(
    "Quit.Hover.TButton",
    font=("Berlin Sans FB Demi", 14),
    foreground="#ffffff",
    background="#ef4444",
    padding=18,
    borderwidth=0,
    relief="flat"
)
style.map(
    "Quit.Hover.TButton",
    background=[("active", "#ef4444")],
    foreground=[("active", "#ffffff")]
)
style.configure(
    "Quit.Active.TButton",
    font=("Berlin Sans FB Demi", 14),
    foreground="#ffffff",
    background="#dc2626",
    padding=18,
    borderwidth=0,
    relief="flat"
)
shadow_frame = tk.Frame(window, bg="#1e293b", bd=0)
shadow_frame.place(relx=0.5, rely=0.48, anchor="center")
card = ttk.Frame(window, style="Card.TFrame", padding=30)
card.place(relx=0.5, rely=0.48, anchor="center")
title = ttk.Label(card, text="Dementia Assistant", style="Title.TLabel")
subtitle = ttk.Label(
    card,
    text="Helping you stay connected",
    style="Sub.TLabel"
)
separator = ttk.Separator(card, orient="horizontal")
btn_detect = ttk.Button(
    card,
    text="👤  Detect Person",
    style="Main.TButton",
    command=detectPerson,
    cursor="hand2"
)
btn_quit = ttk.Button(
    card,
    text="✕  Quit",
    style="Quit.TButton",
    command=close,
    cursor="hand2"
)
btn_detect.bind("<Enter>", lambda e: on_enter(e, btn_detect, "Main"))
btn_detect.bind("<Leave>", lambda e: on_leave(e, btn_detect, "Main"))
btn_detect.bind("<Button-1>", lambda e: on_click(e, btn_detect, "Main"))
btn_quit.bind("<Enter>", lambda e: on_enter(e, btn_quit, "Quit"))
btn_quit.bind("<Leave>", lambda e: on_leave(e, btn_quit, "Quit"))
btn_quit.bind("<Button-1>", lambda e: on_click(e, btn_quit, "Quit"))
window.bind("<Return>", lambda e: detectPerson())
window.bind("<Escape>", lambda e: close())
title.pack(pady=(0, 5))
subtitle.pack(pady=(0, 20))
separator.pack(fill="x", pady=(0, 15))
btn_detect.pack(fill="x", pady=10)
btn_quit.pack(fill="x", pady=(10, 0))
status_frame = tk.Frame(window, bg="#0f172a", height=30)
status_frame.pack(side="bottom", fill="x")
status_label = tk.Label(status_frame, text="Ready",
                        bg="#0f172a", fg="#64748b",
                        font=("Berlin Sans FB Demi", 9))
status_label.pack(side="left", padx=10, pady=5)
version_label = tk.Label(status_frame, text="v1.0",
                         bg="#0f172a", fg="#475569",
                         font=("Berlin Sans FB Demi", 9))
version_label.pack(side="right", padx=10, pady=5)


def update_shadow():
    card.update_idletasks()
    shadow_frame.config(width=card.winfo_width() + 4, height=card.winfo_height() + 4)


window.after(50, update_shadow)


def fade_in():
    alpha = 0.0

    def animate():
        nonlocal alpha
        if alpha < 1.0:
            alpha += 0.05
            window.attributes('-alpha', alpha)
            window.after(20, animate)

    animate()


window.after(100, fade_in)
window.mainloop()
