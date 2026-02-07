import speech_recognition as sr
from groq import Groq
import json

client = Groq(api_key="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")

recognizer = sr.Recognizer()

conversation_history = []

current_name = ""
new_name = ""

person_stuff = [
                ["none","none","none","none"],
                ["none","none","none","none"],
               ]
info = ""

person_number = 0

consent = True

def listen_for_speech():
    with sr.Microphone() as source:
        print("Why you not saying anything??")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        recognizer.pause_threshold = 1
        recognizer.energy_threshold = 300
        
        try:
            audio = recognizer.listen(source, timeout=1, phrase_time_limit=10)
            print("Trying to decipher your muttering")
            
            try:
                text = recognizer.recognize_google(audio, language="en-US")
                return text
            except sr.UnknownValueError:
                print("Speak better")
                    
        except sr.WaitTimeoutError:
            print("Speak god damnit")
    
print("Speak")
while True:
    print("Do you give consent to record this conversation? it will not be used for any malicious purposes or monetary gains.")
    speech = listen_for_speech()
    print(speech)
    if speech is None:
        continue
    if "yes" in speech.lower():
        break
    elif "no" in speech.lower():
        consent = False
        break

while True:
    if not consent:
        break
    speech = listen_for_speech()
    print(speech)
    response = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"Only ouput important elements of this, return only valid json always including name, hobby, age, workplace, if there's no information for one of these, just mark as none. or if there's no input or the input is not relevent, just make the exact same file as {info}, my text is {speech}.",
            }
        ],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"}
    )
    info = json.loads(response.choices[0].message.content)
    if person_stuff[person_number][0] == "none" or person_stuff[person_number][0] == ["none"]: person_stuff[person_number][0] = [info["name"]]
    if person_stuff[person_number][1] == "none" or person_stuff[person_number][1] == ["none"]: person_stuff[person_number][1] = [info["hobby"]]
    if person_stuff[person_number][2] == "none" or person_stuff[person_number][2] == ["none"]: person_stuff[person_number][2] = [info["age"]]
    if person_stuff[person_number][3] == "none" or person_stuff[person_number][3] == ["none"]: person_stuff[person_number][3] = [info["workplace"]]
    print(person_stuff)

