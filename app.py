# --- keep this at very top ---
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import random
from db import init_schema, conn
from routes import DISTRICTS, ROUTES,ROUTE_FARES,fare_by_km, is_available
from services.fares import calc_fare
from services.qr import make_qr
from services.pdf import save_ticket_pdf
from widgets.autocomplete import AutoComplete
import speech_recognition as sr
import pyttsx3
from gtts import gTTS
from playsound import playsound
import tempfile, os
import sys, pathlib
BASE_DIR = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).resolve().parent))

DATA_DIR = pathlib.Path(os.getenv("PROGRAMDATA", str(pathlib.Path.home()))) / "SmartBus"
DATA_DIR.mkdir(parents=True, exist_ok=True)


QRS_DIR = DATA_DIR / "qrs";      QRS_DIR.mkdir(exist_ok=True)
TICKETS_DIR = DATA_DIR / "tickets"; TICKETS_DIR.mkdir(exist_ok=True)


# --- Tamil number + time helpers ---
TA_NUM = {
    "பூஜ்ஜியம்":0, "சுழியம்":0, "பூஜ்யம்":0,
    "ஒன்று":1, "ஒரு":1, "இரண்டு":2, "மூன்று":3, "நான்கு":4, "ஐந்து":5,
    "ஆறு":6, "ஏழு":7, "எட்டு":8, "ஒன்பது":9, "பத்து":10,
    "பதினொன்று":11, "பன்னிரண்டு":12, "பதிமூன்று":13, "பதிநான்கு":14, "பதினைந்து":15,
}
TA_MIN = {
    "ஐம்பது":50, "நாற்பது":40, "முப்பது":30, "இருபது":20,
    "பதினைந்து":15, "பத்து":10, "ஐந்து":5, "பூஜ்ஜியம்":0, "சுழியம்":0, "பூஜ்யம்":0
}
TA_CITY = {
    "சென்னை":"Chennai","கோயம்புத்தூர்":"Coimbatore","மதுரை":"Madurai",
    "சேலம்":"Salem","திருப்பூர்":"Tiruppur","திருச்சி":"Tiruchirappalli",
    "கன்னியாகுமரி":"Kanyakumari","வேலூர்":"Vellore"
}

import re
def ta_en_int(text: str):
    # Try digits first
    m = re.search(r"\d+", text)
    if m: return int(m.group())
    # Then Tamil words
    for w, n in TA_NUM.items():
        if w in text: return n
    return None

def ta_to_hhmm(text: str):
    # 08:30 style
    m = re.search(r"\b(\d{1,2}:\d{2})\b", text)
    if m: return m.group(1)
    # Words: "எட்டு முப்பது", "எட்டு", ...
    hour = None; minute = 0
    for w, n in TA_NUM.items():
        if w in text: hour = n
    for w, n in TA_MIN.items():
        if w in text: minute = n
    if hour is not None:
        hh = max(0, min(23, hour))
        # keep common minute values only
        if minute not in {0,5,10,15,20,30,40,45,50}: minute = 0
        return f"{hh:02d}:{minute:02d}"
    # Fallback "8 30"
    nums = re.findall(r"\d+", text)
    if len(nums) >= 2:
        return f"{int(nums[0]):02d}:{int(nums[1]):02d}"
    return None


import re

def extract_phone(s: str):
    digits = re.sub(r"\D", "", s)              # keep only numbers
    m = re.search(r"(\d{10})", digits)         # first 10-digit chunk
    return m.group(1) if m else None







def get_base_fare(b, d):
    return fare_by_km(b, d)  # km-based dynamic fare





def generate_pnr(boarding, dropping):
    """
    Generate unique PNR like: CBE-CHE-20250927-4821
    (BoardingDropping-Date-Random4digit)
    """
    prefix = f"{boarding[:3].upper()}-{dropping[:3].upper()}"
    today = datetime.now().strftime("%Y%m%d")
    rnd = random.randint(1000, 9999)
    return f"{prefix}-{today}-{rnd}"







try:
    from services.fares import calc_fare
except Exception as e:
    print("calc_fare import failed:", e)
    def calc_fare(base, seats, t=None):
        from datetime import datetime, time as _t
        now = t or datetime.now().time()
        peak = (_t(8,0) <= now <= _t(10,0)) or (_t(17,0) <= now <= _t(20,0))
        return round(max(1, seats) * float(base) * (1.2 if peak else 1.0), 2)




# ---- init ----
init_schema()
root = tk.Tk()
root.title("Smart Bus Ticketing")
root.geometry("920x620")

# ---- left: form ----
form = ttk.Frame(root, padding=16); form.pack(side="left", fill="y")

ttk.Label(form, text="Boarding").grid(row=0, column=0, sticky="w")
boarding = AutoComplete(form, DISTRICTS, width=24); boarding.grid(row=0, column=1)

ttk.Label(form, text="Dropping").grid(row=1, column=0, sticky="w")
dropping = AutoComplete(form, DISTRICTS, width=24); dropping.grid(row=1, column=1)

time_var = tk.StringVar(value="06:00")  # default a valid slot
time_box = ttk.Combobox(
    form,
    textvariable=time_var,
    width=22,
    values=["06:00","08:30","10:00","13:00","17:30","20:00"],
    state="readonly"              # <-- lock typing
)
time_box.grid(row=2, column=1)
time_box.bind("<<ComboboxSelected>>", lambda e: refresh_preview())


ttk.Label(form, text="Seats").grid(row=3, column=0, sticky="w")
seats_var = tk.IntVar(value=0)
ttk.Label(form, textvariable=seats_var, width=6).grid(row=3, column=1, sticky="w")  # read-only label

ttk.Label(form, text="Base Fare (₹)").grid(row=4, column=0, sticky="w")
base_var = tk.DoubleVar(value=199.0)
ttk.Label(form, textvariable=base_var, width=10).grid(row=4, column=1, sticky="w")  # <-- Label, not Entry

ttk.Label(form, text="Phone").grid(row=5, column=0, sticky="w")
phone_var = tk.StringVar()
ttk.Entry(form, textvariable=phone_var, width=20).grid(row=5, column=1, sticky="w")

#--------------------refresh preview------------------------------

def refresh_preview():
    b, d = boarding.get().strip(), dropping.get().strip()
    base_var.set(get_base_fare(b, d))

    tslot = time_var.get()                  # always current selection
    ok, msg = check_availability(b, d, tslot)

    fare = calc_fare(base_var.get(), seats_var.get())
    text = f"""Route: {b} → {d}
Time: {tslot}
Seats: {seats_var.get()}
Phone: {phone_var.get()}
Availability: {msg}
Estimated Fare: ₹{fare}
"""
    set_preview(text)


def _on_any_change(*_):
    refresh_preview()
    boarding.bind("<KeyRelease>", _on_any_change)
    dropping.bind("<KeyRelease>", _on_any_change)
    boarding.bind("<<ComboboxSelected>>", _on_any_change)
    dropping.bind("<<ComboboxSelected>>", _on_any_change)
    time_box.bind("<<ComboboxSelected>>", _on_any_change)


# passenger mini-table
pass_frame = ttk.LabelFrame(form, text="Passengers"); pass_frame.grid(row=6, column=0, columnspan=2, pady=10, sticky="ew")
pass_list = ttk.Treeview(pass_frame, columns=("name","age"), show="headings", height=5)
pass_list.heading("name", text="Name"); pass_list.heading("age", text="Age"); pass_list.pack(fill="x", padx=6, pady=6)

def add_passenger():
    name = simpledialog.askstring("Name", "Passenger name?")
    if not name: return
    age = simpledialog.askinteger("Age", "Age?")
    pass_list.insert("", "end", values=(name, age))

ttk.Button(pass_frame, text="+ Add Passenger", command=add_passenger).pack(pady=4)


# ---- Seat Map (A1–D10) ----
seat_frame = ttk.LabelFrame(form, text="Seat Selection")
seat_frame.grid(row=7, column=0, columnspan=2, pady=10, sticky="ew")

SEAT_ROWS = list("ABCD")
SEAT_COLS = list(range(1, 11))
selected_seats = set()
seat_buttons = {}

def update_seat_ui():
    seats_var.set(len(selected_seats))
    refresh_preview()  # updates fare too

def toggle_seat(label):
    if label in selected_seats:
        selected_seats.remove(label)
        seat_buttons[label].configure(style="TButton")
    else:
        selected_seats.add(label)
        seat_buttons[label].configure(style="Selected.TButton")
    update_seat_ui()

# style for selected
style = ttk.Style()
style.configure("Selected.TButton", relief="sunken")

# grid build
for r, row in enumerate(SEAT_ROWS):
    for c, col in enumerate(SEAT_COLS):
        label = f"{row}{col}"
        btn = ttk.Button(seat_frame, text=label, width=4, command=lambda l=label: toggle_seat(l))
        btn.grid(row=r, column=c, padx=2, pady=2)
        seat_buttons[label] = btn

def clear_seats():
    for s in list(selected_seats):
        seat_buttons[s].configure(style="TButton")
    selected_seats.clear()
    update_seat_ui()

ttk.Button(seat_frame, text="Clear Seats", command=clear_seats).grid(row=len(SEAT_ROWS), column=0, columnspan=3, pady=6, sticky="w")
ttk.Label(seat_frame, text="Selected:").grid(row=len(SEAT_ROWS), column=4, sticky="e")
sel_lbl = ttk.Label(seat_frame, textvariable=seats_var)
sel_lbl.grid(row=len(SEAT_ROWS), column=5, sticky="w")




# ---- right: actions / preview ----
right = ttk.Frame(root, padding=16); right.pack(side="left", fill="both", expand=True)
# create preview (locked)
preview = tk.Text(right, height=20, state="disabled")
preview.pack(fill="both", expand=True)

def set_preview(text: str):
    preview.config(state="normal")
    preview.delete("1.0","end")
    preview.insert("1.0", text)
    preview.config(state="disabled")




# ---- Assistant Panel ----


bot_frame = ttk.LabelFrame(right, text="AI Assistant", padding=8)
bot_frame.pack(fill="x", pady=10)

bot_log = tk.Text(bot_frame, height=10, state="disabled")
bot_log.pack(fill="x", pady=4)



# ---- Tamil / English TTS ----
engine = pyttsx3.init()

def speak(txt):
    try:
        if bot_state.get("lang","en") == "ta":
            # Tamil TTS via gTTS
            f = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(txt, lang="ta").save(f.name)
            f.close()
            playsound(f.name)
            os.unlink(f.name)
        else:
            engine.say(txt)
            engine.runAndWait()
    except Exception as e:
        print("Speak error:", e)



def bot_say(msg):
    bot_log.config(state="normal")
    bot_log.insert("end", "🤖: " + msg + "\n")
    bot_log.config(state="disabled")
    bot_log.see("end")
    speak(msg)   # now speak is already defined ✅

lang_var = tk.StringVar(value="ta")  # default Tamil
lang_row = ttk.Frame(bot_frame); lang_row.pack(fill="x", pady=(0,6))
ttk.Label(lang_row, text="Language:").pack(side="left")

lang_pick = ttk.Combobox(
    lang_row, width=10, state="readonly",
    values=["English","தமிழ்"]
)
lang_pick.set("தமிழ்")               # default select Tamil
lang_pick.pack(side="left", padx=6)

def on_lang_change(event=None):
    sel = lang_pick.get()
    bot_state["lang"] = "ta" if "தமிழ்" in sel else "en"
    msg = "வணக்கம்! உங்கள் ஏறும் இடம் (Boarding) எது?" if bot_state["lang"]=="ta" \
          else "Welcome! What's your boarding point?"
    bot_say(msg)

lang_pick.bind("<<ComboboxSelected>>", on_lang_change)

# ---- Assistant Panel ----
user_var = tk.StringVar()
user_entry = ttk.Entry(bot_frame, textvariable=user_var)
user_entry.pack(fill="x")

def user_send(event=None):
    text = user_var.get().strip()
    if not text: return
    bot_log.config(state="normal")
    bot_log.insert("end", "👤: " + text + "\n")
    bot_log.config(state="disabled")
    bot_log.see("end")
    user_var.set("")
    handle_bot(text)

user_entry.bind("<Return>", user_send)

bot_state = {"step": "welcome", "lang": "ta"}
bot_say("வணக்கம்! மொழி தமிழாக அமைக்கப்பட்டது. உங்கள் ஏறும் இடம் (Boarding) எது?")


def handle_bot(text):
    step = bot_state["step"]
    lang = bot_state.get("lang", "en")

    def T(en_msg, ta_msg):
        return ta_msg if lang == "ta" else en_msg

    if step == "welcome":
        # already greeted
        bot_state["step"] = "boarding"
        return

    elif step == "boarding":
        boarding.set(text.title())
        bot_say(T("Dropping point?", "இறங்கும் இடம் (Dropping) எது?"))
        bot_state["step"] = "dropping"

    elif step == "dropping":
        dropping.set(text.title())
        bot_say(T("How many seats?", "எத்தனை சீட்ஸ் வேண்டும்?"))
        bot_state["step"] = "seats"

    elif step == "seats":
        n = ta_en_int(text.lower()) or 1
        seats_var.set(n)
        bot_say(T("Please enter your 10-digit mobile number.",
                  "உங்கள் 10 இலக்க மொபைல் நம்பரை கொடுங்கள்."))
        bot_state["step"] = "phone"

    elif step == "phone":
        ph = extract_phone(text)
        if not ph:
            bot_say(T("That doesn't look like 10 digits. Please re-enter.",
                      "10 இலக்கம் போல இல்லை. மறுபடியும் கொடுங்கள்."))
            return
        phone_var.set(ph)
        bot_say(T("Preferred time? (e.g., 08:30)",
                  "நேரம் எது? (எ.கா: 08:30)"))
        bot_state["step"] = "time"

    elif step == "time":
        ts = ta_to_hhmm(text) or text.strip()
        if ts in time_box["values"]:
            time_var.set(ts)
        else:
            time_var.set("Now")
        refresh_preview()
        bot_say(T(
            "Now give passenger names and ages one by one (ex: Arun 23). Type 'done' when finished.",
            "இப்போ பயணிகள் பெயர் + வயதை ஒன்றன் பின் ஒன்றாகக் கொடுங்கள் (உதா: அருண் 23). முடிந்ததும் 'done' என்று type செய்யவும்."
        ))
        bot_state["step"] = "passengers"

    elif step == "passengers":
        if text.lower() == "done":
            refresh_preview()
            bot_say(T("All set! Review and click Pay.",
                      "அனைத்தும் தயார்! சரிபார்த்து 'Pay' அழுத்துங்கள்."))
            bot_state["step"] = "done"
        else:
            age = ta_en_int(text.lower())
            if age is None:
                bot_say(T("Format: Name Age (ex: Arun 23). Or type 'done'.",
                          "வடிவம்: பெயர் வயது (உதா: அருண் 23). 'done' என type செய்யலாம்."))
                return
            name = text.replace(str(age), "").strip().title()
            pass_list.insert("", "end", values=(name, age))
            bot_say(T(f"Added {name}, age {age}. Add more or type 'done'.",
                      f"{name}, வயது {age} சேர்க்கப்பட்டது. இன்னும் சேர்க்கலாம் அல்லது 'done' என்று type செய்யவும்."))



def reset_booking():
    # inputs
    boarding.set("")
    dropping.set("")
    time_var.set("Now")
    phone_var.set("")
    base_var.set(199.0)
    seats_var.set(0)

    # passengers
    for iid in pass_list.get_children():
        pass_list.delete(iid)

    # seats
    clear_seats()

    refresh_preview()
    messagebox.showinfo("Reset", "Booking details cleared ✅")

def reset_chat():
    bot_log.config(state="normal")
    bot_log.delete("1.0", "end")
    bot_log.config(state="disabled")
    # restart bot flow
    global bot_state
    bot_state = {"step": "welcome", "lang": "en"}
    bot_say("Vanakkam! Please type 'English' or 'Tamil' to continue.")






# ---- Pay flow (dummy QR) ----
qr_window = None
def pay_now():
    refresh_preview()
    import re
    if not re.fullmatch(r"\d{10}", phone_var.get().strip()):
        messagebox.showwarning("Phone", "Please enter a valid 10-digit mobile number.")
        return

    pnr = generate_pnr(boarding.get(), dropping.get())

    payload = {
        "boarding": boarding.get(),
        "dropping": dropping.get(),
        "time_slot": time_var.get(),
        "seats": len(selected_seats),
        "base_fare": get_base_fare(boarding.get(), dropping.get()),
        "final_fare": calc_fare(get_base_fare(boarding.get(), dropping.get()), len(selected_seats)),
        "phone": phone_var.get(),
        "seat_labels": ",".join(sorted(selected_seats)),
        "pnr": pnr,
    }

    # save ticket (unpaid)
    c = conn(); cur = c.cursor()
    cur.execute("""INSERT INTO tickets(pnr,boarding,dropping,time_slot,seats,base_fare,final_fare,phone,paid)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,0)""",
                (payload["pnr"], payload["boarding"], payload["dropping"], payload["time_slot"],
                 payload["seats"], payload["base_fare"], payload["final_fare"], payload["phone"]))
    c.commit(); ticket_id = cur.lastrowid


    # passengers
    rows = []
    for iid in pass_list.get_children():
        name, age = pass_list.item(iid)["values"]
        rows.append((ticket_id, name, int(age or 0)))
    if rows:
        cur.executemany("INSERT INTO passengers(ticket_id,name,age) VALUES(%s,%s,%s)", rows)
    c.commit()

    seat_labels = ",".join(sorted(selected_seats))
    cur.execute("UPDATE tickets SET seat_labels=%s WHERE id=%s", (seat_labels, ticket_id))
    c.commit()


    # dummy QR
    payload_text = f"PNR:{payload['pnr']}|{payload['boarding']}->{payload['dropping']}|₹{payload['final_fare']}"
    qr_path = make_qr(payload_text)
    cur.execute("UPDATE tickets SET qr_path=%s WHERE id=%s", (qr_path, ticket_id))
    c.commit(); cur.close(); c.close()

    # modal
    global qr_window
    qr_window = tk.Toplevel(root); qr_window.title("Scan & Pay (Demo)")
    ttk.Label(qr_window, text=f"Scan & Pay for Ticket #{ticket_id}").pack(pady=8)
    try:
        # inside pay_now() where you build the modal
        from PIL import Image, ImageTk
        img = Image.open(qr_path).resize((220,220))
        pimg = ImageTk.PhotoImage(img)
        lbl = ttk.Label(qr_window, image=pimg)
        lbl.image = pimg                 # keep reference
        lbl.pack()
        qr_window.photo = pimg           # optional extra ref

        
    except: ttk.Label(qr_window, text=f"[QR saved at {qr_path}]").pack()
    # ensure passengers == selected seats
    pax_count = len(pass_list.get_children())
    if pax_count != len(selected_seats):
        messagebox.showwarning("Seats vs Passengers",f"Selected seats: {len(selected_seats)}, Passengers: {pax_count}\n"
        "Please match passengers to selected seats.")
        return

    

    ttk.Button(qr_window, text="Mark as Paid (demo)", command=lambda: paid_and_close(ticket_id, payload)).pack(pady=10)

import pathlib

def paid_and_close(ticket_id, payload):
    # mark paid
    c = conn(); cur = c.cursor()
    cur.execute("UPDATE tickets SET paid=1 WHERE id=%s", (ticket_id,))
    c.commit(); cur.close(); c.close()
    if qr_window: qr_window.destroy()
    messagebox.showinfo("Payment", "Payment confirmed!")

    # auto save PDF in /tickets folder
    out_dir = pathlib.Path(__file__).resolve().parent / "tickets"
    out_dir.mkdir(exist_ok=True)
    auto_path = out_dir / f"ticket_{ticket_id}.pdf"

    # fetch passengers
    c = conn(); cur = c.cursor(dictionary=True)
    cur.execute("SELECT name, age FROM passengers WHERE ticket_id=%s", (ticket_id,))
    ppl = cur.fetchall(); cur.close(); c.close()

    save_ticket_pdf({"id": ticket_id, **payload}, ppl, str(auto_path))

    # show only info (no dialog)
    # messagebox.showinfo("Saved", f"Ticket auto-saved ✅\n{auto_path}")

    # OPTIONAL: Ask user if they want to save another copy
    if messagebox.askyesno("Saved",
        f"Ticket auto-saved ✅\n\n{auto_path}\n\nDo you want to save another copy?"):
        path = filedialog.asksaveasfilename(
            initialfile=f"ticket_{ticket_id}.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF files","*.pdf")],
            initialdir=str(out_dir)
        )
        if path:
            # re-use already fetched passengers
            save_ticket_pdf({"id": ticket_id, **payload}, ppl, path)
            messagebox.showinfo("Saved", f"Ticket saved to {path}")

    # OPTIONAL: Windows-ல் auto open செய்ய வேண்டும்னா:
    # try:
    #     os.startfile(str(auto_path))
    # except Exception:
    #     pass





def parse_command(text: str):
    import re
    # --- maps ---
    ta_city = {
        "சென்னை":"Chennai","கோயம்புத்தூர்":"Coimbatore","மதுரை":"Madurai",
        "சேலம்":"Salem","திருப்பூர்":"Tiruppur","திருச்சி":"Tiruchirappalli",
        "கன்னியாகுமரி":"Kanyakumari","வேலூர்":"Vellore"
    }
    ta_num = {
        "பூஜ்ஜியம்":0,"சுழியம்":0,"பூஜ்யம்":0,
        "ஒன்று":1,"ஒரு":1,"இரண்டு":2,"மூன்று":3,"நான்கு":4,"ஐந்து":5,
        "ஆறு":6,"ஏழு":7,"எட்டு":8,"ஒன்பது":9,"பத்து":10,
    }
    ta_min = {"ஐம்பது":50,"நாற்பது":40,"முப்பது":30,"இருபது":20,"பதினைந்து":15,"பத்து":10,"ஐந்து":5,"பூஜ்ஜியம்":0,"சுழியம்":0,"பூஜ்யம்":0}

    t = text.strip()

    # city: Tamil → English for matching
    for ta,en in ta_city.items():
        t = t.replace(ta, en)

    # seats: digits or tamil word
    def ta_en_int(s: str):
        m = re.search(r"\d+", s)
        if m: return int(m.group())
        for w,n in ta_num.items():
            if w in s: return n
        return None

    # time: HH:MM or tamil words ("எட்டு முப்பது")
    def ta_to_hhmm(s: str):
        m = re.search(r"\b(\d{1,2}:\d{2})\b", s)
        if m: return m.group(1)
        hour = None; minute = 0
        for w,n in ta_num.items():
            if w in s: hour = n
        for w,n in ta_min.items():
            if w in s: minute = n
        if hour is not None:
            hh = max(0, min(23, hour))
            if minute not in {0,5,10,15,20,30,40,45,50}: minute = 0
            return f"{hh:02d}:{minute:02d}"
        nums = re.findall(r"\d+", s)
        if len(nums) >= 2:
            return f"{int(nums[0]):02d}:{int(nums[1]):02d}"
        return None

    # route: "X இருந்து Y" or "X to Y"
    b = d = None
    low = " " + t.lower() + " "
    if " இருந்து " in t:
        left, right = t.split(" இருந்து ", 1)
        b = left.strip().title()
        if "க்கு" in right:
            d = right.split("க்கு",1)[0].strip().title()
        elif "வரை" in right:
            d = right.split("வரை",1)[0].strip().title()
        else:
            d = right.split()[0].title()
    elif " to " in low:
        left, right = t.lower().split(" to ", 1)
        b = left.strip().title()
        d = right.split()[0].title()

    seats = ta_en_int(t)
    ts = ta_to_hhmm(t)
    return b, d, seats, ts






def voice_fill():
    import threading, time, re
    r = sr.Recognizer()
    lang_code = "ta-IN" if bot_state.get("lang", "en") == "ta" else "en-IN"

    def animate_wave():
        dots = ""
        while getattr(animate_wave, "run", False):
            dots = (dots + "•") if len(dots) < 5 else ""
            voice_status.config(text=f"🎤 Listening {dots}", foreground="red")
            root.update_idletasks()
            time.sleep(0.4)

    with sr.Microphone() as mic:
        voice_status.config(text="🎤 Listening...", foreground="red")
        root.update_idletasks()
        animate_wave.run = True
        t = threading.Thread(target=animate_wave, daemon=True); t.start()

        try:
            if bot_state.get("lang", "en") == "ta":
                speak("சொல்லுங்கள். உதாரணம்: கோயம்புத்தூர் இருந்து சென்னைக்கு, இரண்டு சீட்ஸ், எட்டு முப்பது, மொபைல் நம்பர் 9 8 7 6 ...")
            else:
                speak("Say: Coimbatore to Chennai, 2 seats, 8:30, mobile number nine eight ...")
            r.adjust_for_ambient_noise(mic, duration=0.5)
            audio = r.listen(mic, timeout=6, phrase_time_limit=8)
        except Exception as e:
            animate_wave.run = False
            voice_status.config(text=f"⚠️ Mic error: {e}", foreground="red")
            return

    animate_wave.run = False
    voice_status.config(text="⏳ Processing...", foreground="orange")
    root.update_idletasks()

    try:
        text = r.recognize_google(audio, language=lang_code)
        voice_status.config(text=f"✅ You said: {text}", foreground="green")
    except sr.UnknownValueError:
        voice_status.config(text="⚠️ Could not understand audio", foreground="red")
        return
    except sr.RequestError as e:
        voice_status.config(text=f"⚠️ API error: {e}", foreground="red")
        return


    # --- NEW: phone extraction ---
    ph = extract_phone(text)
    if ph:
        phone_var.set(ph)

    # Parse Tamil/English route + seats + time
    b, d, s, ts = parse_command(text)
    if b: boarding.set(b)
    if d: dropping.set(d)
    if s: seats_var.set(s)
    if ts and ts in time_box['values']:
        time_var.set(ts)

    refresh_preview()

    if bot_state.get("lang") == "ta":
        speak("விவரங்கள் புதுப்பிக்கப்பட்டது")
    else:
        speak("Details updated")




def show_history():
    win = tk.Toplevel(root); win.title("Ticket History")
    cols = ("id","pnr","route","time","seats","fare","paid")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=12)

    widths = {"id":70, "pnr":160, "route":220, "time":120, "seats":70, "fare":90, "paid":70}
    for k in cols:
        tree.heading(k, text=k.upper())
        tree.column(k, width=widths[k], anchor="center")
    tree.pack(fill="both", expand=True)

    c = conn(); cur = c.cursor()
    cur.execute("""SELECT id, pnr, boarding, dropping, time_slot, seats, final_fare, paid
                   FROM tickets ORDER BY id DESC LIMIT 100""")
    for (i, pnr, b, d, tslot, s, fare, paid) in cur.fetchall():
        tree.insert("", "end", values=(i, pnr, f"{b} → {d}", tslot, s, f"₹{fare}", "Yes" if paid else "No"))
    cur.close(); c.close()


def check_availability(b, d, tslot):
    ok = is_available(b, d)
    return ok, ("Available" if ok else "Invalid districts")




bot_say("Vanakkam! Please type 'English' or 'Tamil' to continue.")
# ---- Action Buttons ----
ttk.Button(right, text="Pay", command=pay_now).pack(pady=12)

# ---- Left side extra controls (after functions are defined) ----
extra_frame = ttk.LabelFrame(form, text="Actions", padding=6)
extra_frame.grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)

voice_status = ttk.Label(extra_frame, text="", foreground="blue")
voice_status.pack(fill="x", pady=(0,4))

ttk.Button(extra_frame, text="🎤 Voice Fill", command=voice_fill).pack(fill="x", pady=2)
ttk.Button(extra_frame, text="📜 Ticket History", command=show_history).pack(fill="x", pady=2)
ttk.Button(extra_frame, text="♻️ Reset Booking", command=reset_booking).pack(fill="x", pady=2)
ttk.Button(extra_frame, text="🗑️ Clear Chat", command=reset_chat).pack(fill="x", pady=2)



# --- start UI loop ---
root.mainloop()


