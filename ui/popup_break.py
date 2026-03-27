"""
Всплывающее окно «Пора отдохнуть».
Появляется после break_work_interval_min минут непрерывной работы.
"""

import customtkinter as ctk
import config


BG_MAIN = "#1a1a1a"
BG_CARD = "#242424"
TEXT = "#e0e0e0"
ACCENT = "#3d8ef0"
GREEN = "#4caf50"
YELLOW = "#ff9800"


class PopupBreak(ctk.CTkToplevel):
    def __init__(self, master, work_minutes: int, on_break=None, on_skip=None):
        super().__init__(master)
        self.title("Geser Flow")
        self.geometry(self._position())
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.attributes("-topmost", True)
        self.overrideredirect(False)

        self._on_break = on_break
        self._on_skip = on_skip
        self._work_minutes = work_minutes
        self._break_minutes = config.get("break_duration_min")
        self._closed = False

        self.protocol("WM_DELETE_WINDOW", self._skip)
        self._build_ui()

    def _position(self) -> str:
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except Exception:
            sw, sh = 1920, 1080
        x = sw - 320
        y = sh - 220
        return f"300x180+{x}+{y}"

    def _build_ui(self):
        ctk.CTkLabel(
            self, text=f"Ты работаешь уже {self._work_minutes} мин.",
            font=("Segoe UI", 14, "bold"), text_color=TEXT,
        ).pack(pady=(15, 3))

        ctk.CTkLabel(
            self, text="Пора размяться!",
            font=("Segoe UI", 14), text_color=YELLOW,
        ).pack(pady=(0, 12))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(5, 0))

        ctk.CTkButton(
            btn_frame, text=f"☕ Отдохнуть {self._break_minutes}м",
            width=140, height=38, font=("Segoe UI", 13),
            fg_color=YELLOW, hover_color="#e68900", text_color="#1a1a1a",
            command=self._take_break,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="→ Продолжить",
            width=120, height=38, font=("Segoe UI", 13),
            fg_color=GREEN, hover_color="#388e3c",
            command=self._skip,
        ).pack(side="left", padx=6)

    def _take_break(self):
        self._close()
        if self._on_break:
            self._on_break()

    def _skip(self):
        self._close()
        if self._on_skip:
            self._on_skip()

    def _close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.destroy()
        except Exception:
            pass
