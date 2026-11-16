"""Simple offline tasks/notes window shared by standalone and desktop launch."""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from offline_workspace import OfflineWorkspace


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
    style.configure("Sherlock.TButton", background=INPUT, foreground=FG,
                    padding=(13, 9), borderwidth=0, font=("Segoe UI", 10))
    style.map("Sherlock.TButton", background=[("active", "#34456e"),
                                              ("pressed", "#34456e")],
              foreground=[("disabled", MUTED)])


class WorkspaceWindow:
    def __init__(self, window, initial_tab=0, embedded=False):
        self.window = window
        self.store = OfflineWorkspace()
        self.embedded = embedded
        if not embedded:
            window.title("Sherlock AI — задачи и заметки")
            window.geometry("760x510")
            window.minsize(580, 400)
            window.protocol("WM_DELETE_WINDOW", self.close)
        window.configure(bg=BG)
        configure_dark_theme(window)
        tk.Label(window, text="Задачи и заметки", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", padx=20, pady=(18, 3))
        tk.Label(window, text="Хранятся только на этом компьютере · Telegram не требуется",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=20, pady=(0, 14))
        tabs = ttk.Notebook(window, style="Sherlock.TNotebook")
        self.tabs = tabs
        tabs.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.task_frame = ttk.Frame(tabs, style="Sherlock.TFrame")
        self.note_frame = ttk.Frame(tabs, style="Sherlock.TFrame")
        tabs.add(self.task_frame, text="Задачи")
        tabs.add(self.note_frame, text="Заметки")
        tabs.select(1 if initial_tab == 1 else 0)
        self.tasks = self._table(self.task_frame, ("Состояние", "Задача"), (100, 550))
        self.notes = self._table(self.note_frame, ("Заметка",), (650,))
        self._controls(self.task_frame, (("Добавить задачу", self.add_task),
                                         ("Выполнено", self.complete_task),
                                         ("Удалить", self.delete_task)))
        self._controls(self.note_frame, (("Добавить заметку", self.add_note),
                                         ("Удалить", self.delete_note)))
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
        frame.pack(fill="x", padx=10, pady=(0, 10))
        for text, command in buttons:
            ttk.Button(frame, text=text, command=command,
                       style="Sherlock.TButton").pack(side="left", padx=(0, 8))

    def refresh(self):
        self.tasks.delete(*self.tasks.get_children())
        tasks = self.store.list_tasks()
        for task_id, title, done in tasks:
            self.tasks.insert("", "end", iid=str(task_id), values=("✓ Готово" if done else "○ В работе", title))
        self.notes.delete(*self.notes.get_children())
        notes = self.store.list_notes()
        for note_id, content in notes:
            self.notes.insert("", "end", iid=str(note_id), values=(content,))
        open_count = sum(not done for _, _, done in tasks)
        self.status.configure(text=f"Открытых задач: {open_count} · Заметок: {len(notes)} · Изменения сохраняются автоматически")

    @staticmethod
    def _selected(table):
        ids = table.selection()
        return int(ids[0]) if ids else None

    def add_task(self):
        title = simpledialog.askstring("Новая задача", "Что нужно сделать?", parent=self.window)
        if title is not None:
            try:
                self.store.add_task(title)
                self.refresh()
            except ValueError as exc:
                messagebox.showwarning("Проверь текст", str(exc), parent=self.window)

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
        content = simpledialog.askstring("Новая заметка", "Что запомнить?", parent=self.window)
        if content is not None:
            try:
                self.store.add_note(content)
                self.refresh()
            except ValueError as exc:
                messagebox.showwarning("Проверь текст", str(exc), parent=self.window)

    def delete_note(self):
        note_id = self._selected(self.notes)
        if note_id is not None and messagebox.askyesno("Удалить заметку?", "Удалить выбранную заметку?", parent=self.window):
            self.store.delete_note(note_id)
            self.refresh()

    def select_tab(self, index):
        self.tabs.select(1 if index == 1 else 0)
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
