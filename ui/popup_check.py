"""
Всплывающее окно «Всё ещё работаешь?».
Появляется каждые check_interval_min минут.
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
RED = "#e05545"
MUTED = "#8a8e8a"
HOVER = "#1c201c"


class PopupCheck(ctk.CTkToplevel):
    def __init__(self, master, on_yes=None, on_no=None, on_timeout=None):
        super().__init__(master)
        self.title("Geser Flow")
        self.geometry(self._position())
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.attributes("-topmost", True)
        self.overrideredirect(False)
        if os.path.exists(_ICON_PATH):
            self.after(300, lambda: self.iconbitmap(_ICON_PATH))

        self._on_yes = on_yes
        self._on_no = on_no
        self._on_timeout = on_timeout
        self._remaining = config.get("check_timeout_sec")
        self._total = self._remaining
        self._job = None
        self._closed = False

        self.protocol("WM_DELETE_WINDOW", self._answer_no)
        self._build_ui()
        self._countdown()

    def _position(self) -> str:
        w, h = 290, 170
        try:
            mx = self.winfo_pointerx()
            my = self.winfo_pointery()
        except Exception:
            mx, my = 960, 540
        x = mx - w // 2
        y = my - h // 2
        return f"{w}x{h}+{x}+{y}"

    def _build_ui(self):
        # Карточка
        card = ctk.CTkFrame(
            self, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=10,
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            card, text="ВСЁ ЕЩЁ РАБОТАЕШЬ?",
            font=("Segoe UI", 14, "bold"), text_color=TEXT,
        ).pack(pady=(16, 8))

        self._progress = ctk.CTkProgressBar(
            card, width=230, height=6,
            fg_color=BORDER, progress_color=ACCENT,
            corner_radius=3,
        )
        self._progress.set(1.0)
        self._progress.pack(pady=(0, 6))

        self._lbl_time = ctk.CTkLabel(
            card, text=f"{self._remaining} сек",
            font=("Segoe UI", 10), text_color=MUTED,
        )
        self._lbl_time.pack(pady=(0, 10))

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=(0, 12))

        ctk.CTkButton(
            btn_frame, text="✓ Да, работаю", width=120, height=34,
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=6,
            font=("Segoe UI", 12),
            command=self._answer_yes,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="✗ Нет", width=100, height=34,
            fg_color="transparent", hover_color="#2a1515",
            border_width=1, border_color=RED,
            text_color=RED, corner_radius=6,
            font=("Segoe UI", 12),
            command=self._answer_no,
        ).pack(side="left", padx=4)

    def _countdown(self):
        if self._closed:
            return
        if self._remaining <= 0:
            self._timeout()
            return

        self._remaining -= 1
        ratio = self._remaining / self._total if self._total > 0 else 0
        self._progress.set(ratio)
        self._lbl_time.configure(text=f"{self._remaining} сек")
        self._job = self.after(1000, self._countdown)

    def _answer_yes(self):
        self._close()
        if self._on_yes:
            self._on_yes()

    def _answer_no(self):
        self._close()
        if self._on_no:
            self._on_no()

    def _timeout(self):
        self._close()
        if self._on_timeout:
            self._on_timeout()

    def _close(self):
        self._closed = True
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        try:
            self.destroy()
        except Exception:
            pass
