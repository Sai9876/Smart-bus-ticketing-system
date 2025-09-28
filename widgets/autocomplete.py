import tkinter as tk
from tkinter import ttk

class AutoComplete(ttk.Combobox):
    def __init__(self, master, values, **kwargs):
        super().__init__(master, values=values, **kwargs)
        self._all = list(values)
        self.bind('<KeyRelease>', self._on_change)

    def _on_change(self, e):
        txt = self.get().lower()
        matches = [v for v in self._all if txt in v.lower()]
        self['values'] = matches if matches else self._all
        # keep dropdown open
        if matches: self.event_generate('<Down>')
