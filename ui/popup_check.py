"""
Всплывающее окно «Всё ещё работаешь?».
Появляется каждые check_interval_min минут.
"""

import customtkinter as ctk
import config


BG_MAIN = "#1a1a1a"
BG_CARD = "#242424"
TEXT = "#e0e0e0"
ACCENT = "#3d8ef0"
GREEN = "#4caf50"
RED = "#f44336"


class PopupCheck(ctk.CTkToplevel):
    def __init__(self, master, on_yes=None, on_no=None, on_timeout=None):
        super().__init__(master)
        self.title("Geser Flow")
        self.geometry(self._position())
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        self.attributes("-topmost", True)
        self.overrideredirect(False)

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
        """Позиция в правом нижнем углу экрана."""
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except Exception:
            sw, sh = 1920, 1080
        x = sw - 300
        y = sh - 200
        return f"280x160+{x}+{y}"

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Всё ещё работаешь?",
            font=("Segoe UI", 16, "bold"), text_color=TEXT,
        ).pack(pady=(18, 10))

        self._progress = ctk.CTkProgressBar(
            self, width=240, height=8,
            fg_color=BG_CARD, progress_color=ACCENT,
        )
        self._progress.set(1.0)
        self._progress.pack(pady=(0, 12))

        self._lbl_time = ctk.CTkLabel(
            self, text=f"{self._remaining} сек",
            font=("Segoe UI", 11), text_color="#888888",
        )
        self._lbl_time.pack(pady=(0, 8))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack()

        ctk.CTkButton(
            btn_frame, text="✓ Да, работаю", width=120, height=34,
            fg_color=GREEN, hover_color="#388e3c",
            command=self._answer_yes,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="✗ Нет", width=100, height=34,
            fg_color=RED, hover_color="#c62828",
            command=self._answer_no,
        ).pack(side="left", padx=5)

    def _countdown(self):
        """Обратный отсчёт."""
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
