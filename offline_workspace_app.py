"""Simple offline tasks/notes window shared by standalone and desktop launch."""
import tkinter as tk
from datetime import date, timedelta
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
                                         ("Изменить задачу", self.edit_task_details),
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
        self.tasks.bind("<Double-1>", lambda _event: self.edit_task_details())
        self.note_search = self._search_bar(self.note_frame, "Поиск по заметкам…")
        self.notes_empty = tk.Label(
            self.note_frame, text="Заметок пока нет. Нажми «Новая», чтобы создать первую.",
            bg=PANEL, fg=MUTED, anchor="w", padx=14, pady=10,
        )
        self.notes = self._table(self.note_frame, ("Заметка",), (650,))
        self.memory_search = self._search_bar(self.memory_frame, "Поиск по памяти…")
        self.memory_empty = tk.Label(
            self.memory_frame,
            text="Память пуста. Сохраняются только факты, которые ты добавишь сам.",
            bg=PANEL, fg=MUTED, anchor="w", padx=14, pady=10,
        )
        self.memories = self._table(self.memory_frame, ("Сохранённый факт",), (650,))
        self.note_search.trace_add("write", lambda *_args: self.refresh())
        self.memory_search.trace_add("write", lambda *_args: self.refresh())
        self.history_search = self._search_bar(self.history_frame, "Поиск по названию…")
        self.history_empty = tk.Label(
            self.history_frame, text="Сохранённых разговоров пока нет.",
            bg=PANEL, fg=MUTED, anchor="w", padx=14, pady=10,
        )
        self.conversations = self._table(self.history_frame, ("Название", "Дата"), (450, 160))
        self.history_search.trace_add("write", lambda *_args: self.refresh())
        self._controls(self.note_frame, (("Новая", self.add_note),
                                         ("Изменить", self.edit_note),
                                         ("Сохранить", self.save_note),
                                         ("Удалить", self.delete_note)))
        self.editing_note_id = None
        self.note_baseline = ""
        self.note_hint = tk.Label(self.note_frame, text="Новая заметка · до 1000 символов",
                                  bg=BG, fg=MUTED, anchor="w")
        self.note_hint.pack(fill="x", padx=18, pady=(0, 5))
        self.note_editor = tk.Text(self.note_frame, height=5, bg=INPUT, fg=FG,
                                   insertbackground=FG, wrap="word", relief="flat",
                                   font=("Segoe UI", 10), padx=12, pady=9)
        self.note_editor.pack(fill="x", padx=18, pady=(0, 3))
        note_help = tk.Frame(self.note_frame, bg=BG)
        note_help.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(note_help, text="Ctrl+S — сохранить · Ctrl+N — новая",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        self.note_counter = tk.Label(note_help, text="0 / 1000",
                                     bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.note_counter.pack(side="right")
        self.note_editor.bind("<KeyRelease>", lambda _event: self.refresh_editor_counters())
        self.note_editor.bind("<Control-s>", lambda _event: self.editor_shortcut(self.save_note))
        self.note_editor.bind("<Control-n>", lambda _event: self.editor_shortcut(self.add_note))
        self.note_editor.bind("<Control-Return>", lambda _event: self.editor_shortcut(self.save_note))
        self.notes.bind("<Double-1>", lambda _event: self.edit_note())
        self._controls(self.memory_frame, (("Новый факт", self.new_memory),
                                          ("Изменить", self.edit_memory),
                                          ("Сохранить", self.save_memory),
                                          ("Удалить", self.delete_memory)))
        self.editing_memory_id = None
        self.memory_baseline = ""
        self.memory_hint = tk.Label(self.memory_frame,
                                    text="Память сохраняется только по твоему решению · до 500 символов",
                                    bg=BG, fg=MUTED, anchor="w")
        self.memory_hint.pack(fill="x", padx=18, pady=(0, 5))
        self.memory_editor = tk.Text(self.memory_frame, height=4, bg=INPUT, fg=FG,
                                     insertbackground=FG, wrap="word", relief="flat",
                                     font=("Segoe UI", 10), padx=12, pady=9)
        self.memory_editor.pack(fill="x", padx=18, pady=(0, 3))
        memory_help = tk.Frame(self.memory_frame, bg=BG)
        memory_help.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(memory_help, text="Ctrl+S — сохранить · Ctrl+N — новый факт",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        self.memory_counter = tk.Label(memory_help, text="0 / 500",
                                       bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.memory_counter.pack(side="right")
        self.memory_editor.bind("<KeyRelease>", lambda _event: self.refresh_editor_counters())
        self.memory_editor.bind("<Control-s>", lambda _event: self.editor_shortcut(self.save_memory))
        self.memory_editor.bind("<Control-n>", lambda _event: self.editor_shortcut(self.new_memory))
        self.memory_editor.bind("<Control-Return>", lambda _event: self.editor_shortcut(self.save_memory))
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
    def _search_bar(parent, prompt):
        search_row = tk.Frame(parent, bg=BG)
        search_row.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(search_row, text="⌕", bg=BG, fg=MUTED,
                 font=("Segoe UI", 13)).pack(side="left", padx=(0, 8))
        query = tk.StringVar()
        tk.Entry(search_row, textvariable=query, bg=INPUT, fg=FG,
                 insertbackground=FG, relief="flat",
                 font=("Segoe UI", 10)).pack(
                     side="left", fill="x", expand=True, ipady=7,
                 )
        tk.Label(search_row, text=prompt, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right", padx=(9, 0))
        return query

    @staticmethod
    def _table(parent, labels, widths):
        tree = ttk.Treeview(parent, columns=labels, show="headings", selectmode="browse",
                            style="Sherlock.Treeview")
        for label, width in zip(labels, widths):
            tree.heading(label, text=label)
            tree.column(label, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y", pady=10, padx=(0, 4), before=tree)
        tree.configure(yscrollcommand=scrollbar.set)
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
        selected_note = self._selected(self.notes)
        self.notes.delete(*self.notes.get_children())
        notes = self.store.list_notes()
        note_query = self.note_search.get().strip().casefold()
        visible_notes = [(note_id, content) for note_id, content in notes
                         if note_query in content.casefold()]
        self.notes_empty.configure(
            text="Заметок пока нет. Нажми «Новая», чтобы создать первую." if not notes
            else "По запросу заметок не найдено.",
        )
        if visible_notes:
            self.notes_empty.pack_forget()
        else:
            self.notes_empty.pack(fill="x", padx=10, pady=(7, 0), before=self.notes)
        for note_id, content in visible_notes:
            self.notes.insert("", "end", iid=str(note_id), values=(content,))
        if selected_note is not None and self.notes.exists(str(selected_note)):
            self.notes.selection_set(str(selected_note))
        selected_memory = self._selected(self.memories)
        self.memories.delete(*self.memories.get_children())
        memories = self.store.list_memories()
        memory_query = self.memory_search.get().strip().casefold()
        visible_memories = [(memory_id, content) for memory_id, content in memories
                            if memory_query in content.casefold()]
        self.memory_empty.configure(
            text="Память пуста. Добавь факт только по своему желанию." if not memories
            else "По запросу фактов не найдено.",
        )
        if visible_memories:
            self.memory_empty.pack_forget()
        else:
            self.memory_empty.pack(fill="x", padx=10, pady=(7, 0), before=self.memories)
        for memory_id, content in visible_memories:
            self.memories.insert("", "end", iid=str(memory_id), values=(content,))
        if selected_memory is not None and self.memories.exists(str(selected_memory)):
            self.memories.selection_set(str(selected_memory))
        selected_conversation = self._selected(self.conversations)
        self.conversations.delete(*self.conversations.get_children())
        conversations = self.store.list_conversations()
        history_query = self.history_search.get().strip().casefold()
        visible_conversations = [
            (conversation_id, title, created_at)
            for conversation_id, title, created_at in conversations
            if history_query in title.casefold()
        ]
        self.history_empty.configure(
            text="Сохранённых разговоров пока нет." if not conversations
            else "По этому запросу разговоров не найдено.",
        )
        if visible_conversations:
            self.history_empty.pack_forget()
        else:
            self.history_empty.pack(fill="x", padx=10, pady=(7, 0),
                                    before=self.conversations)
        for conversation_id, title, created_at in visible_conversations:
            self.conversations.insert("", "end", iid=str(conversation_id),
                                      values=(title, created_at))
        if selected_conversation is not None and self.conversations.exists(str(selected_conversation)):
            self.conversations.selection_set(str(selected_conversation))
        open_count = sum(not done for _, _, done in tasks)
        overdue_count = sum(task_bucket(task) == "overdue" for task in detailed_tasks)
        today_count = sum(task_bucket(task) == "today" for task in detailed_tasks)
        self.status.configure(text=f"Открытых: {open_count} · Сегодня: {today_count} · Просрочено: {overdue_count} · Заметок: {len(notes)} · Память: {len(memories)}")

    @staticmethod
    def _selected(table):
        ids = table.selection()
        return int(ids[0]) if ids else None

    def add_task(self):
        self.open_task_editor()

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
        self.open_task_editor(task_id)

    def open_task_editor(self, task_id=None):
        """Single editor for title, priority, deadline and estimated minutes."""
        task = None
        if task_id is not None:
            task = next(
                (item for item in self.store.list_task_estimates() if item[0] == task_id),
                None,
            )
            if task is None:
                self.status.configure(text="Задача больше не найдена. Обнови список.")
                return
        owner = self.window.winfo_toplevel()
        editor = tk.Toplevel(owner)
        editor.title("Новая задача" if task is None else f"Задача №{task_id}")
        editor.configure(bg=BG)
        editor.geometry("440x415")
        editor.resizable(False, False)
        editor.transient(owner)
        content = tk.Frame(editor, bg=BG, padx=22, pady=18)
        content.pack(fill="both", expand=True)

        tk.Label(content, text="Новая задача" if task is None else "Редактирование задачи",
                 bg=BG, fg=FG, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(content, text="Все изменения сохраняются только на этом компьютере.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 14))

        title_var = tk.StringVar(value=task[1] if task else "")
        priority_labels = {"low": "Низкий", "normal": "Обычный", "high": "Высокий"}
        priority_var = tk.StringVar(value=priority_labels.get(task[3], "Обычный") if task else "Обычный")
        due_var = tk.StringVar(value=(task[4] or "") if task else "")
        minutes_var = tk.StringVar(value=str(task[5]) if task and task[5] else "")

        tk.Label(content, text="Название задачи", bg=BG, fg=FG).pack(anchor="w")
        title_input = tk.Entry(content, textvariable=title_var, bg=INPUT, fg=FG,
                               insertbackground=FG, relief="flat", font=("Segoe UI", 11))
        title_input.pack(fill="x", ipady=7, pady=(4, 11))

        details = tk.Frame(content, bg=BG)
        details.pack(fill="x", pady=(0, 11))
        priority_column = tk.Frame(details, bg=BG)
        priority_column.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(priority_column, text="Приоритет", bg=BG, fg=FG).pack(anchor="w")
        ttk.Combobox(priority_column, textvariable=priority_var, state="readonly",
                     values=("Низкий", "Обычный", "Высокий"),
                     style="Sherlock.TCombobox", width=17).pack(fill="x", pady=(4, 0))
        minutes_column = tk.Frame(details, bg=BG)
        minutes_column.pack(side="left", fill="x", expand=True)
        tk.Label(minutes_column, text="Оценка, минуты", bg=BG, fg=FG).pack(anchor="w")
        tk.Entry(minutes_column, textvariable=minutes_var, bg=INPUT, fg=FG,
                 insertbackground=FG, relief="flat").pack(fill="x", ipady=7, pady=(4, 0))

        tk.Label(content, text="Срок · ГГГГ-ММ-ДД (необязательно)",
                 bg=BG, fg=FG).pack(anchor="w")
        tk.Entry(content, textvariable=due_var, bg=INPUT, fg=FG,
                 insertbackground=FG, relief="flat").pack(fill="x", ipady=7, pady=(4, 7))
        shortcuts = tk.Frame(content, bg=BG)
        shortcuts.pack(fill="x", pady=(0, 12))
        for label, value in (
            ("Сегодня", date.today().isoformat()),
            ("Завтра", (date.today() + timedelta(days=1)).isoformat()),
            ("Без срока", ""),
        ):
            tk.Button(shortcuts, text=label, command=lambda v=value: due_var.set(v),
                      bg=PANEL, fg=FG, relief="flat", padx=10, pady=5).pack(
                          side="left", padx=(0, 6))

        def save():
            minutes_text = minutes_var.get().strip()
            try:
                minutes = int(minutes_text) if minutes_text else None
                priority = {"Низкий": "low", "Обычный": "normal", "Высокий": "high"}[priority_var.get()]
                if task is None:
                    self.store.add_task_full(title_var.get(), priority, due_var.get().strip(), minutes)
                elif not self.store.save_task_fields(
                    task_id, title_var.get(), priority, due_var.get().strip(), minutes,
                ):
                    messagebox.showwarning(
                        "Задача не найдена", "Задача удалена. Обнови список.", parent=editor,
                    )
                    return
            except ValueError as exc:
                messagebox.showwarning("Проверь данные", str(exc), parent=editor)
                return
            editor.destroy()
            self.task_filter.set("Открытые" if task is None else self.task_filter.get())
            self.refresh()
            self.status.configure(text="Задача создана." if task is None else "Изменения сохранены.")

        actions = tk.Frame(content, bg=BG)
        actions.pack(fill="x")
        tk.Button(actions, text="Сохранить", command=save, bg=ACCENT, fg=BG,
                  relief="flat", padx=17, pady=9).pack(side="right")
        tk.Button(actions, text="Отмена", command=editor.destroy, bg=PANEL, fg=FG,
                  relief="flat", padx=14, pady=9).pack(side="right", padx=(0, 8))
        editor.bind("<Escape>", lambda _event: editor.destroy())
        editor.grab_set()
        title_input.focus_set()

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

    @staticmethod
    def editor_shortcut(callback):
        callback()
        return "break"

    def refresh_editor_counters(self):
        note_length = len(self.note_editor.get("1.0", "end-1c"))
        memory_length = len(self.memory_editor.get("1.0", "end-1c"))
        self.note_counter.configure(
            text=f"{note_length} / 1000",
            fg="#ffb0a5" if note_length > 1000 else MUTED,
        )
        self.memory_counter.configure(
            text=f"{memory_length} / 500",
            fg="#ffb0a5" if memory_length > 500 else MUTED,
        )

    def confirm_editor_discard(self, kind):
        """Keep local drafts unless the user explicitly discards them."""
        editor = self.note_editor if kind == "note" else self.memory_editor
        baseline = self.note_baseline if kind == "note" else self.memory_baseline
        current = editor.get("1.0", "end-1c")
        if current == baseline:
            return True
        return messagebox.askyesno(
            "Несохранённые изменения",
            "Текст ещё не сохранён. Отменить изменения и продолжить?",
            parent=self.window.winfo_toplevel(),
        )

    def add_note(self):
        if not self.confirm_editor_discard("note"):
            return
        self.editing_note_id = None
        self.note_baseline = ""
        self.note_editor.delete("1.0", "end")
        self.note_hint.configure(text="Новая заметка · до 1000 символов")
        self.note_editor.focus_set()
        self.refresh_editor_counters()

    def edit_note(self):
        note_id = self._selected(self.notes)
        if note_id is None:
            self.status.configure(text="Выбери заметку для редактирования.")
            return
        if not self.confirm_editor_discard("note"):
            return
        values = self.notes.item(str(note_id), "values")
        self.editing_note_id = note_id
        self.note_baseline = values[0] if values else ""
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
            self.note_baseline = content
            self.add_note()
            self.refresh()
        except ValueError as exc:
            messagebox.showwarning("Проверь текст", str(exc), parent=self.window)

    def delete_note(self):
        note_id = self._selected(self.notes)
        if note_id is not None and messagebox.askyesno("Удалить заметку?", "Удалить выбранную заметку?", parent=self.window):
            self.store.delete_note(note_id)
            if self.editing_note_id == note_id:
                self.note_baseline = self.note_editor.get("1.0", "end-1c")
                self.add_note()
            self.refresh()

    def new_memory(self):
        if not self.confirm_editor_discard("memory"):
            return
        self.editing_memory_id = None
        self.memory_baseline = ""
        self.memory_editor.delete("1.0", "end")
        self.memory_hint.configure(text="Новый факт · сохраняется только после нажатия «Сохранить»")
        self.memory_editor.focus_set()
        self.refresh_editor_counters()

    def edit_memory(self):
        memory_id = self._selected(self.memories)
        if memory_id is None:
            self.status.configure(text="Выбери факт памяти.")
            return
        if not self.confirm_editor_discard("memory"):
            return
        values = self.memories.item(str(memory_id), "values")
        self.editing_memory_id = memory_id
        self.memory_baseline = values[0] if values else ""
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
            self.memory_baseline = content
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
                self.memory_baseline = self.memory_editor.get("1.0", "end-1c")
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
        if not self.confirm_editor_discard("note"):
            return False
        if not self.confirm_editor_discard("memory"):
            return False
        self.store.close()
        if not self.embedded:
            self.window.destroy()
        return True


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
