"""Sherlock AI desktop chat for Windows. No Telegram configuration required."""

import asyncio
import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from offline_workspace_app import open_workspace
from desktop_logic import ConversationSession
from local_ai import ask_local_ai, selected_model


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
        root.title("Sherlock AI — личный помощник")
        root.geometry("860x650")
        root.minsize(560, 460)
        root.configure(bg=BACKGROUND)
        root.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(root, bg=BACKGROUND, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="✦ Sherlock AI", font=("Segoe UI", 22, "bold"),
                 fg=TEXT, bg=BACKGROUND).pack(anchor="w")
        tk.Label(header, text="Твой локальный помощник · приватный разговор",
                 font=("Segoe UI", 10), fg=MUTED, bg=BACKGROUND).pack(anchor="w")

        settings = tk.Frame(root, bg=BACKGROUND, padx=24)
        settings.pack(fill="x")
        self.model_label = tk.Label(settings, text="Модель: проверяется…",
                                    bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 10))
        self.model_label.pack(side="left")
        self.tone = tk.StringVar(value="Тёплый")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Sherlock.TCombobox", fieldbackground=INPUT, background=INPUT,
                        foreground=TEXT, arrowcolor=TEXT)
        picker = ttk.Combobox(settings, textvariable=self.tone, state="readonly",
                              values=list(TONES), width=13, style="Sherlock.TCombobox")
        picker.pack(side="right")
        tk.Label(settings, text="Стиль общения:", bg=BACKGROUND, fg=MUTED).pack(
            side="right", padx=(0, 8))

        self.chat = ScrolledText(root, wrap="word", bg=SURFACE, fg=TEXT,
                                 insertbackground=TEXT, font=("Segoe UI", 11),
                                 relief="flat", padx=18, pady=16, state="disabled",
                                 spacing2=5)
        self.chat.pack(fill="both", expand=True, padx=24, pady=(14, 12))
        self.chat.tag_configure("user", foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("assistant", foreground="#98e7c9", font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("system", foreground=MUTED)

        composer = tk.Frame(root, bg=BACKGROUND, padx=24)
        composer.pack(fill="x")
        self.input = tk.Text(composer, height=3, bg=INPUT, fg=TEXT,
                             insertbackground=TEXT, wrap="word", relief="flat",
                             font=("Segoe UI", 11), padx=12, pady=10)
        self.input.pack(side="left", fill="both", expand=True)
        self.input.bind("<Control-Return>", self.send_event)
        self.send_button = tk.Button(composer, text="Отправить ↗", command=self.send,
                                     bg=ACCENT, fg=BACKGROUND, activebackground="#a8b6ff",
                                     relief="flat", padx=16, font=("Segoe UI", 10, "bold"))
        self.send_button.pack(side="right", padx=(10, 0), fill="y")

        footer = tk.Frame(root, bg=BACKGROUND, padx=24, pady=12)
        footer.pack(fill="x")
        self.status = tk.Label(footer, text="Ctrl+Enter — отправить · История только в памяти окна",
                               bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9))
        self.status.pack(side="left")
        tk.Button(footer, text="Задачи и заметки", command=lambda: open_workspace(self.root),
                  bg=SURFACE, fg=TEXT, activebackground=INPUT,
                  relief="flat", padx=12).pack(side="right", padx=(10, 0))
        tk.Button(footer, text="Очистить диалог", command=self.clear,
                  bg=BACKGROUND, fg=MUTED, activebackground=SURFACE,
                  relief="flat").pack(side="right")
        self.append("Sherlock AI", "Привет! ❤️ Напиши мне что-нибудь. Для работы нужна установленная Ollama.", "assistant")
        self.root.after(100, self.poll)
        threading.Thread(target=self.check_model, daemon=True).start()
        self.input.focus_set()

    def append(self, name: str, message: str, kind: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", name + "\n", kind)
        self.chat.insert("end", message + "\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def check_model(self) -> None:
        try:
            result = selected_model()
            self.events.put(("model", "Модель: " + result))
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
        self.input.delete("1.0", "end")
        self.append("Ты", question, "user")
        history = self.session.snapshot()
        tone = TONES[self.tone.get()]
        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.configure(text="Sherlock AI думает…")
        threading.Thread(target=self.generate, args=(question, history, tone),
                         daemon=True).start()

    def generate(self, question: str, history: list, tone: str) -> None:
        try:
            answer = asyncio.run(ask_local_ai(question, history=history, tone=tone))
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
            if event[0] == "model":
                self.model_label.configure(text=event[1])
            elif event[0] == "answer":
                _, question, answer = event
                self.append("Sherlock AI", answer, "assistant")
                self.session.record(question, answer)
                self.busy = False
                self.send_button.configure(state="normal")
                self.status.configure(text="Ctrl+Enter — отправить · История только в памяти окна")
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
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    SherlockDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
