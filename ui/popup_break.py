"""
Всплывающее окно «Пора отдохнуть».
Появляется после break_work_interval_min минут непрерывной работы.
"""

import os
import customtkinter as ctk
import config

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")

BG_MAIN = "#0d0f0d"
BG_CARD = "#141614"
BORDER = "#2a2e2a"
TEXT = "#e8e8e8"
ACCENT = "#2ec4a0"
ORANGE = "#e8a838"
MUTED = "#8a8e8a"


class PopupBreak(ctk.CTkToplevel):
    def __init__(self, master, work_minutes: int, on_break=None, on_skip=None):
        super().__init__(master)
        self.title("Geser Flow")
        self.geometry(self._position())
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.attributes("-topmost", True)
        self.overrideredirect(False)
        if os.path.exists(_ICON_PATH):
            self.after(300, lambda: self.iconbitmap(_ICON_PATH))

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
        x = sw - 330
        y = sh - 230
        return f"310x190+{x}+{y}"

    def _build_ui(self):
        card = ctk.CTkFrame(
            self, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=10,
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            card, text=f"Ты работаешь уже {self._work_minutes} мин",
            font=("Segoe UI", 13, "bold"), text_color=TEXT,
        ).pack(pady=(16, 3))

        ctk.CTkLabel(
            card, text="Пора размяться!",
            font=("Segoe UI", 13), text_color=ORANGE,
        ).pack(pady=(0, 14))

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=(0, 14))

        ctk.CTkButton(
            btn_frame, text=f"☕ Отдохнуть {self._break_minutes}м",
            width=140, height=38, font=("Segoe UI", 12, "bold"),
            fg_color=ORANGE, hover_color="#c48a28",
            text_color="#0d0f0d", corner_radius=6,
            command=self._take_break,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="→ Продолжить",
            width=120, height=38, font=("Segoe UI", 12),
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=6,
            command=self._skip,
        ).pack(side="left", padx=5)

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
