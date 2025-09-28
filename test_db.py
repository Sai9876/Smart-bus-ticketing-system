from db import conn
c = conn()
print("OK:", c.is_connected())
cur = c.cursor()
cur.execute("SELECT CURRENT_USER(), DATABASE()")
print(cur.fetchone())
cur.close(); c.close()


import speech_recognition as sr
r = sr.Recognizer()
with sr.Microphone() as mic:
    print("Say something...")
    audio = r.listen(mic)
print("You said:", r.recognize_google(audio, language="en-IN"))
