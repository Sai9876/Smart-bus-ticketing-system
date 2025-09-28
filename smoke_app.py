import tkinter as tk
from db import init_schema

if __name__ == "__main__":
    init_schema()
    r = tk.Tk()
    r.title("Smart Bus • Smoke Test")
    tk.Label(r, text="App OK + DB OK").pack(padx=20, pady=20)
    r.mainloop()
