"""
Окно настроек приложения.
Слайдеры, переключатели, автозапуск через реестр.
"""

import sys
import os
import customtkinter as ctk
import config

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")


BG_MAIN = "#0d0f0d"
BG_CARD = "#141614"
BORDER = "#2a2e2a"
TEXT = "#e8e8e8"
ACCENT = "#2ec4a0"
MUTED = "#8a8e8a"
HOVER = "#1c201c"

# Ключ автозапуска в реестре Windows
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "GeserFlow"


def _set_autostart(enabled: bool) -> bool:
    """Добавляет/удаляет ключ автозапуска. Возвращает успех."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            exe = sys.executable
            if exe.endswith("python.exe"):
                exe = exe.replace("python.exe", "pythonw.exe")
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
            script = os.path.abspath(script)
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{script}"')
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Geser Flow — Настройки")
        w, h = 360, 520
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        if os.path.exists(_ICON_PATH):
            self.after(300, lambda: self.iconbitmap(_ICON_PATH))

        self._build_ui()

    def _build_ui(self):
        # Заголовок
        ctk.CTkLabel(
            self, text="НАСТРОЙКИ",
            font=("Segoe UI", 10), text_color=MUTED,
        ).pack(padx=20, pady=(14, 8), anchor="w")

        # --- Карточка: Проверка активности ---
        card1 = ctk.CTkFrame(
            self, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        card1.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            card1, text="ПРОВЕРКА АКТИВНОСТИ",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(padx=14, pady=(10, 6), anchor="w")

        # Интервал
        row1 = ctk.CTkFrame(card1, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(0, 2))
        ctk.CTkLabel(row1, text="Интервал", text_color=TEXT, font=("Segoe UI", 12)).pack(side="left")
        self._lbl_check = ctk.CTkLabel(row1, text="", text_color=ACCENT, font=("Segoe UI", 12, "bold"))
        self._lbl_check.pack(side="right")

        self._check_interval = ctk.CTkSlider(
            card1, from_=5, to=60, number_of_steps=55,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color="#25a385",
            width=280,
        )
        self._check_interval.set(config.get("check_interval_min"))
        self._check_interval.pack(padx=14, pady=(0, 4))
        self._check_interval.configure(command=self._update_check_label)
        self._update_check_label(config.get("check_interval_min"))

        # Таймаут
        row2 = ctk.CTkFrame(card1, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(4, 2))
        ctk.CTkLabel(row2, text="Таймаут ответа", text_color=TEXT, font=("Segoe UI", 12)).pack(side="left")
        self._lbl_timeout = ctk.CTkLabel(row2, text="", text_color=ACCENT, font=("Segoe UI", 12, "bold"))
        self._lbl_timeout.pack(side="right")

        self._check_timeout = ctk.CTkSlider(
            card1, from_=30, to=120, number_of_steps=90,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color="#25a385",
            width=280,
        )
        self._check_timeout.set(config.get("check_timeout_sec"))
        self._check_timeout.pack(padx=14, pady=(0, 12))
        self._check_timeout.configure(command=self._update_timeout_label)
        self._update_timeout_label(config.get("check_timeout_sec"))

        # --- Карточка: Перекуры ---
        card2 = ctk.CTkFrame(
            self, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        card2.pack(fill="x", padx=16, pady=(0, 8))

        header2 = ctk.CTkFrame(card2, fg_color="transparent")
        header2.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(
            header2, text="РЕЖИМ ПЕРЕКУРОВ",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(side="left")

        self._break_enabled = ctk.CTkSwitch(
            header2, text="", width=40,
            fg_color=BORDER, progress_color=ACCENT,
            button_color="#c8c8c8", button_hover_color="#ffffff",
            command=self._toggle_break,
        )
        if config.get("break_mode_enabled"):
            self._break_enabled.select()
        self._break_enabled.pack(side="right")

        # Фрейм настроек перекуров
        self._break_frame = ctk.CTkFrame(card2, fg_color="transparent")

        row3 = ctk.CTkFrame(self._break_frame, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(0, 2))
        ctk.CTkLabel(row3, text="Работать без перерыва", text_color=TEXT, font=("Segoe UI", 11)).pack(side="left")
        self._lbl_break_work = ctk.CTkLabel(row3, text="", text_color=ACCENT, font=("Segoe UI", 11, "bold"))
        self._lbl_break_work.pack(side="right")

        self._break_work = ctk.CTkSlider(
            self._break_frame, from_=30, to=180, number_of_steps=150,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color="#25a385",
            width=270,
        )
        self._break_work.set(config.get("break_work_interval_min"))
        self._break_work.pack(padx=14, pady=(0, 4))
        self._break_work.configure(command=self._update_break_work_label)
        self._update_break_work_label(config.get("break_work_interval_min"))

        row4 = ctk.CTkFrame(self._break_frame, fg_color="transparent")
        row4.pack(fill="x", padx=14, pady=(4, 2))
        ctk.CTkLabel(row4, text="Длительность перерыва", text_color=TEXT, font=("Segoe UI", 11)).pack(side="left")
        self._lbl_break_dur = ctk.CTkLabel(row4, text="", text_color=ACCENT, font=("Segoe UI", 11, "bold"))
        self._lbl_break_dur.pack(side="right")

        self._break_dur = ctk.CTkSlider(
            self._break_frame, from_=5, to=30, number_of_steps=25,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color="#25a385",
            width=270,
        )
        self._break_dur.set(config.get("break_duration_min"))
        self._break_dur.pack(padx=14, pady=(0, 12))
        self._break_dur.configure(command=self._update_break_dur_label)
        self._update_break_dur_label(config.get("break_duration_min"))

        if config.get("break_mode_enabled"):
            self._break_frame.pack(fill="x")

        # --- Карточка: Автозапуск ---
        card3 = ctk.CTkFrame(
            self, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        card3.pack(fill="x", padx=16, pady=(0, 8))

        row5 = ctk.CTkFrame(card3, fg_color="transparent")
        row5.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            row5, text="Автозапуск с Windows",
            text_color=TEXT, font=("Segoe UI", 12),
        ).pack(side="left")

        self._autostart = ctk.CTkSwitch(
            row5, text="", width=40,
            fg_color=BORDER, progress_color=ACCENT,
            button_color="#c8c8c8", button_hover_color="#ffffff",
        )
        if config.get("autostart"):
            self._autostart.select()
        self._autostart.pack(side="right")

        # ---
        self._turbo = ctk.CTkSwitch(
            self, text="", width=36,
            fg_color="#1c1c1c", progress_color="#2a2e2a",
            button_color="#555555", button_hover_color="#666666",
        )
        if config.get("turbo_mode"):
            self._turbo.select()
        self._turbo.pack(anchor="e", padx=20, pady=(0, 4))

        # Кнопка сохранить
        ctk.CTkButton(
            self, text="СОХРАНИТЬ", width=310, height=42,
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=8,
            font=("Segoe UI", 14, "bold"),
            command=self._save,
        ).pack(padx=16, pady=(8, 14))

    def _update_check_label(self, val):
        self._lbl_check.configure(text=f"{int(float(val))} мин")

    def _update_timeout_label(self, val):
        self._lbl_timeout.configure(text=f"{int(float(val))} сек")

    def _update_break_work_label(self, val):
        self._lbl_break_work.configure(text=f"{int(float(val))} мин")

    def _update_break_dur_label(self, val):
        self._lbl_break_dur.configure(text=f"{int(float(val))} мин")

    def _toggle_break(self):
        if self._break_enabled.get():
            self._break_frame.pack(fill="x")
        else:
            self._break_frame.pack_forget()

    def _save(self):
        config.set("check_interval_min", int(self._check_interval.get()))
        config.set("check_timeout_sec", int(self._check_timeout.get()))
        config.set("break_mode_enabled", bool(self._break_enabled.get()))
        config.set("break_work_interval_min", int(self._break_work.get()))
        config.set("break_duration_min", int(self._break_dur.get()))

        autostart = bool(self._autostart.get())
        success = _set_autostart(autostart)
        if success:
            config.set("autostart", autostart)

        config.set("turbo_mode", bool(self._turbo.get()))

        config.save_all()
        self.destroy()
