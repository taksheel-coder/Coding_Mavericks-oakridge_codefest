#UI

import tkinter as tk
from tkinter import ttk

def detectPerson():
    None #taksheel will make

def close():
    window.destroy()

window = tk.Tk()
window.title("Dementia Assistant")
window.geometry("500x400")
window.resizable(width = False, height =  False)
window.configure(bg="#0f172a")

style = ttk.Style()
style.theme_use("clam")

style.configure("Card.TFrame", background="#020617")

style.configure(
    "Title.TLabel",
    background="#020617",
    foreground="#e5e7eb",
    font=("Bauhaus 93", 22, "bold")
)

style.configure(
    "Sub.TLabel",
    background="#020617",
    foreground="#9ca3af",
    font=("Bauhaus 93", 11)
)

style.configure(
    "Main.TButton",
    font=("Bauhaus 93", 12, "bold"),
    foreground="#020617",
    background="#38bdf8",
    padding=10
)

style.map(
    "Main.TButton",
    background=[("active", "#0ea5e9")]
)

style.configure(
    "Quit.TButton",
    font=("Bauhaus 93", 13),
    foreground="#e5e7eb",
    background="#020617",
    padding=8
)

style.map(
    "Quit.TButton",
    foreground=[("active", "#f87171")]
)

card = ttk.Frame(window, style="Card.TFrame", padding=30)
card.place(relx=0.5, rely=0.5, anchor="center")

title = ttk.Label(card, text="Dementia Assistant", style="Title.TLabel")
subtitle = ttk.Label(
    card,
    text="Dementia Assistant",
    style="Sub.TLabel"
)

btn_detect = ttk.Button(
    card,
    text="Detect Person",
    style="Main.TButton",
    command=detectPerson
)

btn_quit = ttk.Button(
    card,
    text="Quit",
    style="Quit.TButton",
    command=close
)

title.pack(pady=(0, 5))
subtitle.pack(pady=(0, 25))
btn_detect.pack(fill="x", pady=10)
btn_quit.pack(fill="x", pady=(10, 0))

window.mainloop()
