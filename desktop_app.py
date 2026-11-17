"""Sherlock AI desktop chat for Windows. No Telegram configuration required."""

import asyncio
import json
import os
from pathlib import Path
import time
import queue
import sqlite3
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
        self.model_config_path = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".sherlock_ai")) / "SherlockAI" / "desktop_settings.json"
        self.model_choice = tk.StringVar(value=self.load_model_choice())
        self.performance = tk.StringVar(value=self.load_performance())
        root.title("Sherlock AI — личный помощник")
        root.geometry("920x640")
        root.minsize(620, 480)
        root.configure(bg=BACKGROUND)
        root.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(root, bg=BACKGROUND, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="✦ Sherlock AI", font=("Segoe UI", 22, "bold"),
                 fg=TEXT, bg=BACKGROUND).pack(anchor="w")
        tk.Label(header, text="Твой локальный помощник · приватный разговор",
                 font=("Segoe UI", 10), fg=MUTED, bg=BACKGROUND).pack(anchor="w")
        self.activity = tk.Label(header, text="Готов к общению · Telegram не требуется",
                                 font=("Segoe UI", 9), fg="#98e7c9", bg=BACKGROUND)
        self.activity.pack(anchor="w", pady=(7, 0))

        body = tk.Frame(root, bg=BACKGROUND)
        body.pack(fill="both", expand=True)
        navigation = tk.Frame(body, bg="#10182a", width=154, padx=10, pady=14)
        navigation.pack(side="left", fill="y")
        navigation.pack_propagate(False)
        tk.Label(navigation, text="РАЗДЕЛЫ", bg="#10182a", fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(2, 12))
        self.nav_buttons = {}
        for label, target in (("● Общение", "chat"), ("✓ Задачи", "tasks"), ("✎ Заметки", "notes"), ("◇ Память", "memory"), ("▤ История", "history"), ("⌕ Инструменты", "tools"), ("⚙ Настройки", "settings")):
            button = tk.Button(navigation, text=label, command=lambda page=target: self.show_page(page),
                               bg=INPUT if target == "chat" else "#10182a", fg=TEXT,
                               activebackground=INPUT, activeforeground=TEXT,
                               relief="flat", padx=12, pady=11, anchor="w")
            button.pack(fill="x", pady=(0, 6))
            self.nav_buttons[target] = button
        tk.Label(navigation, text="Локально · приватно", bg="#10182a", fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="bottom", pady=10)
        self.content_area = tk.Frame(body, bg=BACKGROUND)
        self.content_area.pack(side="left", fill="both", expand=True)
        self.chat_page = tk.Frame(self.content_area, bg=BACKGROUND)
        self.chat_page.pack(fill="both", expand=True)
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
        tk.Label(self.settings_page, text="Настройки помощника", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=24, pady=(26, 8))
        tk.Label(self.settings_page, text="Выбор модели и производительности действует только на этом компьютере.",
                 bg=BACKGROUND, fg=MUTED, wraplength=480, justify="left").pack(anchor="w", padx=24, pady=(0, 22))
        settings = tk.Frame(self.settings_page, bg=BACKGROUND, padx=24)
        settings.pack(fill="x")
        self.model_label = tk.Label(settings, text="Модель: проверяется…",
                                    bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 10))
        self.model_label.pack(side="left")
        self.model_picker = ttk.Combobox(settings, textvariable=self.model_choice, width=16, state="readonly")
        self.model_picker.pack(side="left", padx=(9, 0))
        self.model_picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        self.tone = tk.StringVar(value=self.load_tone())
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Sherlock.TCombobox", fieldbackground=INPUT, background=INPUT,
                        foreground=TEXT, arrowcolor=TEXT)
        style.map("Sherlock.TCombobox", fieldbackground=[("readonly", INPUT)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", INPUT)],
                  selectforeground=[("readonly", TEXT)])

        performance_bar = tk.Frame(self.settings_page, bg=BACKGROUND, padx=24)
        performance_bar.pack(fill="x", pady=(9, 0))
        tk.Label(performance_bar, text="Скорость:", bg=BACKGROUND, fg=MUTED).pack(side="left")
        self.performance_picker = ttk.Combobox(performance_bar, textvariable=self.performance,
                                                values=["Быстро", "Баланс", "Качество"],
                                                width=12, state="readonly", style="Sherlock.TCombobox")
        self.performance_picker.pack(side="left", padx=(8, 12))
        self.performance_picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        tk.Label(performance_bar, text="Стиль:", bg=BACKGROUND, fg=MUTED).pack(side="left")
        picker = ttk.Combobox(performance_bar, textvariable=self.tone, state="readonly",
                              values=list(TONES), width=11, style="Sherlock.TCombobox")
        picker.pack(side="left", padx=(8, 0))
        picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        tk.Label(self.settings_page,
                 text="Быстро: краткие ответы · Баланс: повседневная работа · Качество: больше контекста",
                 bg=BACKGROUND, fg=MUTED, wraplength=480, justify="left").pack(anchor="w", padx=24, pady=(22, 0))

        self.chat = ScrolledText(self.chat_page, height=8, wrap="word", bg=SURFACE, fg=TEXT,
                                 insertbackground=TEXT, font=("Segoe UI", 11),
                                 relief="flat", padx=18, pady=16, state="disabled",
                                 spacing2=5)
        self.chat.pack(fill="both", expand=True, padx=24, pady=(14, 12))
        self.chat.tag_configure("user", foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("assistant", foreground="#98e7c9", font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("system", foreground=MUTED)

        composer = tk.Frame(self.chat_page, bg=BACKGROUND, padx=24)
        composer.pack(fill="x")
        self.input = tk.Text(composer, height=2, bg=INPUT, fg=TEXT,
                             insertbackground=TEXT, wrap="word", relief="flat",
                             font=("Segoe UI", 11), padx=12, pady=10)
        self.input.pack(side="left", fill="both", expand=True)
        self.input.bind("<Control-Return>", self.send_event)
        self.send_button = tk.Button(composer, text="Отправить ↗", command=self.send,
                                     bg=ACCENT, fg=BACKGROUND, activebackground="#a8b6ff",
                                     relief="flat", padx=16, font=("Segoe UI", 10, "bold"))
        self.send_button.pack(side="right", padx=(10, 0), fill="y")

        footer = tk.Frame(self.chat_page, bg=BACKGROUND, padx=24, pady=12)
        footer.pack(fill="x")
        self.status = tk.Label(footer, text="Ctrl+Enter — отправить · История только в памяти окна",
                               bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9))
        self.status.pack(side="left")
        tk.Button(footer, text="Сохранить диалог", command=self.save_conversation,
                  bg=SURFACE, fg=TEXT, activebackground=INPUT,
                  relief="flat", padx=10).pack(side="right", padx=(0, 8))
        tk.Button(footer, text="Очистить диалог", command=self.clear,
                  bg=BACKGROUND, fg=MUTED, activebackground=SURFACE,
                  relief="flat").pack(side="right")
        self.append("Sherlock AI", "Привет! ❤️ Напиши мне что-нибудь. Для работы нужна установленная Ollama.", "assistant")
        self.root.after(100, self.poll)
        threading.Thread(target=self.check_model, daemon=True).start()
        self.input.focus_set()

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

    def show_page(self, page: str) -> None:
        for name, button in self.nav_buttons.items():
            button.configure(bg=INPUT if name == page else "#10182a")
        self.chat_page.pack_forget()
        self.settings_page.pack_forget()
        self.tools_page.pack_forget()
        if self.workspace_panel is not None:
            self.workspace_panel.window.pack_forget()
        if page == "chat":
            self.chat_page.pack(fill="both", expand=True)
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
                                                        "tone": self.tone.get()}, ensure_ascii=False), encoding="utf-8")
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
        self.closed = True
        if self.workspace_panel is not None:
            self.workspace_panel.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    SherlockDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
