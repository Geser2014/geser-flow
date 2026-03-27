"""
Окно настроек приложения.
Слайдеры, переключатели, автозапуск через реестр.
"""

import sys
import os
import customtkinter as ctk
import config


BG_MAIN = "#1a1a1a"
BG_CARD = "#242424"
TEXT = "#e0e0e0"
ACCENT = "#3d8ef0"
MUTED = "#888888"
GREEN = "#4caf50"

# Ключ автозапуска в реестре Windows
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "GeserFlow"


def _set_autostart(enabled: bool) -> bool:
    """Добавляет/удаляет ключ автозапуска. Возвращает успех."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            # Путь к pythonw + main.py
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
        self.geometry("340x500")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 20, "pady": (10, 2)}

        # Интервал проверки
        ctk.CTkLabel(self, text="Интервал проверки активности", text_color=TEXT,
                      font=("Segoe UI", 12)).pack(**pad, anchor="w")
        self._check_interval = ctk.CTkSlider(
            self, from_=5, to=60, number_of_steps=55,
            fg_color=BG_CARD, progress_color=ACCENT, button_color=ACCENT,
            width=280,
        )
        self._check_interval.set(config.get("check_interval_min"))
        self._check_interval.pack(padx=20, pady=(0, 0))
        self._lbl_check = ctk.CTkLabel(self, text="", text_color=MUTED, font=("Segoe UI", 11))
        self._lbl_check.pack(padx=20, anchor="w")
        self._check_interval.configure(command=self._update_check_label)
        self._update_check_label(config.get("check_interval_min"))

        # Таймаут подтверждения
        ctk.CTkLabel(self, text="Таймаут подтверждения", text_color=TEXT,
                      font=("Segoe UI", 12)).pack(**pad, anchor="w")
        self._check_timeout = ctk.CTkSlider(
            self, from_=30, to=120, number_of_steps=90,
            fg_color=BG_CARD, progress_color=ACCENT, button_color=ACCENT,
            width=280,
        )
        self._check_timeout.set(config.get("check_timeout_sec"))
        self._check_timeout.pack(padx=20, pady=(0, 0))
        self._lbl_timeout = ctk.CTkLabel(self, text="", text_color=MUTED, font=("Segoe UI", 11))
        self._lbl_timeout.pack(padx=20, anchor="w")
        self._check_timeout.configure(command=self._update_timeout_label)
        self._update_timeout_label(config.get("check_timeout_sec"))

        # Режим перекуров
        self._break_enabled = ctk.CTkSwitch(
            self, text="Режим перекуров", text_color=TEXT,
            fg_color=BG_CARD, progress_color=GREEN,
            font=("Segoe UI", 12),
            command=self._toggle_break,
        )
        if config.get("break_mode_enabled"):
            self._break_enabled.select()
        self._break_enabled.pack(**pad, anchor="w")

        # Фрейм настроек перекуров
        self._break_frame = ctk.CTkFrame(self, fg_color="transparent")

        ctk.CTkLabel(self._break_frame, text="Работать без перерыва", text_color=TEXT,
                      font=("Segoe UI", 11)).pack(padx=20, anchor="w")
        self._break_work = ctk.CTkSlider(
            self._break_frame, from_=30, to=180, number_of_steps=150,
            fg_color=BG_CARD, progress_color=ACCENT, button_color=ACCENT,
            width=260,
        )
        self._break_work.set(config.get("break_work_interval_min"))
        self._break_work.pack(padx=20)
        self._lbl_break_work = ctk.CTkLabel(self._break_frame, text="", text_color=MUTED,
                                              font=("Segoe UI", 10))
        self._lbl_break_work.pack(padx=20, anchor="w")
        self._break_work.configure(command=self._update_break_work_label)
        self._update_break_work_label(config.get("break_work_interval_min"))

        ctk.CTkLabel(self._break_frame, text="Длительность перерыва", text_color=TEXT,
                      font=("Segoe UI", 11)).pack(padx=20, anchor="w")
        self._break_dur = ctk.CTkSlider(
            self._break_frame, from_=5, to=30, number_of_steps=25,
            fg_color=BG_CARD, progress_color=ACCENT, button_color=ACCENT,
            width=260,
        )
        self._break_dur.set(config.get("break_duration_min"))
        self._break_dur.pack(padx=20)
        self._lbl_break_dur = ctk.CTkLabel(self._break_frame, text="", text_color=MUTED,
                                             font=("Segoe UI", 10))
        self._lbl_break_dur.pack(padx=20, anchor="w")
        self._break_dur.configure(command=self._update_break_dur_label)
        self._update_break_dur_label(config.get("break_duration_min"))

        if config.get("break_mode_enabled"):
            self._break_frame.pack(fill="x")

        # Автозапуск
        self._autostart = ctk.CTkSwitch(
            self, text="Автозапуск с Windows", text_color=TEXT,
            fg_color=BG_CARD, progress_color=GREEN,
            font=("Segoe UI", 12),
        )
        if config.get("autostart"):
            self._autostart.select()
        self._autostart.pack(padx=20, pady=(10, 2), anchor="w")

        # Кнопка сохранить
        ctk.CTkButton(
            self, text="Сохранить", width=280, height=38,
            fg_color=ACCENT, hover_color="#2d6ed0",
            font=("Segoe UI", 14, "bold"),
            command=self._save,
        ).pack(padx=20, pady=(15, 10))

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

        config.save_all()
        self.destroy()
