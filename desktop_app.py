"""Sherlock AI desktop chat for Windows. No Telegram configuration required."""

import asyncio
import json
import os
from pathlib import Path
import time
import queue
import sqlite3
from datetime import date, timedelta, datetime
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from offline_workspace_app import WorkspaceWindow
from offline_workspace import OfflineWorkspace
from memory_suggestions import proposed_memory
from local_file_preview import preview_text_file
from local_document_analysis import build_document_prompt, MAX_ANALYSIS_CHARS
from local_folder_search import search_text_folder
from local_recent_files import recent_text_files, format_recent_file
from local_commands import parse_local_command
from local_action_policy import may_execute
from task_overview import filtered_tasks, describe_task
from task_daily_briefing import build_daily_briefing
from day_overview import build_day_overview
from focus_session import FocusSession
from task_planner import build_task_plan, build_day_parts, build_time_budget_plan
from task_scheduler import build_timed_schedule, describe_current_slot, shift_saved_schedule, build_remaining_day_schedule
from task_reminders import ReminderTracker, valid_reminder_time
from desktop_logic import ConversationSession
from local_ai import ask_local_ai, selected_model, installed_models


BACKGROUND = "#0b1020"
SURFACE = "#151d32"
INPUT = "#1e2942"
TEXT = "#e7eaf2"
MUTED = "#98a6c4"
ACCENT = "#8b9eff"
TONES = {"Тёплый": "warm", "Краткий": "concise", "Деловой": "professional"}


class SherlockDesktop:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.session = ConversationSession()
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.workspace_panel = None
        self.full_history = []
        self.selected_file_excerpt = ""
        self.selected_file_name = ""
        self.search_folder = ""
        self.searching = False
        self.pending_schedule = None
        self.current_page = "chat"
        self.focus_session = FocusSession()
        self.focus_target_minutes = None
        self.reminder_popup = None
        self.model_config_path = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".sherlock_ai")) / "SherlockAI" / "desktop_settings.json"
        self.reminder_tracker = ReminderTracker(self.model_config_path.parent / "shown_reminders.json")
        self.reminders_enabled = tk.BooleanVar(value=self.load_reminders_enabled())
        self.reminder_time = tk.StringVar(value=self.load_reminder_time())
        self.model_choice = tk.StringVar(value=self.load_model_choice())
        self.performance = tk.StringVar(value=self.load_performance())
        root.title("Sherlock AI — личный помощник")
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.geometry(f"{min(1120, screen_width - 40)}x{min(760, screen_height - 90)}")
        root.minsize(760, 550)
        root.configure(bg=BACKGROUND)
        root.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(root, bg=BACKGROUND, padx=20, pady=11)
        header.pack(fill="x")
        brand_row = tk.Frame(header, bg=BACKGROUND)
        brand_row.pack(fill="x")
        tk.Label(brand_row, text="✦ Sherlock AI", font=("Segoe UI", 20, "bold"),
                 fg=TEXT, bg=BACKGROUND).pack(side="left")
        self.activity = tk.Label(
            brand_row, text="Готов к общению · Telegram не требуется",
            font=("Segoe UI", 9), fg="#98e7c9", bg=BACKGROUND,
            anchor="e",
        )
        self.activity.pack(side="right", padx=(12, 0))
        tk.Label(header, text="Личный помощник · локально и приватно",
                 font=("Segoe UI", 9), fg=MUTED, bg=BACKGROUND).pack(anchor="w", pady=(3, 0))

        body = tk.Frame(root, bg=BACKGROUND)
        body.pack(fill="both", expand=True)
        self.navigation = tk.Frame(body, bg="#10182a", width=164, padx=8, pady=10)
        self.navigation.pack(side="left", fill="y")
        self.navigation.pack_propagate(False)
        self.nav_heading = tk.Label(self.navigation, text="РАЗДЕЛЫ", bg="#10182a", fg=MUTED,
                                    font=("Segoe UI", 9, "bold"))
        self.nav_heading.pack(anchor="w", padx=12, pady=(4, 12))
        self.nav_items = (
            ("●", "Общение", "chat"), ("◷", "Мой день", "day"),
            ("✓", "Задачи", "tasks"), ("✎", "Заметки", "notes"),
            ("◇", "Память", "memory"), ("▤", "История", "history"),
            ("⌕", "Инструменты", "tools"), ("⚙", "Настройки", "settings"),
        )
        self.nav_buttons = {}
        for icon, label, target in self.nav_items:
            button = tk.Button(
                self.navigation, text=f"{icon}  {label}",
                command=lambda page=target: self.show_page(page),
                bg=INPUT if target == "chat" else "#10182a", fg=TEXT,
                activebackground=INPUT, activeforeground=TEXT,
                relief="flat", borderwidth=0, highlightthickness=0,
                padx=12, pady=8, anchor="w", font=("Segoe UI", 10),
            )
            button.pack(fill="x", pady=(0, 3))
            self.nav_buttons[target] = button
        self.nav_privacy = tk.Label(
            self.navigation, text="● Только на устройстве",
            bg="#10182a", fg="#98e7c9", font=("Segoe UI", 8),
        )
        self.nav_privacy.pack(side="bottom", pady=8)
        self.nav_compact = False
        self.content_area = tk.Frame(body, bg=BACKGROUND)
        self.content_area.pack(side="left", fill="both", expand=True)
        self.chat_page = tk.Frame(self.content_area, bg=BACKGROUND)
        self.chat_page.pack(fill="both", expand=True)
        self.day_page = tk.Frame(self.content_area, bg=BACKGROUND)
        self.day_canvas = tk.Canvas(self.day_page, bg=BACKGROUND, highlightthickness=0)
        self.day_scrollbar = ttk.Scrollbar(self.day_page, orient="vertical",
                                            command=self.day_canvas.yview)
        self.day_canvas.configure(yscrollcommand=self.day_scrollbar.set)
        self.day_scrollbar.pack(side="right", fill="y")
        self.day_canvas.pack(side="left", fill="both", expand=True)
        self.day_content = tk.Frame(self.day_canvas, bg=BACKGROUND)
        self.day_canvas_window = self.day_canvas.create_window(
            (0, 0), window=self.day_content, anchor="nw",
        )
        self.day_content.bind(
            "<Configure>",
            lambda _event: self.day_canvas.configure(
                scrollregion=self.day_canvas.bbox("all"),
            ),
        )
        self.day_canvas.bind(
            "<Configure>",
            lambda event: self.day_canvas.itemconfigure(
                self.day_canvas_window, width=event.width,
            ),
        )
        tk.Label(self.day_content, text="Мой день", font=("Segoe UI", 20, "bold"),
                 bg=BACKGROUND, fg=TEXT).pack(anchor="w", padx=20, pady=(12, 2))
        tk.Label(self.day_content, text="Задачи и расписание · только локальные данные",
                 bg=BACKGROUND, fg=MUTED).pack(anchor="w", padx=20, pady=(0, 9))
        controls = tk.Frame(self.day_content, bg=BACKGROUND)
        controls.pack(fill="x", padx=20, pady=(0, 9))
        tk.Button(controls, text="↻ Обновить", command=self.refresh_day_page,
                  bg=ACCENT, fg=BACKGROUND, relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(controls, text="Все задачи", command=lambda: self.show_page("tasks"),
                  bg=INPUT, fg=TEXT, relief="flat", padx=12, pady=8).pack(side="left", padx=(8, 0))
        self.day_summary = tk.Label(self.day_content, bg=SURFACE, fg=TEXT, justify="left",
                                    anchor="w", padx=14, pady=10, wraplength=540,
                                    font=("Segoe UI", 9, "bold"))
        self.day_summary.pack(fill="x", padx=20, pady=(0, 8))
        metrics = tk.Frame(self.day_content, bg=BACKGROUND)
        metrics.pack(fill="x", padx=20, pady=(0, 8))
        self.day_metric_values = {}
        for key, title in (("tasks", "АКТУАЛЬНЫЕ ЗАДАЧИ"),
                           ("focus", "ФОКУС СЕГОДНЯ"),
                           ("load", "ОЦЕНКА НАГРУЗКИ")):
            card = tk.Frame(metrics, bg=SURFACE, padx=10, pady=8)
            card.pack(side="left", fill="x", expand=True, padx=(0, 7))
            tk.Label(card, text=title, bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            value = tk.Label(card, text="—", bg=SURFACE, fg=TEXT,
                             font=("Segoe UI", 12, "bold"))
            value.pack(anchor="w", pady=(5, 0))
            self.day_metric_values[key] = value
        self.day_progress = ttk.Progressbar(self.day_content, mode="determinate", maximum=100)
        self.day_progress.pack(fill="x", padx=20, pady=(0, 9))
        day_tabs = tk.Frame(self.day_content, bg=BACKGROUND)
        day_tabs.pack(fill="x", padx=20, pady=(0, 8))
        self.day_tab_buttons = {}
        for key, label in (("tasks", "Задачи и фокус"), ("analytics", "Расписание и аналитика")):
            button = tk.Button(day_tabs, text=label,
                               command=lambda tab=key: self.show_day_panel(tab),
                               bg=INPUT, fg=TEXT, relief="flat", padx=12, pady=7)
            button.pack(side="left", padx=(0, 8))
            self.day_tab_buttons[key] = button
        self.day_action_panel = tk.Frame(self.day_content, bg=BACKGROUND)
        self.day_analysis_panel = tk.Frame(self.day_content, bg=BACKGROUND)
        task_toolbar = tk.Frame(self.day_action_panel, bg=BACKGROUND)
        task_toolbar.pack(fill="x", padx=20, pady=(0, 5))
        tk.Label(task_toolbar, text="Ближайшие задачи", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Button(task_toolbar, text="✓ Выполнено", command=self.complete_day_task,
                  bg=INPUT, fg=TEXT, relief="flat", padx=12, pady=6).pack(side="right")
        self.day_tasks = tk.Listbox(self.day_action_panel, height=4, bg=SURFACE, fg=TEXT,
                                    selectbackground=ACCENT, selectforeground=BACKGROUND,
                                    borderwidth=0, highlightthickness=0,
                                    font=("Segoe UI", 10))
        self.day_tasks.pack(fill="x", padx=20, pady=(2, 6))
        self.day_empty_tasks = tk.Label(
            self.day_action_panel, text="На сегодня нет незавершённых задач. Хорошая работа! ✨",
            bg=SURFACE, fg=MUTED, padx=16, pady=16, anchor="w",
            font=("Segoe UI", 10),
        )
        self.day_task_rows = []
        focus_card = tk.Frame(self.day_action_panel, bg=SURFACE, padx=16, pady=12)
        focus_card.pack(fill="x", padx=20, pady=(2, 10))
        self.focus_label = tk.Label(
            focus_card, text="ГОТОВ К РАБОТЕ", bg=SURFACE, fg=MUTED,
            anchor="w", font=("Segoe UI", 9, "bold"),
        )
        self.focus_label.pack(fill="x")
        self.focus_timer_value = tk.Label(
            focus_card, text="00:00", bg=SURFACE, fg="#a9f6ce",
            anchor="w", font=("Segoe UI", 32, "bold"),
        )
        self.focus_timer_value.pack(fill="x", pady=(4, 3))
        self.focus_task_value = tk.Label(
            focus_card, text="Выбери задачу и нажми «Начать».",
            bg=SURFACE, fg=TEXT, anchor="w", justify="left",
            wraplength=430, font=("Segoe UI", 10),
        )
        self.focus_task_value.pack(fill="x", pady=(0, 6))
        self.focus_progress = ttk.Progressbar(
            focus_card, mode="determinate", maximum=100,
        )
        self.focus_progress.pack(fill="x", pady=(1, 4))
        self.focus_progress_label = tk.Label(
            focus_card, text="Оценка времени не задана",
            bg=SURFACE, fg=MUTED, anchor="w",
            font=("Segoe UI", 9),
        )
        self.focus_progress_label.pack(fill="x", pady=(0, 10))
        focus_controls = tk.Frame(focus_card, bg=SURFACE)
        focus_controls.pack(fill="x")
        self.focus_buttons = {}
        for key, label, action in (
            ("start", "▶ Начать", self.start_focus),
            ("pause", "Ⅱ Пауза", self.toggle_focus),
            ("finish", "■ Завершить", self.finish_focus),
        ):
            button = tk.Button(
                focus_controls, text=label, command=action,
                bg=ACCENT if key == "start" else INPUT,
                fg=BACKGROUND if key == "start" else TEXT,
                relief="flat", padx=10, pady=8,
            )
            button.pack(side="left", padx=(0, 8))
            self.focus_buttons[key] = button
        self.refresh_focus_label()
        self.day_feedback = tk.Label(self.day_action_panel, text="", bg=BACKGROUND, fg=MUTED,
                                     anchor="w", justify="left")
        self.day_feedback.pack(fill="x", padx=20, pady=(0, 5))
        self.day_rebalance_section = tk.Frame(self.day_action_panel, bg=BACKGROUND)
        tk.Label(self.day_rebalance_section, text="Предложенные задачи для переноса",
                 bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20)
        self.day_rebalance_tasks = tk.Listbox(
            self.day_rebalance_section, height=3, selectmode="extended",
            bg=SURFACE, fg=TEXT, selectbackground=ACCENT,
            selectforeground=BACKGROUND, borderwidth=0,
            highlightthickness=0, exportselection=False,
            font=("Segoe UI", 10),
        )
        self.day_rebalance_tasks.pack(fill="x", padx=20, pady=(5, 6))
        self.day_rebalance_rows = []
        self.day_rebalance_date = None
        tk.Button(self.day_rebalance_section, text="→ Предпросмотр и перенос выбранных на завтра",
                  command=self.confirm_day_rebalance, bg=INPUT, fg=TEXT,
                  relief="flat", padx=12, pady=7).pack(
                      anchor="w", padx=20, pady=(0, 10))
        self.day_text = ScrolledText(self.day_analysis_panel, wrap="word", bg=SURFACE, fg=TEXT,
                                    font=("Segoe UI", 10), relief="flat", padx=16,
                                    pady=14, state="disabled")
        self.day_text.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.day_text.tag_configure("active_block", foreground="#a9f6ce",
                                    background="#203a39", font=("Segoe UI", 10, "bold"))
        self.day_text.tag_configure("past_block", foreground="#7e90ad")
        self.day_text.tag_configure("future_block", foreground="#d2dcff")
        self.show_day_panel("tasks")
        self.tools_page = tk.Frame(self.content_area, bg=BACKGROUND)
        tk.Label(self.tools_page, text="Локальные инструменты", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=24, pady=(22, 7))
        tk.Label(self.tools_page, text="Просматривай файлы локально. Анализ с ИИ запускается отдельно, только после подтверждения.",
                 bg=BACKGROUND, fg=MUTED, wraplength=500, justify="left").pack(anchor="w", padx=24, pady=(0, 12))
        tk.Button(self.tools_page, text="Выбрать файл…", command=self.open_local_file,
                  bg=INPUT, fg=TEXT, activebackground=SURFACE,
                  relief="flat", padx=14, pady=8).pack(anchor="w", padx=24)
        self.analyze_file_button = tk.Button(self.tools_page, text="Проанализировать с ИИ", command=self.analyze_local_file,
                                             bg=ACCENT, fg=BACKGROUND, activebackground="#a8b6ff",
                                             relief="flat", padx=14, pady=8, state="disabled")
        self.analyze_file_button.pack(anchor="w", padx=24, pady=(9, 0))
        self.file_details = tk.Label(self.tools_page, text="Файл не выбран", bg=BACKGROUND, fg=MUTED,
                                     wraplength=520, justify="left")
        self.file_details.pack(anchor="w", padx=24, pady=(12, 6))
        self.file_preview = ScrolledText(self.tools_page, wrap="word", bg=SURFACE, fg=TEXT,
                                         font=("Consolas", 10), state="disabled", relief="flat",
                                         padx=12, pady=10)
        self.file_preview.pack(fill="both", expand=True, padx=24, pady=(0, 9))
        search_bar = tk.Frame(self.tools_page, bg=BACKGROUND)
        search_bar.pack(fill="x", padx=24, pady=(0, 7))
        tk.Button(search_bar, text="Папка…", command=self.choose_search_folder,
                  bg=INPUT, fg=TEXT, relief="flat", padx=10).pack(side="left")
        self.search_query = tk.Entry(search_bar, bg=INPUT, fg=TEXT, insertbackground=TEXT,
                                     relief="flat", font=("Segoe UI", 10))
        self.search_query.pack(side="left", fill="x", expand=True, padx=8)
        self.search_button = tk.Button(search_bar, text="Найти", command=self.start_folder_search,
                                       bg=ACCENT, fg=BACKGROUND, relief="flat", padx=10)
        self.search_button.pack(side="left")
        self.recent_button = tk.Button(search_bar, text="Недавние", command=self.start_recent_files,
                                       bg=INPUT, fg=TEXT, relief="flat", padx=10)
        self.recent_button.pack(side="left", padx=(8, 0))
        self.search_details = tk.Label(self.tools_page, text="Поиск: сначала выбери папку · без отправки в ИИ",
                                        bg=BACKGROUND, fg=MUTED, wraplength=520, justify="left")
        self.search_details.pack(anchor="w", padx=24)
        self.search_results = ScrolledText(self.tools_page, height=6, wrap="word", bg=SURFACE,
                                            fg=TEXT, font=("Consolas", 9), state="disabled",
                                            relief="flat", padx=12, pady=7)
        self.search_results.pack(fill="x", padx=24, pady=(4, 12))

        self.settings_page = tk.Frame(self.content_area, bg=BACKGROUND)
        settings_canvas = tk.Canvas(self.settings_page, bg=BACKGROUND, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(self.settings_page, orient="vertical",
                                           command=settings_canvas.yview)
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_scrollbar.pack(side="right", fill="y")
        settings_canvas.pack(side="left", fill="both", expand=True)
        settings_content = tk.Frame(settings_canvas, bg=BACKGROUND)
        settings_window = settings_canvas.create_window((0, 0), window=settings_content, anchor="nw")
        settings_content.bind("<Configure>", lambda _event: settings_canvas.configure(
            scrollregion=settings_canvas.bbox("all")))
        settings_canvas.bind("<Configure>", lambda event: settings_canvas.itemconfigure(
            settings_window, width=event.width))

        tk.Label(settings_content, text="Настройки", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=24, pady=(22, 5))
        tk.Label(settings_content, text="Настрой Sherlock AI под свой компьютер и привычки.",
                 bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 10)).pack(
                     anchor="w", padx=24, pady=(0, 14))

        def settings_card(title, subtitle):
            card = tk.Frame(settings_content, bg=SURFACE, padx=18, pady=15)
            card.pack(fill="x", padx=24, pady=(0, 12))
            tk.Label(card, text=title, bg=SURFACE, fg=TEXT,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w")
            tk.Label(card, text=subtitle, bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 9), justify="left", wraplength=590).pack(
                         anchor="w", pady=(3, 12))
            return card

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Sherlock.TCombobox", fieldbackground=INPUT, background=INPUT,
                        foreground=TEXT, arrowcolor=TEXT, borderwidth=0,
                        padding=(8, 6), font=("Segoe UI", 10))
        style.map("Sherlock.TCombobox", fieldbackground=[("readonly", INPUT)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", INPUT)],
                  selectforeground=[("readonly", TEXT)])

        model_card = settings_card(
            "◈ Локальная модель",
            "Ответы создаются на твоём компьютере через Ollama. Telegram для общения не нужен.")
        self.model_label = tk.Label(model_card, text="Модель: проверяется…",
                                    bg=SURFACE, fg="#a9f6ce", font=("Segoe UI", 10))
        self.model_label.pack(anchor="w", pady=(0, 8))
        self.model_picker = ttk.Combobox(
            model_card, textvariable=self.model_choice, width=26,
            state="readonly", style="Sherlock.TCombobox")
        self.model_picker.pack(anchor="w")
        self.model_picker.bind("<<ComboboxSelected>>", self.save_model_choice)

        behavior_card = settings_card(
            "⚡ Поведение и производительность",
            "Выбери, насколько подробными будут ответы, и как Шерлок будет общаться.")
        self.tone = tk.StringVar(value=self.load_tone())
        behavior_fields = tk.Frame(behavior_card, bg=SURFACE)
        behavior_fields.pack(fill="x")
        performance_column = tk.Frame(behavior_fields, bg=SURFACE)
        performance_column.pack(side="left", padx=(0, 20))
        tk.Label(performance_column, text="Режим ответа", bg=SURFACE, fg=MUTED).pack(anchor="w")
        self.performance_picker = ttk.Combobox(
            performance_column, textvariable=self.performance,
            values=["Быстро", "Баланс", "Качество"], width=16,
            state="readonly", style="Sherlock.TCombobox")
        self.performance_picker.pack(anchor="w", pady=(6, 0))
        self.performance_picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        tone_column = tk.Frame(behavior_fields, bg=SURFACE)
        tone_column.pack(side="left")
        tk.Label(tone_column, text="Характер общения", bg=SURFACE, fg=MUTED).pack(anchor="w")
        picker = ttk.Combobox(
            tone_column, textvariable=self.tone, state="readonly",
            values=list(TONES), width=17, style="Sherlock.TCombobox")
        picker.pack(anchor="w", pady=(6, 0))
        picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        tk.Label(behavior_card,
                 text="Быстро — коротко · Баланс — на каждый день · Качество — больше контекста",
                 bg=SURFACE, fg=MUTED, justify="left", wraplength=590,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 0))

        reminder_card = settings_card(
            "◷ Напоминания",
            "Шерлок напомнит о сроках задач, пока приложение открыто.")
        tk.Checkbutton(reminder_card, text="Включить напоминания о задачах",
                       variable=self.reminders_enabled, command=self.save_model_choice,
                       bg=SURFACE, fg=TEXT, selectcolor=INPUT,
                       activebackground=SURFACE, activeforeground=TEXT,
                       font=("Segoe UI", 10)).pack(anchor="w")
        reminder_time_row = tk.Frame(reminder_card, bg=SURFACE)
        reminder_time_row.pack(anchor="w", pady=(10, 0))
        tk.Label(reminder_time_row, text="Показывать после", bg=SURFACE, fg=MUTED).pack(
            side="left", padx=(0, 10))
        self.reminder_time_picker = ttk.Combobox(
            reminder_time_row, textvariable=self.reminder_time, width=10,
            values=["08:00", "09:00", "10:00", "12:00", "15:00", "18:00", "20:00"],
            state="readonly", style="Sherlock.TCombobox")
        self.reminder_time_picker.pack(side="left")
        self.reminder_time_picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        tk.Label(reminder_card,
                 text="Проверка раз в минуту. Без фоновой службы и системных уведомлений.",
                 bg=SURFACE, fg=MUTED, wraplength=590, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(11, 0))

        privacy_card = settings_card(
            "⌑ Приватность",
            "Задачи, заметки, память и сохранённые диалоги находятся в локальной базе SQLite.")
        tk.Label(privacy_card,
                 text="Ничего не отправляется в облако автоматически. "
                      "Анализ файлов запускается только по твоему выбору.",
                 bg=SURFACE, fg="#a9f6ce", justify="left", wraplength=590,
                 font=("Segoe UI", 9)).pack(anchor="w")

        chat_heading = tk.Frame(self.chat_page, bg=BACKGROUND, padx=24, pady=12)
        chat_heading.pack(fill="x")
        heading_text = tk.Frame(chat_heading, bg=BACKGROUND)
        heading_text.pack(side="left", fill="x", expand=True)
        tk.Label(heading_text, text="Личное общение", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        self.chat_model_status = tk.Label(
            heading_text, text="● Проверяем локальную модель…", bg=BACKGROUND,
            fg=MUTED, font=("Segoe UI", 9), anchor="w",
        )
        self.chat_model_status.pack(anchor="w", pady=(3, 0))
        quick_actions = tk.Frame(chat_heading, bg=BACKGROUND)
        quick_actions.pack(side="right", padx=(12, 0))
        tk.Button(quick_actions, text="◷ Мой день", command=lambda: self.show_page("day"),
                  bg=SURFACE, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                  relief="flat", padx=11, pady=7).pack(side="left", padx=(0, 6))
        tk.Button(quick_actions, text="✓ Задачи", command=lambda: self.show_page("tasks"),
                  bg=SURFACE, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                  relief="flat", padx=11, pady=7).pack(side="left")

        self.chat = ScrolledText(self.chat_page, height=8, wrap="word", bg=SURFACE, fg=TEXT,
                                 insertbackground=TEXT, font=("Segoe UI", 11),
                                 relief="flat", borderwidth=0, padx=18, pady=16,
                                 state="disabled", spacing2=5)
        self.chat.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self.chat.tag_configure("user", foreground=ACCENT, font=("Segoe UI", 11, "bold"),
                                spacing1=6, spacing3=3)
        self.chat.tag_configure("assistant", foreground="#98e7c9",
                                font=("Segoe UI", 11, "bold"), spacing1=6, spacing3=3)
        self.chat.tag_configure("system", foreground=MUTED)

        composer = tk.Frame(self.chat_page, bg=SURFACE, padx=12, pady=10)
        composer.pack(fill="x", padx=24)
        tk.Label(composer, text="Твоё сообщение", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))
        compose_row = tk.Frame(composer, bg=SURFACE)
        compose_row.pack(fill="x")
        self.input = tk.Text(compose_row, height=2, bg=INPUT, fg=TEXT,
                             insertbackground=TEXT, wrap="word", relief="flat",
                             font=("Segoe UI", 11), padx=12, pady=10)
        self.input.bind("<Control-Return>", self.send_event)
        self.send_button = tk.Button(compose_row, text="Отправить ↗", command=self.send,
                                     bg=ACCENT, fg=BACKGROUND, activebackground="#a8b6ff",
                                     activeforeground=BACKGROUND, relief="flat",
                                     padx=16, font=("Segoe UI", 10, "bold"))
        self.send_button.pack(side="right", padx=(10, 0), fill="y")
        self.input.pack(side="left", fill="both", expand=True)

        footer = tk.Frame(self.chat_page, bg=BACKGROUND, padx=24, pady=10)
        footer.pack(fill="x")
        self.status = tk.Label(footer, text="Ctrl+Enter — отправить · Диалог остаётся в памяти окна",
                               bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        tk.Button(footer, text="Сохранить диалог", command=self.save_conversation,
                  bg=SURFACE, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                  relief="flat", padx=10, pady=6).pack(side="right", padx=(0, 8))
        tk.Button(footer, text="Очистить", command=self.clear,
                  bg=BACKGROUND, fg=MUTED, activebackground=SURFACE,
                  activeforeground=TEXT, relief="flat", padx=8, pady=6).pack(side="right")
        self.status.pack(side="left", fill="x", expand=True)
        self.append("Sherlock AI", "Привет! ❤️ Я рядом. Расскажи, что у тебя на уме, или начни с плана дня. Для ответов нужна локальная Ollama.", "assistant")
        self.show_daily_briefing()
        self.root.after(100, self.poll)
        self.root.after(60_000, self.check_reminders)
        self.root.after(60_000, self.tick_day_page)
        self.root.after(1000, self.tick_focus)
        threading.Thread(target=self.check_model, daemon=True).start()
        self.input.focus_set()
        self.root.bind("<Configure>", self.on_window_resize)
        self.root.bind_all("<MouseWheel>", self.on_mouse_wheel, add="+")
        self.root.after_idle(lambda: self.update_navigation_layout(self.root.winfo_width()))

    def on_mouse_wheel(self, event):
        """Scroll the day overview when the pointer is over its content."""
        if self.current_page != "day" or not event.delta:
            return
        if isinstance(event.widget, (tk.Text, tk.Listbox, ttk.Treeview)):
            return
        widget = event.widget
        while widget is not None:
            if widget is self.day_page:
                self.day_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            widget = getattr(widget, "master", None)

    def on_window_resize(self, event) -> None:
        if event.widget is self.root:
            self.activity.configure(wraplength=max(160, event.width - 320))
            self.update_navigation_layout(event.width)

    def update_navigation_layout(self, width: int) -> None:
        compact = width < 960
        if self.nav_compact == compact:
            return
        self.nav_compact = compact
        self.navigation.configure(width=56 if compact else 164,
                                  padx=4 if compact else 8)
        if compact:
            self.nav_heading.pack_forget()
            self.nav_privacy.pack_forget()
        else:
            self.nav_heading.pack(anchor="w", padx=12, pady=(4, 12), before=self.nav_buttons["chat"])
            self.nav_privacy.pack(side="bottom", pady=8)
        for icon, label, target in self.nav_items:
            button = self.nav_buttons[target]
            button.configure(
                text=icon if compact else f"{icon}  {label}",
                anchor="center" if compact else "w",
                padx=2 if compact else 12,
                font=("Segoe UI", 13 if compact else 10),
            )

    def show_daily_briefing(self) -> None:
        """Show only locally stored urgent tasks; startup must survive a DB error."""
        try:
            with OfflineWorkspace() as workspace:
                briefing = build_daily_briefing(workspace.list_task_details())
        except (OSError, sqlite3.Error, ValueError):
            return
        if briefing:
            self.append("План на день", briefing, "assistant")

    def check_reminders(self) -> None:
        """Read local tasks once per minute while the application is open."""
        if self.closed:
            return
        if self.reminders_enabled.get() and time.strftime("%H:%M") >= self.reminder_time.get():
            try:
                with OfflineWorkspace() as workspace:
                    notice = self.reminder_tracker.due_messages(workspace.list_task_details())
            except (OSError, sqlite3.Error, ValueError):
                notice = ""
            if notice:
                self.append("Напоминание", notice, "assistant")
                self.show_reminder_popup(notice, tuple(self.reminder_tracker.last_displayed_ids))
        self.root.after(60_000, self.check_reminders)

    def show_reminder_popup(self, notice: str, task_ids: tuple) -> None:
        """Small in-app desktop popup, without OS permissions or dependencies."""
        if self.reminder_popup is not None:
            try:
                self.reminder_popup.destroy()
            except tk.TclError:
                pass
        popup = tk.Toplevel(self.root)
        self.reminder_popup = popup
        popup.title("Sherlock AI · Напоминание")
        popup.configure(bg=SURFACE)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        width, height = 390, 245
        x = max(0, popup.winfo_screenwidth() - width - 35)
        y = max(0, popup.winfo_screenheight() - height - 85)
        popup.geometry(f"{width}x{height}+{x}+{y}")
        tk.Label(popup, text="⏰ Sherlock AI напоминает", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(13, 5))
        tk.Label(popup, text=notice[:650], bg=SURFACE, fg=TEXT, justify="left",
                 wraplength=355, font=("Segoe UI", 9)).pack(anchor="w", padx=15)
        controls = tk.Frame(popup, bg=SURFACE)
        controls.pack(side="bottom", fill="x", padx=15, pady=12)
        intervals = {"15 минут": 15, "30 минут": 30, "1 час": 60, "2 часа": 120, "4 часа": 240}
        interval_choice = tk.StringVar(popup, value="2 часа")
        interval_picker = ttk.Combobox(controls, textvariable=interval_choice, width=10,
                                       values=list(intervals), state="readonly",
                                       style="Sherlock.TCombobox")
        interval_picker.pack(side="left", padx=(0, 6))
        tk.Button(controls, text="Отложить",
                  command=lambda: self.snooze_reminder_popup(task_ids, popup, intervals[interval_choice.get()]),
                  bg=ACCENT, fg=BACKGROUND, relief="flat", padx=8).pack(side="left")
        tk.Button(controls, text="Закрыть", command=popup.destroy,
                  bg=INPUT, fg=TEXT, relief="flat", padx=8).pack(side="right")
        popup.after(30_000, lambda: popup.destroy() if popup.winfo_exists() else None)

    def snooze_reminder_popup(self, task_ids: tuple, popup: tk.Toplevel, minutes: int) -> None:
        try:
            self.reminder_tracker.snooze(task_ids, minutes=minutes)
            self.append("Sherlock AI", f"Напоминания по выбранным задачам отложены на {minutes} мин.", "assistant")
        except (OSError, ValueError):
            self.append("Sherlock AI", "Не удалось отложить напоминания.", "assistant")
        popup.destroy()

    def open_local_file(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, title="Выбрать текстовый файл",
                                         filetypes=[("Текстовые файлы", "*.txt *.md *.json *.csv *.tsv *.log *.py *.yaml *.yml *.ini *.toml"),
                                                    ("Все файлы", "*.*")])
        if not path:
            return
        try:
            preview = preview_text_file(path)
            details = "{} · {} байт".format(preview["name"], preview["size"])
            if preview["truncated"]:
                details += " · показано только начало файла"
            content = preview["content"]
            self.selected_file_name = preview["name"]
            self.selected_file_excerpt = content
            self.analyze_file_button.configure(state="normal" if content.strip() else "disabled")
        except (OSError, ValueError) as exc:
            self.selected_file_name = ""
            self.selected_file_excerpt = ""
            self.analyze_file_button.configure(state="disabled")
            details = "Не удалось открыть файл: " + str(exc)
            content = ""
        self.file_details.configure(text=details)
        self.file_preview.configure(state="normal")
        self.file_preview.delete("1.0", "end")
        self.file_preview.insert("1.0", content)
        self.file_preview.configure(state="disabled")

    def analyze_local_file(self) -> None:
        if self.busy or self.closed:
            messagebox.showinfo("Sherlock AI занят", "Дождись завершения текущего ответа.", parent=self.root)
            return
        if not self.selected_file_excerpt.strip():
            return
        if self.input.get("1.0", "end-1c").strip():
            messagebox.showinfo("Несохранённый черновик",
                                "В чате уже есть черновик. Отправь или удали его перед анализом файла.",
                                parent=self.root)
            return
        prompt, sent_chars = build_document_prompt(self.selected_file_name, self.selected_file_excerpt)
        confirmed = messagebox.askyesno(
            "Передать фрагмент локальной модели?",
            "Файл: {}\n\nВ локальную Ollama будет передано до {} символов из выбранного файла "
            "(сейчас: {}).\n\nТекст будет виден в чате и войдёт в историю текущего диалога. "
            "Он не сохраняется на диск автоматически. Продолжить?".format(
                self.selected_file_name, MAX_ANALYSIS_CHARS, sent_chars),
            parent=self.root,
        )
        if not may_execute("analyze_file", confirmed=confirmed):
            return
        self.show_page("chat")
        self.input.insert("1.0", prompt)
        self.send()

    def choose_search_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Выбрать папку для локального поиска")
        if folder:
            self.search_folder = folder
            self.search_details.configure(text="Папка: " + folder)

    def start_folder_search(self, command_question=None, command_query=None) -> None:
        if self.searching or self.closed:
            return
        if not self.search_folder:
            self.search_details.configure(text="Сначала выбери папку.")
            return
        query = command_query if command_query is not None else self.search_query.get().strip()
        if not query or len(query) > 120:
            self.search_details.configure(text="Введите запрос длиной от 1 до 120 символов.")
            return
        self.searching = True
        self.search_button.configure(state="disabled")
        self.recent_button.configure(state="disabled")
        self.search_details.configure(text="Ищу в выбранной папке…")
        threading.Thread(target=self.search_folder_worker,
                         args=(self.search_folder, query, command_question), daemon=True).start()

    def start_recent_files(self, command_question=None) -> None:
        if self.searching or self.closed:
            return
        if not self.search_folder:
            self.search_details.configure(text="Сначала выбери папку.")
            return
        self.searching = True
        self.search_button.configure(state="disabled")
        self.recent_button.configure(state="disabled")
        self.search_details.configure(text="Проверяю даты изменения файлов…")
        threading.Thread(target=self.recent_files_worker,
                         args=(self.search_folder, command_question), daemon=True).start()

    def recent_files_worker(self, folder: str, question=None) -> None:
        try:
            result = recent_text_files(folder)
            self.events.put(("recent_files", result, None, question))
        except (OSError, ValueError) as exc:
            self.events.put(("recent_files", None, str(exc), question))

    def display_recent_files(self, result, error, question=None) -> None:
        self.searching = False
        self.search_button.configure(state="normal")
        self.recent_button.configure(state="normal")
        if error:
            self.search_details.configure(text="Ошибка просмотра: " + error)
            if question:
                self.append("Sherlock AI", "Не удалось показать файлы: " + error, "assistant")
            return
        self.search_details.configure(text="Недавно изменённые документы · проверено: {}{}".format(
            result["checked"], " · достигнут лимит" if result["limit_reached"] else ""))
        entries = [format_recent_file(item) for item in result["files"]]
        self.search_results.configure(state="normal")
        self.search_results.delete("1.0", "end")
        self.search_results.insert("1.0", "\n\n".join(entries) if entries else "Текстовых файлов не найдено.")
        self.search_results.configure(state="disabled")
        if question:
            self.append("Sherlock AI", "Последние документы (подробности в «Инструментах»):\n" +
                        ("\n".join(item["path"] for item in result["files"][:5]) or "Файлов нет."), "assistant")

    def search_folder_worker(self, folder: str, query: str, question=None) -> None:
        try:
            result = search_text_folder(folder, query)
            self.events.put(("folder_search", result, None, question))
        except (OSError, ValueError) as exc:
            self.events.put(("folder_search", None, str(exc), question))

    def display_folder_search(self, result, error, question=None) -> None:
        self.searching = False
        self.search_button.configure(state="normal")
        self.recent_button.configure(state="normal")
        if error:
            self.search_details.configure(text="Ошибка поиска: " + error)
            if question:
                self.append("Sherlock AI", "Поиск не завершён: " + error, "assistant")
            return
        self.search_details.configure(text="Проверено: {} · найдено: {} · пропущено: {}{}".format(
            result["checked"], len(result["matches"]), result["skipped"],
            " · достигнут лимит поиска" if result["limit_reached"] else ""))
        lines = []
        for item in result["matches"]:
            lines.append("{}\n  {}\n".format(item["path"], item["excerpt"]))
        self.search_results.configure(state="normal")
        self.search_results.delete("1.0", "end")
        self.search_results.insert("1.0", "\n".join(lines) if lines else "Совпадений не найдено.")
        self.search_results.configure(state="disabled")
        if question:
            self.append("Sherlock AI", "Найдено совпадений: {}. Подробности в «Инструментах».\n{}".format(
                len(result["matches"]), "\n".join(item["path"] for item in result["matches"][:5])), "assistant")

    def selected_day_task(self):
        selected = self.day_tasks.curselection()
        if selected and selected[0] < len(self.day_task_rows):
            return self.day_task_rows[selected[0]]
        return None

    def start_focus(self) -> None:
        selected = self.selected_day_task()
        if selected is None:
            self.day_feedback.configure(text="Выбери задачу для фокусировки.")
            return
        try:
            self.focus_session.start(*selected)
            self.focus_target_minutes = None
            try:
                with OfflineWorkspace() as workspace:
                    for task in workspace.list_task_estimates():
                        if task[0] == selected[0]:
                            self.focus_target_minutes = task[5]
                            break
            except (OSError, sqlite3.Error):
                pass
            self.day_feedback.configure(text="Фокус-сессия начата. Таймер работает локально.")
            self.refresh_focus_label()
        except ValueError as exc:
            self.day_feedback.configure(text=str(exc))

    def toggle_focus(self) -> None:
        try:
            if self.focus_session.paused:
                self.focus_session.resume()
            else:
                self.focus_session.pause()
            self.refresh_focus_label()
        except ValueError as exc:
            self.day_feedback.configure(text=str(exc))

    def finish_focus(self) -> None:
        if not self.focus_session.active:
            self.day_feedback.configure(text="Сначала начни фокус-сессию.")
            return
        task_id, title, duration = self.focus_session.finish()
        self.focus_target_minutes = None
        self.refresh_focus_label()
        self.day_feedback.configure(text=f"Сессия завершена: {duration // 60} мин. {duration % 60} сек.")
        save_approved = duration > 0 and messagebox.askyesno(
            "Сохранить время работы?",
            f"Сохранить {duration // 60} мин. {duration % 60} сек. по задаче #{task_id} в локальной истории?",
            parent=self.root,
        )
        if may_execute("save_focus", confirmed=save_approved):
            try:
                with OfflineWorkspace() as workspace:
                    workspace.save_focus_session(task_id, title, duration, date.today().isoformat())
            except (OSError, sqlite3.Error, ValueError):
                self.day_feedback.configure(text="Сессия завершена, но сохранить время не удалось.")
        if messagebox.askyesno(
            "Отметить задачу выполненной?",
            f"Фокус-сессия по задаче #{task_id} завершена.\n\n{title[:200]}\n\nОтметить задачу выполненной?",
            parent=self.root,
        ) and may_execute("complete_task", confirmed=True):
            try:
                with OfflineWorkspace() as workspace:
                    workspace.complete_task(task_id)
                self.refresh_day_page()
            except (OSError, sqlite3.Error):
                self.day_feedback.configure(text="Сессия завершена, но изменить задачу не удалось.")

    def refresh_focus_label(self) -> None:
        active = self.focus_session.active
        paused = active and self.focus_session.paused
        seconds = self.focus_session.seconds() if active else 0
        self.focus_timer_value.configure(
            text=f"{seconds // 60:02d}:{seconds % 60:02d}",
            fg="#ffd38a" if paused else "#a9f6ce",
        )
        self.focus_label.configure(
            text="ПАУЗА" if paused else "В РАБОТЕ" if active else "ГОТОВ К РАБОТЕ",
            fg="#ffd38a" if paused else "#a9f6ce" if active else MUTED,
        )
        self.focus_task_value.configure(
            text=(f"#{self.focus_session.task_id} · {self.focus_session.title[:75]}"
                  if active else "Выбери задачу и нажми «Начать»."),
        )
        target = self.focus_target_minutes if active else None
        if target:
            elapsed_minutes = seconds // 60
            self.focus_progress["value"] = min(100, seconds * 100 / (target * 60))
            remaining = max(0, target * 60 - seconds)
            if seconds >= target * 60:
                progress_text = f"Ориентир {target} мин достигнут · +{(seconds - target * 60) // 60} мин"
            else:
                progress_text = (
                    f"Ориентир {target} мин · осталось "
                    f"{remaining // 60} мин {remaining % 60} сек"
                )
            self.focus_progress_label.configure(text=progress_text, fg=TEXT)
        else:
            self.focus_progress["value"] = 0
            self.focus_progress_label.configure(
                text="Оценка времени не задана" if active else "Ожидание начала работы",
                fg=MUTED,
            )
        self.focus_buttons["start"].configure(state="disabled" if active else "normal")
        self.focus_buttons["pause"].configure(
            state="normal" if active else "disabled",
            text="▶ Продолжить" if paused else "Ⅱ Пауза",
        )
        self.focus_buttons["finish"].configure(state="normal" if active else "disabled")

    def tick_focus(self) -> None:
        if self.closed:
            return
        if self.current_page == "day" and self.focus_session.active:
            self.refresh_focus_label()
        self.root.after(1000, self.tick_focus)

    def complete_day_task(self) -> None:
        selection = self.day_tasks.curselection()
        if not selection or selection[0] >= len(self.day_task_rows):
            self.day_feedback.configure(text="Сначала выбери задачу из списка.")
            return
        task_id, title = self.day_task_rows[selection[0]]
        approved = messagebox.askyesno(
            "Завершить задачу?",
            f"Отметить задачу #{task_id} выполненной?\n\n{title[:200]}",
            parent=self.root,
        )
        if not may_execute("complete_task", confirmed=approved):
            return
        try:
            with OfflineWorkspace() as workspace:
                changed = workspace.complete_task(task_id)
            self.day_feedback.configure(text="Задача завершена." if changed else "Задача уже завершена или удалена.")
            self.refresh_day_page()
        except (OSError, sqlite3.Error):
            self.day_feedback.configure(text="Не удалось изменить задачу.")

    def show_day_panel(self, panel: str) -> None:
        """Switch visible day content without rebuilding widgets or losing state."""
        if panel not in ("tasks", "analytics"):
            return
        self.day_action_panel.pack_forget()
        self.day_analysis_panel.pack_forget()
        target = self.day_action_panel if panel == "tasks" else self.day_analysis_panel
        target.pack(fill="both", expand=True)
        for name, button in self.day_tab_buttons.items():
            button.configure(bg=ACCENT if name == panel else INPUT,
                             fg=BACKGROUND if name == panel else TEXT)

    def confirm_day_rebalance(self) -> None:
        """Show exact due-date changes and require explicit approval."""
        selected = self.day_rebalance_tasks.curselection()
        rows = [self.day_rebalance_rows[index] for index in selected
                if index < len(self.day_rebalance_rows)]
        if not rows:
            self.day_feedback.configure(text="Выбери задачи из списка предложений.")
            return
        day = self.day_rebalance_date
        if day is None or day != date.today().isoformat():
            self.day_feedback.configure(text="Дата изменилась. Обнови страницу.")
            return
        tomorrow = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        preview = "\n".join(
            f"#{task_id} {title[:70]}: {day} → {tomorrow}"
            for task_id, title, _, _ in rows
        )
        approved = messagebox.askyesno(
            "Подтвердить перенос задач?",
            "Изменятся только сроки выбранных задач:\n\n" + preview +
            "\n\nПеренести эти задачи на завтра?",
            parent=self.root,
        )
        if not may_execute("defer_tasks", confirmed=approved):
            return
        try:
            with OfflineWorkspace() as workspace:
                changed = workspace.defer_nonurgent_tasks(
                    day, [task_id for task_id, _, _, _ in rows],
                )
            self.refresh_day_page()
            self.day_feedback.configure(text=f"Перенесено задач: {changed}.")
        except (OSError, sqlite3.Error, ValueError):
            self.day_feedback.configure(
                text="Список задач изменился или перенос не удался. Обнови страницу.")

    def tick_day_page(self) -> None:
        """Refresh only the visible planner; stop scheduling on window close."""
        if self.closed:
            return
        if self.current_page == "day":
            self.refresh_day_page()
        self.root.after(60_000, self.tick_day_page)

    def refresh_day_page(self) -> None:
        selected = self.day_tasks.curselection()
        selected_id = (self.day_task_rows[selected[0]][0]
                       if selected and selected[0] < len(self.day_task_rows) else None)
        self.day_task_rows = []
        self.day_tasks.delete(0, "end")
        self.day_rebalance_rows = []
        self.day_rebalance_date = None
        self.day_rebalance_tasks.delete(0, "end")
        self.day_progress["value"] = 0
        for value in self.day_metric_values.values():
            value.configure(text="—", fg=TEXT)
        if not may_execute("view_plan") or not may_execute("list_tasks"):
            self.day_summary.configure(text="Доступ к данным ограничен")
            sections = "Просмотр задач или расписания запрещён настройками безопасности."
        else:
            try:
                with OfflineWorkspace() as workspace:
                    tasks = workspace.list_task_details()
                    saved = workspace.latest_plan()
                    if may_execute("view_focus"):
                        focus_count, focus_seconds = workspace.focus_day_summary(date.today().isoformat())
                        week_count, week_seconds = workspace.focus_week_summary(date.today().isoformat())
                        recent_focus = workspace.recent_focus_sessions()
                        top_focus = workspace.top_focus_tasks(date.today().isoformat())
                        focus_vs_estimate = workspace.focus_estimate_comparison(date.today().isoformat())
                        focus_suggestions = workspace.focus_duration_recommendations(date.today().isoformat())
                        focus_week_days = workspace.focus_last_seven_days(date.today().isoformat())
                        workload = workspace.day_workload_snapshot(date.today().isoformat())
                        rebalance = workspace.suggest_day_rebalance(date.today().isoformat())
                    else:
                        focus_count, focus_seconds = 0, 0
                        week_count, week_seconds = 0, 0
                        recent_focus = []
                        top_focus = []
                        focus_vs_estimate = []
                        focus_suggestions = []
                        focus_week_days = []
                        workload = None
                        rebalance = None
                now = datetime.now()
                if rebalance is not None and rebalance[1]:
                    self.day_rebalance_date = now.date().isoformat()
                    self.day_rebalance_rows = list(rebalance[1])
                    for task_id, title, minutes, priority in self.day_rebalance_rows:
                        badge = "Низкий" if priority == "low" else "Обычный"
                        self.day_rebalance_tasks.insert(
                            "end", f"#{task_id} · {title[:65]} · {minutes} мин · {badge}"
                        )
                summary, status, tasks_text, timeline = build_day_overview(
                    tasks, saved, now=now)
                relevant = [item for item in tasks if item[4] and item[4] <= now.date().isoformat()]
                completed = sum(1 for item in relevant if item[2])
                self.day_progress["value"] = 100 * completed / len(relevant) if relevant else 0
                open_tasks = sorted(
                    (item for item in relevant if not item[2]),
                    key=lambda item: (item[4], {"high": 0, "normal": 1, "low": 2}.get(item[3], 1), item[0]),
                )[:12]
                self.day_task_rows = [(item[0], item[1]) for item in open_tasks]
                for index, item in enumerate(open_tasks):
                    task_id, title, _, priority, due_date = item
                    overdue = due_date < now.date().isoformat()
                    badge = "⚠ ПРОСРОЧЕНО" if overdue else ("● СРОЧНО" if priority == "high" else "· Сегодня")
                    self.day_tasks.insert("end", f"{badge}  #{task_id} · {title}")
                    if overdue:
                        self.day_tasks.itemconfig(index, fg="#ffb0a5")
                    elif priority == "high":
                        self.day_tasks.itemconfig(index, fg="#ffd38a")
                    if task_id == selected_id:
                        self.day_tasks.selection_set(index)
                if open_tasks:
                    self.day_empty_tasks.pack_forget()
                    self.day_tasks.pack(fill="x", padx=20, pady=(2, 6),
                                        before=self.focus_label.master)
                else:
                    self.day_tasks.pack_forget()
                    self.day_empty_tasks.pack(fill="x", padx=20, pady=(2, 6),
                                              before=self.focus_label.master)
                if self.day_rebalance_rows:
                    self.day_rebalance_section.pack(fill="x", pady=(4, 7))
                else:
                    self.day_rebalance_section.pack_forget()
                self.day_metric_values["tasks"].configure(
                    text=f"{sum(not item[2] for item in relevant)} открыто",
                    fg="#ffb0a5" if any(not item[2] and item[4] < now.date().isoformat() for item in relevant)
                    else TEXT,
                )
                self.day_metric_values["focus"].configure(
                    text=f"{focus_seconds // 3600} ч {(focus_seconds % 3600) // 60} мин",
                    fg="#a9f6ce",
                )
                if workload is None:
                    self.day_metric_values["load"].configure(text="Нет данных")
                else:
                    total_minutes, _, unknown_tasks, typical_minutes, _ = workload
                    is_overloaded = (typical_minutes is not None and not unknown_tasks
                                     and total_minutes > typical_minutes * 1.2
                                     and total_minutes - typical_minutes >= 30)
                    self.day_metric_values["load"].configure(
                        text=f"{total_minutes // 60} ч {total_minutes % 60} мин"
                             + (" +" if unknown_tasks else ""),
                        fg="#ffb0a5" if is_overloaded else "#ffd38a" if unknown_tasks else TEXT,
                    )
                self.day_summary.configure(
                    text=summary + f"\nФокус сегодня: {focus_seconds // 3600} ч "
                         f"{(focus_seconds % 3600) // 60} мин · сессий: {focus_count}")
                recent_lines = "\n".join(
                    f"{session_day} · #{task_id} {title[:55]} · {seconds // 60} мин. {seconds % 60} сек."
                    for task_id, title, seconds, session_day in recent_focus
                ) or "Сохранённых сессий пока нет."
                max_focus = max((seconds for _, _, _, seconds in top_focus), default=0)
                top_lines = "\n".join(
                    f"#{task_id} {title[:35]} · "
                    f"{seconds // 3600} ч {(seconds % 3600) // 60} мин · "
                    f"{sessions} сесс.\n"
                    f"{'▰' * max(1, round(seconds * 12 / max_focus))}"
                    for task_id, title, sessions, seconds in top_focus
                ) or "Пока нет сохранённых фокус-сессий за неделю."
                estimate_lines = "\n".join(
                    f"#{task_id} {title[:35]} · оценка {estimate} мин / "
                    f"факт {actual // 60} мин · "
                    f"{'+' if actual > estimate * 60 else '−' if actual < estimate * 60 else '='}"
                    f"{abs(actual - estimate * 60) // 60} мин"
                    for task_id, title, estimate, actual in focus_vs_estimate
                ) or "Сегодня нет завершённых сессий по задачам с оценкой времени."
                suggestions_text = "\n".join(
                    f"#{task_id} {title[:35]} · оценка {estimate} мин → "
                    f"ориентир {suggested} мин/день (дней с работой: {days})"
                    for task_id, title, estimate, suggested, days in focus_suggestions
                ) or "Недостаточно истории для надёжных подсказок."
                week_max = max((seconds for _, seconds in focus_week_days), default=0)
                weekdays = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
                week_chart = "\n".join(
                    f"{weekdays[date.fromisoformat(day).weekday()]} {day[5:]}  "
                    f"{'▰' * max(1, round(seconds * 12 / week_max)) if seconds else '·'} "
                    f"{seconds // 3600} ч {(seconds % 3600) // 60} мин"
                    for day, seconds in focus_week_days
                ) if focus_week_days else "Статистика недоступна."
                if workload is None:
                    workload_text = "Оценка нагрузки недоступна."
                else:
                    minutes, known_tasks, unknown_tasks, typical, active_days = workload
                    workload_text = (
                        f"Срочные и просроченные открытые задачи: "
                        f"{minutes // 60} ч {minutes % 60} мин "
                        f"(с оценкой: {known_tasks}, без оценки: {unknown_tasks})."
                    )
                    if typical is None:
                        workload_text += "\nПока недостаточно истории для сравнения (нужно 3 дня активности)."
                    else:
                        workload_text += (
                            f"\nТипичное сохранённое фокус-время: "
                            f"{typical // 60} ч {typical % 60} мин/день "
                            f"(дней: {active_days})."
                        )
                        if unknown_tasks:
                            workload_text += "\nЧасть задач без оценки; полная нагрузка неизвестна."
                        elif minutes > typical * 1.2 and minutes - typical >= 30:
                            workload_text += "\n⚠ Возможно, день перегружен. Проверь приоритеты и перерывы."
                        else:
                            workload_text += "\nПо сохранённым данным явного превышения не видно."
                if rebalance is None:
                    rebalance_text = "Предложения недоступны."
                else:
                    excess, candidates, remaining = rebalance
                    if not excess:
                        rebalance_text = "Сейчас нет оснований предлагать перенос."
                    elif not candidates:
                        rebalance_text = "Перегрузка есть, но подходящих несрочных задач на сегодня нет."
                    else:
                        rebalance_text = "\n".join(
                            f"• #{task_id} {title[:40]} · {minutes} мин · "
                            f"{'низкий' if priority == 'low' else 'обычный'} приоритет"
                            for task_id, title, minutes, priority in candidates
                        )
                        rebalance_text += (
                            f"\nИзбыток оценки над обычным фокус-временем: {excess} мин."
                            "\nЭто лишь предложение. Сроки задач не изменены."
                        )
                        if remaining:
                            rebalance_text += f"\nОстанется нераспределённым: {remaining} мин."
                sections = ("СЕЙЧАС\n" + status +
                            "\n\nОЦЕНКА НАГРУЗКИ · ТОЛЬКО ПОДСКАЗКА\n" + workload_text +
                            "\n\nВОЗМОЖНЫЙ ПЕРЕНОС · БЕЗ ИЗМЕНЕНИЙ\n" + rebalance_text +
                            "\n\nБЛИЖАЙШИЕ ЗАДАЧИ\n" + tasks_text +
                            "\n\nВРЕМЕННАЯ ШКАЛА\n" + timeline +
                            "\n\nФОКУС ЗА 7 ДНЕЙ\n" +
                            f"{week_seconds // 3600} ч {(week_seconds % 3600) // 60} мин · "
                            f"сессий: {week_count}\n" +
                            week_chart +
                            "\n\nПЛАН И ФАКТ ПО ЗАДАЧАМ СЕГОДНЯ\n" + estimate_lines +
                            "\n\nПОДСКАЗКИ ПО ВРЕМЕНИ · БЕЗ ИЗМЕНЕНИЯ ЗАДАЧ\n" + suggestions_text +
                            "\n\nТОП ЗАДАЧ ПО ВРЕМЕНИ (7 ДНЕЙ)\n" + top_lines +
                            "\n\nПОСЛЕДНИЕ СЕССИИ\n" + recent_lines)
            except (OSError, sqlite3.Error, ValueError):
                self.day_summary.configure(text="Не удалось загрузить данные")
                sections = "Проверь локальное хранилище задач."
        self.day_text.configure(state="normal")
        self.day_text.delete("1.0", "end")
        self.day_text.insert("1.0", sections)
        for index, line in enumerate(sections.splitlines(), start=1):
            tag = ("active_block" if line.startswith("▶  ") else
                   "past_block" if line.startswith("✓  ") else
                   "future_block" if line.startswith("○  ") else None)
            if tag:
                self.day_text.tag_add(tag, f"{index}.0", f"{index}.end")
        self.day_text.configure(state="disabled")

    def show_page(self, page: str) -> None:
        self.current_page = page
        for name, button in self.nav_buttons.items():
            button.configure(bg=INPUT if name == page else "#10182a")
        self.chat_page.pack_forget()
        self.day_page.pack_forget()
        self.settings_page.pack_forget()
        self.tools_page.pack_forget()
        if self.workspace_panel is not None:
            self.workspace_panel.window.pack_forget()
        if page == "chat":
            self.chat_page.pack(fill="both", expand=True)
            return
        if page == "day":
            self.refresh_day_page()
            self.day_page.pack(fill="both", expand=True)
            return
        if page == "settings":
            self.settings_page.pack(fill="both", expand=True)
            return
        if page == "tools":
            self.tools_page.pack(fill="both", expand=True)
            return
        if self.workspace_panel is None:
            workspace_frame = tk.Frame(self.content_area, bg=BACKGROUND)
            self.workspace_panel = WorkspaceWindow(workspace_frame, embedded=True,
                                                  on_open_conversation=self.open_conversation)
        self.workspace_panel.select_tab({"tasks": 0, "notes": 1, "memory": 2, "history": 3}.get(page, 0))
        self.workspace_panel.window.pack(fill="both", expand=True)

    def append(self, name: str, message: str, kind: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", name + "\n", kind)
        self.chat.insert("end", message + "\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def load_model_choice(self) -> str:
        try:
            return json.loads(self.model_config_path.read_text(encoding="utf-8")).get("model", "Авто")
        except (OSError, ValueError, TypeError):
            return "Авто"

    def load_tone(self) -> str:
        try:
            value = json.loads(self.model_config_path.read_text(encoding="utf-8")).get("tone", "Тёплый")
            return value if value in TONES else "Тёплый"
        except (OSError, ValueError, TypeError):
            return "Тёплый"

    def load_reminder_time(self) -> str:
        try:
            value = json.loads(self.model_config_path.read_text(encoding="utf-8")).get("reminder_time", "09:00")
            return value if valid_reminder_time(value) else "09:00"
        except (OSError, ValueError, TypeError):
            return "09:00"

    def load_reminders_enabled(self) -> bool:
        try:
            value = json.loads(self.model_config_path.read_text(encoding="utf-8")).get("reminders_enabled", False)
            return value is True
        except (OSError, ValueError, TypeError):
            return False

    def load_performance(self) -> str:
        try:
            value = json.loads(self.model_config_path.read_text(encoding="utf-8")).get("performance", "Быстро")
            return value if value in ("Быстро", "Баланс", "Качество") else "Быстро"
        except (OSError, ValueError, TypeError):
            return "Быстро"

    def save_model_choice(self, event=None) -> None:
        try:
            self.model_config_path.parent.mkdir(parents=True, exist_ok=True)
            self.model_config_path.write_text(json.dumps({"model": self.model_choice.get(), "performance": self.performance.get(),
                                                        "tone": self.tone.get(), "reminders_enabled": self.reminders_enabled.get(), "reminder_time": self.reminder_time.get()}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            self.status.configure(text="Не удалось сохранить выбор модели.")

    def append_stream_start(self) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", "Sherlock AI\n", "assistant")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def append_stream_chunk(self, chunk: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", chunk)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def check_model(self) -> None:
        try:
            result = selected_model()
            models = installed_models()
            self.events.put(("model", "Модель: " + result, models))
        except Exception:
            self.events.put(("model", "Ollama не готова · проверь установку и модель"))

    def send_event(self, event) -> str:
        self.send()
        return "break"

    def send(self) -> None:
        if self.busy or self.closed:
            return
        question = self.input.get("1.0", "end-1c").strip()
        if not question:
            return
        command = parse_local_command(question)
        if command is not None:
            self.input.delete("1.0", "end")
            self.append("Ты", question, "user")
            if command[0] == "save_note":
                approved = messagebox.askyesno(
                    "Сохранить заметку?",
                    "Добавить заметку в локальную базу Sherlock AI?\n\n" + command[1][:500],
                    parent=self.root,
                )
                if not may_execute("save_note", confirmed=approved):
                    self.append("Sherlock AI", "Заметка не сохранена.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        workspace.add_note(command[1])
                    if self.workspace_panel is not None:
                        self.workspace_panel.refresh()
                    self.append("Sherlock AI", "Заметка сохранена локально. Посмотреть её можно в разделе «Заметки».", "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось сохранить заметку.", "assistant")
                return
            if command[0] == "snooze_reminder":
                task_id, minutes = command[1]
                try:
                    with OfflineWorkspace() as workspace:
                        task = next((entry for entry in workspace.list_task_details()
                                     if entry[0] == task_id), None)
                    if task is None:
                        self.append("Sherlock AI", f"Задача #{task_id} не найдена.", "assistant")
                    elif task[2]:
                        self.append("Sherlock AI", f"Задача #{task_id} уже выполнена.", "assistant")
                    elif not task[4]:
                        self.append("Sherlock AI", "У этой задачи нет срока — напоминание пока не назначено.", "assistant")
                    else:
                        approved = messagebox.askyesno(
                            "Отложить напоминание?",
                            f"Задача #{task_id}: {task[1]}\n\nОтложить на {minutes} мин.?",
                            parent=self.root,
                        )
                        if may_execute("snooze_reminder", confirmed=approved):
                            self.reminder_tracker.snooze([task_id], minutes=minutes)
                            self.append("Sherlock AI",
                                        f"Напоминание о задаче #{task_id} отложено на {minutes} мин.",
                                        "assistant")
                        else:
                            self.append("Sherlock AI", "Напоминание не изменено.", "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось отложить напоминание.", "assistant")
                return
            if command[0] == "set_task_estimate":
                task_id, minutes = command[1]
                try:
                    with OfflineWorkspace() as workspace:
                        task = next((item for item in workspace.list_task_details() if item[0] == task_id), None)
                        if task is None:
                            self.append("Sherlock AI", f"Задача #{task_id} не найдена.", "assistant")
                        else:
                            approved = messagebox.askyesno(
                                "Изменить длительность?",
                                f"Задача #{task_id}: {task[1]}\nОценка: {minutes} мин.\n\nСохранить?",
                                parent=self.root,
                            )
                            if may_execute("update_task", confirmed=approved):
                                workspace.update_task_estimate(task_id, minutes)
                                self.append("Sherlock AI", f"Длительность задачи #{task_id}: ~{minutes} мин.", "assistant")
                            else:
                                self.append("Sherlock AI", "Оценка длительности не изменена.", "assistant")
                    if self.workspace_panel is not None:
                        self.workspace_panel.refresh()
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось сохранить длительность задачи.", "assistant")
                return
            if command[0] == "defer_nonurgent":
                try:
                    today = date.today().isoformat()
                    with OfflineWorkspace() as workspace:
                        candidates = workspace.nonurgent_tasks_due(today)
                    if not candidates:
                        self.append("Sherlock AI",
                                    "Нет незавершённых несрочных задач со сроком на сегодня. "
                                    "Просроченные задачи и задачи без срока не затронуты.",
                                    "assistant")
                        return
                    total_candidates = len(candidates)
                    candidates = candidates[:10]  # Every affected task must fit in the confirmation dialog.
                    next_day = (date.today() + timedelta(days=1)).isoformat()
                    preview = "\n".join(f"#{task_id} · {title[:100]}" for task_id, title in candidates)
                    approved = messagebox.askyesno(
                        "Перенести задачи?",
                        f"Перенести {len(candidates)} несрочных задач с {today} на {next_day}?\n\n" +
                        preview + (f"\n\nПоказаны первые 10 из {total_candidates}. Остальные можно перенести повторной командой." if total_candidates > 10 else "") +
                        "\n\nВысокоприоритетные и просроченные задачи останутся без изменений.",
                        parent=self.root,
                    )
                    if not may_execute("update_task", confirmed=approved):
                        self.append("Sherlock AI", "Перенос отменён, задачи не изменены.", "assistant")
                        return
                    with OfflineWorkspace() as workspace:
                        count = workspace.defer_nonurgent_tasks(today, [item[0] for item in candidates])
                    self.append("Sherlock AI",
                                f"Перенесено задач: {count}. Новый срок: {next_day}.",
                                "assistant")
                except (OSError, sqlite3.Error, ValueError) as exc:
                    self.append("Sherlock AI", "Не удалось перенести задачи: " + str(exc), "assistant")
                return
            if command[0] == "plan_remaining":
                if not may_execute("list_tasks"):
                    self.append("Sherlock AI", "Просмотр задач запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        tasks = workspace.list_task_estimates()
                    plan = build_remaining_day_schedule(tasks, command[1])
                    self.pending_schedule = (date.today().isoformat(), plan)
                    self.append("Планировщик", plan, "assistant")
                except (OSError, sqlite3.Error, ValueError) as exc:
                    self.append("Sherlock AI", "Не удалось распланировать оставшееся время: " + str(exc), "assistant")
                return
            if command[0] == "delay_schedule":
                if not may_execute("view_plan"):
                    self.append("Sherlock AI", "Просмотр расписания запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        saved = workspace.latest_plan()
                    if not saved:
                        self.append("Sherlock AI", "Сначала составь и сохрани расписание на сегодня.", "assistant")
                        return
                    preview = shift_saved_schedule(saved[2], saved[1], command[1])
                    self.pending_schedule = (date.today().isoformat(), preview)
                    self.append("Планировщик", preview, "assistant")
                except (OSError, sqlite3.Error, ValueError) as exc:
                    self.append("Sherlock AI", "Не удалось пересчитать расписание: " + str(exc), "assistant")
                return
            if command[0] == "current_schedule_slot":
                if not may_execute("view_plan"):
                    self.append("Sherlock AI", "Просмотр расписания запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        saved = workspace.latest_plan()
                    result = (describe_current_slot(saved[2], saved[1]) if saved else
                              "Сохранённых расписаний пока нет. Сначала составь и сохрани план на сегодня.")
                    self.append("Планировщик", result, "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось определить текущую задачу.", "assistant")
                return
            if command[0] == "list_saved_schedules":
                if not may_execute("view_plan"):
                    self.append("Sherlock AI", "Просмотр планов запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        plans = workspace.list_saved_plans()
                    history = ("Последние сохранённые расписания:\n" +
                               "\n".join(f"#{plan_id} · {plan_date} · сохранено {created_at}"
                                         for plan_id, plan_date, created_at in plans) +
                               "\n\nЧтобы открыть, напиши: «Открой расписание #N».")
                    self.append("История расписаний",
                                history if plans else "Пока нет сохранённых расписаний.",
                                "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось загрузить историю расписаний.", "assistant")
                return
            if command[0] == "open_saved_schedule":
                if not may_execute("view_plan"):
                    self.append("Sherlock AI", "Просмотр плана запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        saved = workspace.get_saved_plan(command[1])
                    self.append("Сохранённый план",
                                saved[2] if saved else f"Расписание #{command[1]} не найдено.",
                                "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось открыть расписание.", "assistant")
                return
            if command[0] == "show_saved_schedule":
                if not may_execute("view_plan"):
                    self.append("Sherlock AI", "Просмотр плана запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        saved = workspace.latest_plan()
                    self.append("Сохранённый план",
                                saved[2] if saved else "Пока нет сохранённого расписания.",
                                "assistant")
                except (OSError, sqlite3.Error):
                    self.append("Sherlock AI", "Не удалось открыть сохранённый план.", "assistant")
                return
            if command[0] == "save_schedule":
                if self.pending_schedule is None:
                    self.append("Sherlock AI", "Сначала составь расписание с указанием времени начала.", "assistant")
                    return
                plan_date, content = self.pending_schedule
                approved = messagebox.askyesno(
                    "Сохранить расписание?",
                    "Сохранить последнее предложенное расписание в локальной базе?\n\n" + content[:500],
                    parent=self.root,
                )
                if not may_execute("save_plan", confirmed=approved):
                    self.append("Sherlock AI", "Расписание не сохранено.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        plan_id = workspace.save_plan(plan_date, content)
                    self.pending_schedule = None
                    self.append("Sherlock AI",
                                f"Расписание сохранено локально (план #{plan_id}). Его можно открыть командой «Покажи сохранённое расписание».",
                                "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось сохранить расписание.", "assistant")
                return
            if command[0] == "timed_schedule":
                if not may_execute("list_tasks"):
                    self.append("Sherlock AI", "Просмотр задач запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        plan = build_timed_schedule(workspace.list_task_estimates(), *command[1])
                    self.pending_schedule = (date.today().isoformat(), plan)
                    self.append("Планировщик", plan, "assistant")
                except (OSError, sqlite3.Error, ValueError) as exc:
                    self.append("Sherlock AI", "Не удалось составить расписание: " + str(exc), "assistant")
                return
            if command[0] == "plan_budget":
                if not may_execute("list_tasks"):
                    self.append("Sherlock AI", "Просмотр задач запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        plan = build_time_budget_plan(workspace.list_task_estimates(), command[1])
                    self.append("Планировщик", plan, "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось составить план по времени.", "assistant")
                return
            if command[0] in ("plan_today", "plan_week", "plan_day_parts"):
                if not may_execute("list_tasks"):
                    self.append("Sherlock AI", "Просмотр задач запрещён настройками безопасности.", "assistant")
                    return
                try:
                    with OfflineWorkspace() as workspace:
                        entries = workspace.list_task_details()
                        plan = (build_day_parts(entries) if command[0] == "plan_day_parts" else
                                build_task_plan(entries, period="today" if command[0] == "plan_today" else "week"))
                    self.append("Планировщик", plan, "assistant")
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось составить план задач.", "assistant")
                return
            if command[0] in ("create_task", "list_tasks", "tasks_today", "tasks_overdue", "complete_task", "set_task_due", "set_task_priority"):
                try:
                    with OfflineWorkspace() as workspace:
                        if command[0] in ("list_tasks", "tasks_today", "tasks_overdue"):
                            if may_execute("list_tasks"):
                                entries = workspace.list_task_details()
                                labels = {"list_tasks": "Твои задачи",
                                          "tasks_today": "Задачи на сегодня",
                                          "tasks_overdue": "Просроченные задачи"}
                                if command[0] != "list_tasks":
                                    category = "today" if command[0] == "tasks_today" else "overdue"
                                    entries = filtered_tasks(entries, category)
                                lines = [describe_task(item) for item in entries[:30]]
                                self.append("Sherlock AI", labels[command[0]] + ":\n" +
                                            ("\n".join(lines) if lines else "Задач нет."),
                                            "assistant")
                        elif command[0] == "create_task":
                            confirmed = messagebox.askyesno(
                                "Добавить задачу?",
                                "Сохранить задачу в локальной базе?\n\n" + command[1][:300],
                                parent=self.root,
                            )
                            if may_execute("create_task", confirmed=confirmed):
                                task_id = workspace.add_task(command[1])
                                self.append("Sherlock AI", "Создана задача #{}: {}".format(task_id, command[1]), "assistant")
                            else:
                                self.append("Sherlock AI", "Задача не создана.", "assistant")
                        elif command[0] in ("set_task_due", "set_task_priority"):
                            task_id, value = command[1]
                            target = next((item for item in workspace.list_task_details() if item[0] == task_id), None)
                            if target is None:
                                self.append("Sherlock AI", "Задача #{} не найдена.".format(task_id), "assistant")
                            else:
                                priority = target[3]
                                due_date = target[4]
                                if command[0] == "set_task_due":
                                    due_date = value
                                    label = "Срок: " + value
                                else:
                                    priority = {"низкий": "low", "обычный": "normal", "высокий": "high"}[value]
                                    label = "Приоритет: " + value
                                # Validate the date and priority before requesting user consent.
                                workspace._validate_task_meta(priority, due_date)
                                approved = messagebox.askyesno(
                                    "Изменить задачу?",
                                    "Задача #{}: {}\n\n{}\n\nПрименить изменение?".format(
                                        task_id, target[1], label),
                                    parent=self.root,
                                )
                                if may_execute("update_task", confirmed=approved):
                                    workspace.update_task_details(task_id, priority, due_date)
                                    self.append("Sherlock AI", "Задача #{} обновлена: {}".format(task_id, label), "assistant")
                                else:
                                    self.append("Sherlock AI", "Задача не изменена.", "assistant")
                        else:
                            target = next((item for item in workspace.list_tasks() if item[0] == command[1]), None)
                            if target is None:
                                self.append("Sherlock AI", "Задача #{} не найдена.".format(command[1]), "assistant")
                            elif target[2]:
                                self.append("Sherlock AI", "Задача #{} уже выполнена.".format(command[1]), "assistant")
                            else:
                                confirmed = messagebox.askyesno(
                                    "Завершить задачу?",
                                    "Отметить выполненной задачу #{}?\n\n{}".format(target[0], target[1]),
                                    parent=self.root,
                                )
                                if may_execute("complete_task", confirmed=confirmed) and workspace.complete_task(target[0]):
                                    self.append("Sherlock AI", "Задача #{} выполнена.".format(target[0]), "assistant")
                                else:
                                    self.append("Sherlock AI", "Задача не изменена.", "assistant")
                    if self.workspace_panel is not None:
                        self.workspace_panel.refresh()
                except (OSError, sqlite3.Error, ValueError):
                    self.append("Sherlock AI", "Не удалось выполнить действие с задачами.", "assistant")
                return
            if not self.search_folder:
                self.append("Sherlock AI", "Сначала выбери папку в разделе «Инструменты» → «Папка…».", "assistant")
                self.show_page("tools")
                return
            if self.searching:
                self.append("Sherlock AI", "Поиск уже выполняется. Дождись его завершения.", "assistant")
                return
            if command[0] == "recent" and may_execute("recent_files"):
                self.start_recent_files(command_question=question)
            elif command[0] == "search" and may_execute("search_files"):
                self.search_query.delete(0, "end")
                self.search_query.insert(0, command[1])
                self.start_folder_search(command_question=question, command_query=command[1])
            else:
                self.append("Sherlock AI", "Действие запрещено настройками безопасности.", "assistant")
            return
        model = self.model_choice.get()
        if model != "Авто" and model not in self.model_picker["values"]:
            self.status.configure(text="Выбранная модель не установлена на этом компьютере.")
            return
        self.input.delete("1.0", "end")
        self.append("Ты", question, "user")
        if question.lower().lstrip().startswith("запомни"):
            fact = proposed_memory(question)
            if fact is None:
                self.append("Sherlock AI",
                            "Не сохранил. Напиши «Запомни, что ...» без паролей, кодов и других секретов (до 500 символов).",
                            "assistant")
                return
            if not messagebox.askyesno("Сохранить в память?",
                                        f"Сохранить этот факт только на компьютере?\n\n{fact}",
                                        parent=self.root):
                self.append("Sherlock AI", "Хорошо, ничего не сохраняю.", "assistant")
                return
            try:
                with OfflineWorkspace() as workspace:
                    workspace.add_memory(fact)
                if self.workspace_panel is not None:
                    self.workspace_panel.refresh()
                self.append("Sherlock AI", "Сохранил в память. Это можно изменить или удалить в разделе «Память».",
                            "assistant")
            except (OSError, sqlite3.Error, ValueError):
                self.append("Sherlock AI", "Не удалось сохранить факт в локальной памяти.", "assistant")
            return
        history = self.session.snapshot()
        try:
            with OfflineWorkspace() as workspace:
                facts = [content for _id, content in workspace.list_memories()[:50]]
        except (OSError, sqlite3.Error):
            facts = []
        tone = TONES[self.tone.get()]
        self.busy = True
        self.stream_has_chunks = False
        self.append_stream_start()
        self.started_at = time.monotonic()
        self.activity.configure(text="Sherlock AI формирует ответ · первый запуск модели может занять время", fg=ACCENT)
        self.send_button.configure(state="disabled")
        self.status.configure(text="Sherlock AI думает…")
        threading.Thread(target=self.generate, args=(question, history, tone, None if model == "Авто" else model, self.performance.get(), facts),
                         daemon=True).start()

    def generate(self, question: str, history: list, tone: str, model: str | None, performance: str, facts: list[str]) -> None:
        try:
            answer = asyncio.run(ask_local_ai(question, history=history, tone=tone, model=model, facts=facts,
                                              on_chunk=lambda chunk: self.events.put(("chunk", chunk)),
                                              performance=performance))
        except Exception:
            answer = "Не удалось получить ответ. Проверь подключение к Ollama."
        self.events.put(("answer", question, answer))

    def poll(self) -> None:
        if self.closed:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "chunk":
                self.stream_has_chunks = True
                self.append_stream_chunk(event[1])
            elif event[0] == "model":
                self.model_label.configure(text=event[1])
                model_ready = len(event) > 2 and bool(event[2])
                if model_ready:
                    active_model = self.model_choice.get()
                    active_model = active_model if active_model != "Авто" else event[1].removeprefix("Модель: ")
                    self.chat_model_status.configure(
                        text="● Локальная модель готова · " + active_model,
                        fg="#98e7c9",
                    )
                else:
                    self.chat_model_status.configure(
                        text="● Ollama не готова · открой настройки",
                        fg="#f6b7a2",
                    )
                if len(event) > 2:
                    models = ["Авто"] + event[2]
                    self.model_picker["values"] = models
                    if self.model_choice.get() not in models:
                        self.model_choice.set("Авто")
                        self.save_model_choice()
            elif event[0] == "recent_files":
                self.display_recent_files(event[1], event[2], event[3])
            elif event[0] == "folder_search":
                self.display_folder_search(event[1], event[2], event[3])
            elif event[0] == "answer":
                _, question, answer = event
                if not self.stream_has_chunks or answer.startswith(("Ошибка генерации", "Локальная модель недоступна", "Не удалось получить ответ")):
                    if self.stream_has_chunks:
                        self.append_stream_chunk("\n[Ответ прервался] ")
                    self.append_stream_chunk(answer)
                self.append_stream_chunk("\n\n")
                if self.session.record(question, answer):
                    self.full_history.extend(({"role": "user", "content": question},
                                              {"role": "assistant", "content": answer}))
                    self.full_history = self.full_history[-200:]
                self.busy = False
                self.activity.configure(text="Готов к общению", fg="#98e7c9")
                self.send_button.configure(state="normal")
                self.status.configure(text="Ctrl+Enter — отправить · История только в памяти окна")
        if self.busy:
            elapsed = int(time.monotonic() - self.started_at)
            self.activity.configure(text=f"Sherlock AI думает… {elapsed} с · ожидаем ответ локальной модели")
        self.root.after(100, self.poll)

    def save_conversation(self) -> None:
        if self.busy:
            self.status.configure(text="Дождись завершения ответа перед сохранением.")
            return
        if not self.full_history:
            self.status.configure(text="Пока нет завершённых сообщений для сохранения.")
            return
        title = next((m["content"][:70] for m in self.full_history if m["role"] == "user"), "Диалог")
        try:
            with OfflineWorkspace() as workspace:
                workspace.save_conversation(title, self.full_history)
            if self.workspace_panel is not None:
                self.workspace_panel.refresh()
            self.status.configure(text="Диалог сохранён локально · открыть можно в разделе «История»")
        except (OSError, sqlite3.Error, ValueError):
            self.status.configure(text="Не удалось сохранить диалог.")

    def open_conversation(self, messages: list[dict[str, str]]) -> None:
        if self.busy:
            self.status.configure(text="Дождись ответа перед открытием другого диалога.")
            return
        self.full_history = [dict(item) for item in messages]
        self.session.history = [dict(item) for item in messages[-12:]]
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        for item in messages:
            self.append("Ты" if item["role"] == "user" else "Sherlock AI",
                        item["content"], item["role"])
        self.show_page("chat")
        self.status.configure(text="Сохранённый диалог открыт · изменения не сохраняются автоматически")

    def clear(self) -> None:
        if self.busy:
            self.status.configure(text="Дождись ответа перед очисткой.")
            return
        self.session.clear()
        self.full_history.clear()
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self.append("Sherlock AI", "Начнём с чистого листа! ✨", "assistant")

    def close(self) -> None:
        if self.busy and not messagebox.askyesno(
            "Ответ ещё формируется",
            "Локальная модель ещё отвечает. Закрыть Sherlock AI и прервать ответ?",
            parent=self.root,
        ):
            return
        unsent = self.input.get("1.0", "end-1c").strip()
        if unsent and not messagebox.askyesno(
            "Несохранённое сообщение",
            "В поле ввода остался текст, который ты не отправил. Закрыть приложение?",
            parent=self.root,
        ):
            return
        if self.workspace_panel is not None and not self.workspace_panel.close():
            return
        self.closed = True
        self.root.destroy()



def run_self_test() -> int:
    """Smoke-test bundled Tk/Tcl and isolated SQLite without network or user data."""
    from tempfile import TemporaryDirectory

    # Loading Tcl verifies that the frozen build contains its Tcl runtime.
    interpreter = tk.Tcl()
    interpreter.eval("set sherlock_smoke_test ready")
    if interpreter.eval("set sherlock_smoke_test") != "ready":
        raise RuntimeError("Tcl runtime is unavailable.")

    with TemporaryDirectory(prefix="sherlock-smoke-") as folder:
        path = Path(folder) / "workspace.sqlite3"
        with OfflineWorkspace(path) as workspace:
            task_id = workspace.add_task("Проверка сборки")
            note_id = workspace.add_note("Локальное хранилище работает")
            if workspace.list_tasks() != [(task_id, "Проверка сборки", 0)]:
                raise RuntimeError("Could not write a temporary task.")
            if not workspace.save_task_fields(
                task_id, "Проверка редактирования", "high", "2026-11-18", 25,
            ):
                raise RuntimeError("Could not update a temporary task.")
            row = workspace.list_task_estimates()[0]
            if row[1:] != ("Проверка редактирования", 0, "high", "2026-11-18", 25):
                raise RuntimeError("Could not verify updated task fields.")
        with OfflineWorkspace(path) as workspace:
            if workspace.list_notes() != [(note_id, "Локальное хранилище работает")]:
                raise RuntimeError("Could not reopen the temporary database.")
    return 0


def run_gui_self_test() -> int:
    """Exercise real Tk widgets with only temporary local data."""
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    with TemporaryDirectory(prefix="sherlock-gui-") as folder:
        with patch.dict(os.environ, {"LOCALAPPDATA": folder}), (
            patch(__name__ + ".selected_model", return_value="test-model")
        ), patch(__name__ + ".installed_models", return_value=["test-model"]):
            root = tk.Tk()
            root.withdraw()
            try:
                app = SherlockDesktop(root)
                for page in ("chat", "day", "tasks", "notes", "memory", "history", "settings"):
                    app.show_page(page)
                    root.update_idletasks()
                app.update_navigation_layout(800)
                if int(app.navigation.cget("width")) != 56:
                    raise RuntimeError("Compact navigation did not activate.")
                app.update_navigation_layout(1200)
                if int(app.navigation.cget("width")) != 164:
                    raise RuntimeError("Expanded navigation did not activate.")
                app.show_page("chat")
                app.close()
            finally:
                if root.winfo_exists():
                    root.destroy()
    return 0


def main() -> None:
    root = tk.Tk()
    SherlockDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(run_self_test())
    if sys.argv[1:] == ["--gui-self-test"]:
        raise SystemExit(run_gui_self_test())
    main()
