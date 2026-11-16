"""Sherlock AI desktop chat for Windows. No Telegram configuration required."""

import asyncio
import json
import os
from pathlib import Path
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from offline_workspace_app import WorkspaceWindow
from offline_workspace import OfflineWorkspace
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
        for label, target in (("● Общение", "chat"), ("✓ Задачи", "tasks"), ("✎ Заметки", "notes"), ("◇ Память", "memory")):
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
        settings = tk.Frame(self.chat_page, bg=BACKGROUND, padx=24)
        settings.pack(fill="x")
        self.model_label = tk.Label(settings, text="Модель: проверяется…",
                                    bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 10))
        self.model_label.pack(side="left")
        self.model_picker = ttk.Combobox(settings, textvariable=self.model_choice, width=16, state="readonly")
        self.model_picker.pack(side="left", padx=(9, 0))
        self.model_picker.bind("<<ComboboxSelected>>", self.save_model_choice)
        self.tone = tk.StringVar(value="Тёплый")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Sherlock.TCombobox", fieldbackground=INPUT, background=INPUT,
                        foreground=TEXT, arrowcolor=TEXT)
        style.map("Sherlock.TCombobox", fieldbackground=[("readonly", INPUT)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", INPUT)],
                  selectforeground=[("readonly", TEXT)])

        performance_bar = tk.Frame(self.chat_page, bg=BACKGROUND, padx=24)
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
        tk.Button(footer, text="Очистить диалог", command=self.clear,
                  bg=BACKGROUND, fg=MUTED, activebackground=SURFACE,
                  relief="flat").pack(side="right")
        self.append("Sherlock AI", "Привет! ❤️ Напиши мне что-нибудь. Для работы нужна установленная Ollama.", "assistant")
        self.root.after(100, self.poll)
        threading.Thread(target=self.check_model, daemon=True).start()
        self.input.focus_set()

    def show_page(self, page: str) -> None:
        for name, button in self.nav_buttons.items():
            button.configure(bg=INPUT if name == page else "#10182a")
        if page == "chat":
            if self.workspace_panel is not None:
                self.workspace_panel.window.pack_forget()
            self.chat_page.pack(fill="both", expand=True)
            return
        self.chat_page.pack_forget()
        if self.workspace_panel is None:
            workspace_frame = tk.Frame(self.content_area, bg=BACKGROUND)
            self.workspace_panel = WorkspaceWindow(workspace_frame, embedded=True)
        self.workspace_panel.select_tab({"tasks": 0, "notes": 1, "memory": 2}.get(page, 0))
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

    def load_performance(self) -> str:
        try:
            value = json.loads(self.model_config_path.read_text(encoding="utf-8")).get("performance", "Быстро")
            return value if value in ("Быстро", "Баланс", "Качество") else "Быстро"
        except (OSError, ValueError, TypeError):
            return "Быстро"

    def save_model_choice(self, event=None) -> None:
        try:
            self.model_config_path.parent.mkdir(parents=True, exist_ok=True)
            self.model_config_path.write_text(json.dumps({"model": self.model_choice.get(), "performance": self.performance.get()}, ensure_ascii=False), encoding="utf-8")
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
        model = self.model_choice.get()
        if model != "Авто" and model not in self.model_picker["values"]:
            self.status.configure(text="Выбранная модель не установлена на этом компьютере.")
            return
        self.input.delete("1.0", "end")
        self.append("Ты", question, "user")
        history = self.session.snapshot()
        try:
            with OfflineWorkspace() as workspace:
                facts = [content for _id, content in workspace.list_memories()[:50]]
        except OSError:
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
            elif event[0] == "answer":
                _, question, answer = event
                if not self.stream_has_chunks or answer.startswith(("Ошибка генерации", "Локальная модель недоступна", "Не удалось получить ответ")):
                    if self.stream_has_chunks:
                        self.append_stream_chunk("\n[Ответ прервался] ")
                    self.append_stream_chunk(answer)
                self.append_stream_chunk("\n\n")
                self.session.record(question, answer)
                self.busy = False
                self.activity.configure(text="Готов к общению", fg="#98e7c9")
                self.send_button.configure(state="normal")
                self.status.configure(text="Ctrl+Enter — отправить · История только в памяти окна")
        if self.busy:
            elapsed = int(time.monotonic() - self.started_at)
            self.activity.configure(text=f"Sherlock AI думает… {elapsed} с · ожидаем ответ локальной модели")
        self.root.after(100, self.poll)

    def clear(self) -> None:
        if self.busy:
            self.status.configure(text="Дождись ответа перед очисткой.")
            return
        self.session.clear()
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
