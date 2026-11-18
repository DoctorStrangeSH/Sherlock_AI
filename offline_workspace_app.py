"""Simple offline tasks/notes window shared by standalone and desktop launch."""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from offline_workspace import OfflineWorkspace
from task_overview import task_bucket


BG = "#0b1020"
PANEL = "#151d32"
INPUT = "#1e2942"
FG = "#e7eaf2"
MUTED = "#98a6c4"
ACCENT = "#8b9eff"


def configure_dark_theme(window):
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure("Sherlock.TFrame", background=BG)
    style.configure("Sherlock.TNotebook", background=BG, borderwidth=0)
    style.configure("Sherlock.TNotebook.Tab", background=INPUT, foreground=FG,
                    padding=(18, 10), font=("Segoe UI", 10))
    style.map("Sherlock.TNotebook.Tab", background=[("selected", PANEL), ("active", PANEL)],
              foreground=[("selected", ACCENT)])
    style.configure("Sherlock.Treeview", background=PANEL, fieldbackground=PANEL,
                    foreground=FG, rowheight=32, borderwidth=0,
                    font=("Segoe UI", 10))
    style.map("Sherlock.Treeview", background=[("selected", "#35446e")],
              foreground=[("selected", "#ffffff")])
    style.configure("Sherlock.Treeview.Heading", background=INPUT, foreground=MUTED,
                    font=("Segoe UI", 10, "bold"), padding=9, relief="flat")
    style.map("Sherlock.Treeview.Heading", background=[("active", "#293757")])
    style.configure("Sherlock.TCombobox", fieldbackground=INPUT, background=INPUT,
                    foreground=FG, arrowcolor=FG, padding=6)
    style.map("Sherlock.TCombobox", fieldbackground=[("readonly", INPUT)],
              foreground=[("readonly", FG)])
    style.configure("Sherlock.TButton", background=INPUT, foreground=FG,
                    padding=(13, 9), borderwidth=0, font=("Segoe UI", 10))
    style.map("Sherlock.TButton", background=[("active", "#34456e"),
                                              ("pressed", "#34456e")],
              foreground=[("disabled", MUTED)])


class WorkspaceWindow:
    def __init__(self, window, initial_tab=0, embedded=False, on_open_conversation=None):
        self.window = window
        self.store = OfflineWorkspace()
        self.embedded = embedded
        self.on_open_conversation = on_open_conversation
        if not embedded:
            window.title("Sherlock AI — личное пространство")
            window.geometry("760x510")
            window.minsize(580, 400)
            window.protocol("WM_DELETE_WINDOW", self.close)
        window.configure(bg=BG)
        configure_dark_theme(window)
        tk.Label(window, text="Личное пространство", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", padx=20, pady=(18, 3))
        tk.Label(window, text="Хранятся только на этом компьютере · Telegram не требуется",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=20, pady=(0, 14))
        tabs = ttk.Notebook(window, style="Sherlock.TNotebook")
        self.tabs = tabs
        tabs.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.task_frame = ttk.Frame(tabs, style="Sherlock.TFrame")
        self.note_frame = ttk.Frame(tabs, style="Sherlock.TFrame")
        self.memory_frame = ttk.Frame(tabs, style="Sherlock.TFrame")
        self.history_frame = ttk.Frame(tabs, style="Sherlock.TFrame")
        tabs.add(self.task_frame, text="Задачи")
        tabs.add(self.note_frame, text="Заметки")
        tabs.add(self.memory_frame, text="Память")
        tabs.add(self.history_frame, text="История")
        tabs.select(initial_tab if initial_tab in (0, 1, 2, 3) else 0)
        self._controls(self.task_frame, (("Добавить задачу", self.add_task),
                                         ("Изменить срок/приоритет", self.edit_task_details),
                                         ("Длительность", self.edit_task_estimate),
                                         ("Выполнено", self.complete_task),
                                         ("Удалить", self.delete_task)))
        quick_task = tk.Frame(self.task_frame, bg=BG)
        quick_task.pack(fill="x", padx=10, pady=(0, 8))
        self.quick_task_title = tk.Entry(
            quick_task, bg=INPUT, fg=FG, insertbackground=FG, relief="flat",
            font=("Segoe UI", 10),
        )
        self.quick_task_title.pack(side="left", fill="x", expand=True, ipady=8)
        self.quick_task_title.bind("<Return>", self.add_quick_task)
        tk.Button(
            quick_task, text="+ Добавить", command=self.add_quick_task,
            bg=ACCENT, fg=BG, activebackground="#a8b6ff", relief="flat",
            padx=12, pady=7, font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=(8, 0))
        filters = tk.Frame(self.task_frame, bg=BG)
        filters.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(filters, text="Показывать:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.task_filter = tk.StringVar(value="Открытые")
        self.task_filter_picker = ttk.Combobox(
            filters, textvariable=self.task_filter, state="readonly",
            values=("Открытые", "Сегодня", "Просроченные", "Выполненные", "Все"),
            width=17, style="Sherlock.TCombobox",
        )
        self.task_filter_picker.pack(side="left")
        self.task_filter_picker.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        self.task_count_label = tk.Label(filters, text="", bg=BG, fg=MUTED,
                                         font=("Segoe UI", 9))
        self.task_count_label.pack(side="right")
        self.tasks_hint = tk.Label(
            self.task_frame, text="Создай первую задачу, чтобы начать планировать день.",
            bg=PANEL, fg=MUTED, anchor="w", padx=14, pady=12,
            font=("Segoe UI", 10),
        )
        self.tasks_hint.pack(fill="x", padx=10, pady=(0, 3))
        self.tasks = self._table(self.task_frame, ("Состояние", "Задача", "Приоритет", "Срок", "Оценка"), (115, 330, 100, 115, 85))
        self.tasks.tag_configure("overdue", foreground="#ffb0a5")
        self.tasks.tag_configure("today", foreground="#ffd38a")
        self.tasks.tag_configure("done", foreground="#98e7c9")
        self.notes = self._table(self.note_frame, ("Заметка",), (650,))
        self.memories = self._table(self.memory_frame, ("Сохранённый факт",), (650,))
        self.conversations = self._table(self.history_frame, ("Название", "Дата"), (450, 160))
        self._controls(self.note_frame, (("Новая", self.add_note),
                                         ("Изменить", self.edit_note),
                                         ("Сохранить", self.save_note),
                                         ("Удалить", self.delete_note)))
        self.editing_note_id = None
        self.note_hint = tk.Label(self.note_frame, text="Новая заметка · до 1000 символов",
                                  bg=BG, fg=MUTED, anchor="w")
        self.note_hint.pack(fill="x", padx=18, pady=(0, 5))
        self.note_editor = tk.Text(self.note_frame, height=5, bg=INPUT, fg=FG,
                                   insertbackground=FG, wrap="word", relief="flat",
                                   font=("Segoe UI", 10), padx=12, pady=9)
        self.note_editor.pack(fill="x", padx=18, pady=(0, 10))
        self.notes.bind("<Double-1>", lambda _event: self.edit_note())
        self._controls(self.memory_frame, (("Новый факт", self.new_memory),
                                          ("Изменить", self.edit_memory),
                                          ("Сохранить", self.save_memory),
                                          ("Удалить", self.delete_memory)))
        self.editing_memory_id = None
        self.memory_hint = tk.Label(self.memory_frame,
                                    text="Память сохраняется только по твоему решению · до 500 символов",
                                    bg=BG, fg=MUTED, anchor="w")
        self.memory_hint.pack(fill="x", padx=18, pady=(0, 5))
        self.memory_editor = tk.Text(self.memory_frame, height=4, bg=INPUT, fg=FG,
                                     insertbackground=FG, wrap="word", relief="flat",
                                     font=("Segoe UI", 10), padx=12, pady=9)
        self.memory_editor.pack(fill="x", padx=18, pady=(0, 10))
        self.memories.bind("<Double-1>", lambda _event: self.edit_memory())
        self._controls(self.history_frame, (("Открыть", self.open_conversation),
                                           ("Удалить", self.delete_conversation)))
        tk.Label(self.history_frame,
                 text="Сохраняются только диалоги, для которых ты нажал «Сохранить диалог».",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(0, 12))
        self.conversations.bind("<Double-1>", lambda _event: self.open_conversation())
        self.status = tk.Label(window, text="", bg=BG, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(anchor="w", padx=20, pady=(0, 9))
        self.refresh()

    @staticmethod
    def _table(parent, labels, widths):
        tree = ttk.Treeview(parent, columns=labels, show="headings", selectmode="browse",
                            style="Sherlock.Treeview")
        for label, width in zip(labels, widths):
            tree.heading(label, text=label)
            tree.column(label, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        return tree

    @staticmethod
    def _controls(parent, buttons):
        frame = ttk.Frame(parent, style="Sherlock.TFrame")
        frame.pack(fill="x", padx=10, pady=(8, 7))
        row = None
        for index, (text, command) in enumerate(buttons):
            if index % 3 == 0:
                row = ttk.Frame(frame, style="Sherlock.TFrame")
                row.pack(fill="x", pady=(0, 5))
            ttk.Button(row, text=text, command=command,
                       style="Sherlock.TButton").pack(side="left", padx=(0, 8))

    def refresh(self):
        selected = self._selected(self.tasks)
        self.tasks.delete(*self.tasks.get_children())
        tasks = self.store.list_tasks()
        priority_labels = {"low": "Низкий", "normal": "Обычный", "high": "Высокий"}
        detailed_tasks = self.store.list_task_estimates()
        states = {"done": "✓ Готово", "overdue": "⚠ Просрочено",
                  "today": "◉ Сегодня", "upcoming": "○ В работе",
                  "unscheduled": "○ В работе"}
        active_filter = self.task_filter.get()
        buckets = {
            "Открытые": {"overdue", "today", "upcoming", "unscheduled"},
            "Сегодня": {"today"},
            "Просроченные": {"overdue"},
            "Выполненные": {"done"},
            "Все": set(states),
        }[active_filter]
        visible_tasks = [task for task in detailed_tasks if task_bucket(task) in buckets]
        visible_tasks.sort(key=lambda task: (
            {"overdue": 0, "today": 1, "upcoming": 2, "unscheduled": 3, "done": 4}[task_bucket(task)],
            {"high": 0, "normal": 1, "low": 2}.get(task[3], 1),
            task[4] or "9999-99-99", task[0],
        ))
        self.task_count_label.configure(text=f"Показано: {len(visible_tasks)}")
        if visible_tasks:
            self.tasks_hint.pack_forget()
        else:
            empty_text = ("Задач пока нет. Добавь первую выше." if not detailed_tasks else
                          "По выбранному фильтру задач нет.")
            self.tasks_hint.configure(text=empty_text)
            self.tasks_hint.pack(fill="x", padx=10, pady=(0, 3), before=self.tasks)
        for task in visible_tasks:
            task_id, title, done, priority, due_date, minutes = task
            bucket = task_bucket(task)
            tags = (bucket,) if bucket in ("overdue", "today", "done") else ()
            self.tasks.insert("", "end", iid=str(task_id), tags=tags,
                              values=(states[bucket], title,
                                      priority_labels.get(priority, "Обычный"), due_date or "—",
                                      f"{minutes} мин." if minutes else "—"))
        if selected is not None and self.tasks.exists(str(selected)):
            self.tasks.selection_set(str(selected))
        self.notes.delete(*self.notes.get_children())
        notes = self.store.list_notes()
        for note_id, content in notes:
            self.notes.insert("", "end", iid=str(note_id), values=(content,))
        self.memories.delete(*self.memories.get_children())
        memories = self.store.list_memories()
        for memory_id, content in memories:
            self.memories.insert("", "end", iid=str(memory_id), values=(content,))
        self.conversations.delete(*self.conversations.get_children())
        conversations = self.store.list_conversations()
        for conversation_id, title, created_at in conversations:
            self.conversations.insert("", "end", iid=str(conversation_id), values=(title, created_at))
        open_count = sum(not done for _, _, done in tasks)
        overdue_count = sum(task_bucket(task) == "overdue" for task in detailed_tasks)
        today_count = sum(task_bucket(task) == "today" for task in detailed_tasks)
        self.status.configure(text=f"Открытых: {open_count} · Сегодня: {today_count} · Просрочено: {overdue_count} · Заметок: {len(notes)} · Память: {len(memories)}")

    @staticmethod
    def _selected(table):
        ids = table.selection()
        return int(ids[0]) if ids else None

    def add_task(self):
        title = simpledialog.askstring("Новая задача", "Что нужно сделать?", parent=self.window)
        if title is not None:
            self.create_task(title)

    def add_quick_task(self, event=None):
        title = self.quick_task_title.get()
        if self.create_task(title):
            self.quick_task_title.delete(0, "end")
            self.quick_task_title.focus_set()
        return "break"

    def create_task(self, title):
        try:
            self.store.add_task(title)
            self.task_filter.set("Открытые")
            self.refresh()
            return True
        except ValueError as exc:
            messagebox.showwarning("Проверь текст", str(exc), parent=self.window)
            return False

    def edit_task_details(self):
        task_id = self._selected(self.tasks)
        if task_id is None:
            self.status.configure(text="Сначала выбери задачу.")
            return
        details = next((task for task in self.store.list_task_details() if task[0] == task_id), None)
        if details is None:
            return
        current = {"low": "низкий", "normal": "обычный", "high": "высокий"}.get(details[3], "обычный")
        priority_text = simpledialog.askstring(
            "Приоритет задачи", "Выбери: низкий / обычный / высокий", initialvalue=current,
            parent=self.window)
        if priority_text is None:
            return
        priorities = {"низкий": "low", "обычный": "normal", "высокий": "high"}
        priority = priorities.get(priority_text.strip().lower())
        if priority is None:
            messagebox.showwarning("Приоритет", "Введи: низкий, обычный или высокий.", parent=self.window)
            return
        due = simpledialog.askstring(
            "Срок задачи", "Дата ГГГГ-ММ-ДД или пусто (без срока)",
            initialvalue=details[4] or "", parent=self.window)
        if due is None:
            return
        try:
            self.store.update_task_details(task_id, priority, due.strip() or None)
            self.refresh()
        except ValueError as exc:
            messagebox.showwarning("Проверь срок", str(exc), parent=self.window)

    def edit_task_estimate(self):
        task_id = self._selected(self.tasks)
        if task_id is None:
            self.status.configure(text="Сначала выбери задачу.")
            return
        entry = next((item for item in self.store.list_task_estimates() if item[0] == task_id), None)
        if entry is None:
            return
        value = simpledialog.askstring(
            "Длительность задачи",
            "Примерное время в минутах (5–1440). Пустое поле — неизвестно.",
            initialvalue=str(entry[5]) if entry[5] else "", parent=self.window)
        if value is None:
            return
        try:
            stripped = value.strip()
            minutes = int(stripped) if stripped else None
            self.store.update_task_estimate(task_id, minutes)
            self.refresh()
        except ValueError as exc:
            messagebox.showwarning("Проверь длительность", str(exc), parent=self.window)

    def complete_task(self):
        task_id = self._selected(self.tasks)
        if task_id is not None:
            self.store.complete_task(task_id)
            self.refresh()

    def delete_task(self):
        task_id = self._selected(self.tasks)
        if task_id is not None and messagebox.askyesno("Удалить задачу?", "Удалить выбранную задачу?", parent=self.window):
            self.store.delete_task(task_id)
            self.refresh()

    def add_note(self):
        self.editing_note_id = None
        self.note_editor.delete("1.0", "end")
        self.note_hint.configure(text="Новая заметка · до 1000 символов")
        self.note_editor.focus_set()

    def edit_note(self):
        note_id = self._selected(self.notes)
        if note_id is None:
            self.status.configure(text="Выбери заметку для редактирования.")
            return
        values = self.notes.item(str(note_id), "values")
        self.editing_note_id = note_id
        self.note_editor.delete("1.0", "end")
        self.note_editor.insert("1.0", values[0] if values else "")
        self.note_hint.configure(text=f"Редактирование заметки №{note_id}")
        self.note_editor.focus_set()

    def save_note(self):
        content = self.note_editor.get("1.0", "end-1c")
        try:
            if self.editing_note_id is None:
                self.store.add_note(content)
            elif not self.store.update_note(self.editing_note_id, content):
                self.status.configure(text="Заметка уже удалена. Обнови список.")
                return
            self.add_note()
            self.refresh()
        except ValueError as exc:
            messagebox.showwarning("Проверь текст", str(exc), parent=self.window)

    def delete_note(self):
        note_id = self._selected(self.notes)
        if note_id is not None and messagebox.askyesno("Удалить заметку?", "Удалить выбранную заметку?", parent=self.window):
            self.store.delete_note(note_id)
            if self.editing_note_id == note_id:
                self.add_note()
            self.refresh()

    def new_memory(self):
        self.editing_memory_id = None
        self.memory_editor.delete("1.0", "end")
        self.memory_hint.configure(text="Новый факт · сохраняется только после нажатия «Сохранить»")
        self.memory_editor.focus_set()

    def edit_memory(self):
        memory_id = self._selected(self.memories)
        if memory_id is None:
            self.status.configure(text="Выбери факт памяти.")
            return
        values = self.memories.item(str(memory_id), "values")
        self.editing_memory_id = memory_id
        self.memory_editor.delete("1.0", "end")
        self.memory_editor.insert("1.0", values[0] if values else "")
        self.memory_hint.configure(text=f"Редактирование факта №{memory_id}")
        self.memory_editor.focus_set()

    def save_memory(self):
        content = self.memory_editor.get("1.0", "end-1c")
        try:
            if self.editing_memory_id is None:
                self.store.add_memory(content)
            elif not self.store.update_memory(self.editing_memory_id, content):
                self.status.configure(text="Факт уже удалён.")
                return
            self.new_memory()
            self.refresh()
        except ValueError as exc:
            messagebox.showwarning("Проверь текст", str(exc), parent=self.window)

    def delete_memory(self):
        memory_id = self._selected(self.memories)
        if memory_id is not None and messagebox.askyesno(
                "Удалить память?", "Навсегда удалить выбранный факт?",
                parent=self.window):
            self.store.delete_memory(memory_id)
            if self.editing_memory_id == memory_id:
                self.new_memory()
            self.refresh()

    def open_conversation(self):
        conversation_id = self._selected(self.conversations)
        if conversation_id is None or self.on_open_conversation is None:
            return
        messages = self.store.load_conversation(conversation_id)
        if messages is not None:
            self.on_open_conversation(messages)

    def delete_conversation(self):
        conversation_id = self._selected(self.conversations)
        if conversation_id is not None and messagebox.askyesno(
                "Удалить диалог?", "Удалить эту сохранённую копию диалога?",
                parent=self.window):
            self.store.delete_conversation(conversation_id)
            self.refresh()

    def select_tab(self, index):
        self.tabs.select(index if index in (0, 1, 2, 3) else 0)
        self.refresh()

    def close(self):
        self.store.close()
        if not self.embedded:
            self.window.destroy()


def open_workspace(parent, initial_tab=0):
    child = tk.Toplevel(parent)
    WorkspaceWindow(child, initial_tab=initial_tab)
    return child


def main():
    root = tk.Tk()
    WorkspaceWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
