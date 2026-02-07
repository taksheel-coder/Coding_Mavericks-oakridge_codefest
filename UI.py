import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

def detectPerson():
    None #Software.py code will be here

def close():
    window.destroy()

def on_enter(e, button, style_name):
    button.configure(style=f"{style_name}.Hover.TButton")

def on_leave(e, button, style_name):
    button.configure(style=f"{style_name}.TButton")

window = tk.Tk()
window.title("Dementia Assistant")
window.geometry("500x400")
window.resizable(width = False, height = False)

try:
    window.iconbitmap('Icon.ico')
except:
    try:
        icon = tk.PhotoImage(file='Icon.png')
        window.iconphoto(True, icon)
    except:
        pass

try:
    bg_image = Image.open('background.png') # over here we have added the image that will be in the same file, working on a way to show it via gcode
    bg_image = bg_image.resize((500, 400), Image.Resampling.LANCZOS)
    bg_photo = ImageTk.PhotoImage(bg_image)
    
    bg_label = tk.Label(window, image=bg_photo)
    bg_label.image = bg_photo  
    bg_label.place(x=0, y=0, relwidth=1, relheight=1)
except Exception as e:
    window.configure(bg="#0f172a")
    print(f"Could not load background: {e}")

style = ttk.Style()
style.theme_use("clam")

style.configure("Card.TFrame", background="#020617")

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
    relief="flat"
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
    "Quit.TButton",
    font=("Berlin Sans FB Demi", 13),
    foreground="#e5e7eb",
    background="#475569",
    padding=15,
    borderwidth=0,
    relief="flat"
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
    command=detectPerson,
    cursor="hand2"
)

btn_quit = ttk.Button(
    card,
    text="Quit",
    style="Quit.TButton",
    command=close,
    cursor="hand2"
)

btn_detect.bind("<Enter>", lambda e: on_enter(e, btn_detect, "Main"))
btn_detect.bind("<Leave>", lambda e: on_leave(e, btn_detect, "Main"))

btn_quit.bind("<Enter>", lambda e: on_enter(e, btn_quit, "Quit"))
btn_quit.bind("<Leave>", lambda e: on_leave(e, btn_quit, "Quit"))

title.pack(pady=(0, 5))
subtitle.pack(pady=(0, 25))
btn_detect.pack(fill="x", pady=10)
btn_quit.pack(fill="x", pady=(10, 0))

window.mainloop()
