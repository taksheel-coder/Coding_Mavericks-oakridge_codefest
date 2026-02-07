import speech_recognition as sr
from groq import Groq
import json
import threading
import queue
import time
import os

client = Groq(api_key="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") 
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

# speech to text settings
recognizer.energy_threshold = 100
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.pause_threshold = 0.5
recognizer.phrase_threshold = 0.1
recognizer.non_speaking_duration = 0.3


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
    global person_stuff

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

    return updated

def print_info():
    print("all info:")
    for key, value in person_stuff.items():
        print(f"  {key.capitalize()}: {value}")

def main():
    global running, person_stuff, conversation_history


    listener_thread = threading.Thread(target=always_listening, daemon=True)
    listener_thread.start()

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

                text_lower = text.lower()

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



if __name__ == "__main__":
    main()
