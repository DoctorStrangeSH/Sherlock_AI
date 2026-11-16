"""Simple offline tasks/notes window shared by standalone and desktop launch."""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from offline_workspace import OfflineWorkspace


class WorkspaceWindow:
    def __init__(self, window):
        self.window = window
        self.store = OfflineWorkspace()
        window.title("Sherlock AI — задачи и заметки")
        window.geometry("760x510")
        window.minsize(580, 400)
        window.configure(bg="#0b1020")
        window.protocol("WM_DELETE_WINDOW", self.close)
        tk.Label(window, text="Задачи и заметки", font=("Segoe UI", 20, "bold"),
                 bg="#0b1020", fg="#e7eaf2").pack(anchor="w", padx=20, pady=(18, 3))
        tk.Label(window, text="Хранятся только на этом компьютере · Telegram не требуется",
                 bg="#0b1020", fg="#98a6c4").pack(anchor="w", padx=20, pady=(0, 14))
        tabs = ttk.Notebook(window)
        tabs.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.task_frame = ttk.Frame(tabs)
        self.note_frame = ttk.Frame(tabs)
        tabs.add(self.task_frame, text="Задачи")
        tabs.add(self.note_frame, text="Заметки")
        self.tasks = self._table(self.task_frame, ("Состояние", "Задача"), (100, 550))
        self.notes = self._table(self.note_frame, ("Заметка",), (650,))
        self._controls(self.task_frame, (("Добавить задачу", self.add_task),
                                         ("Выполнено", self.complete_task),
                                         ("Удалить", self.delete_task)))
        self._controls(self.note_frame, (("Добавить заметку", self.add_note),
                                         ("Удалить", self.delete_note)))
        self.refresh()

    @staticmethod
    def _table(parent, labels, widths):
        tree = ttk.Treeview(parent, columns=labels, show="headings", selectmode="browse")
        for label, width in zip(labels, widths):
            tree.heading(label, text=label)
            tree.column(label, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        return tree

    @staticmethod
    def _controls(parent, buttons):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=10, pady=(0, 10))
        for text, command in buttons:
            ttk.Button(frame, text=text, command=command).pack(side="left", padx=(0, 8))

    def refresh(self):
        self.tasks.delete(*self.tasks.get_children())
        for task_id, title, done in self.store.list_tasks():
            self.tasks.insert("", "end", iid=str(task_id), values=("✓ Готово" if done else "○ В работе", title))
        self.notes.delete(*self.notes.get_children())
        for note_id, content in self.store.list_notes():
            self.notes.insert("", "end", iid=str(note_id), values=(content,))

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

    def close(self):
        self.store.close()
        self.window.destroy()


def open_workspace(parent):
    child = tk.Toplevel(parent)
    WorkspaceWindow(child)
    return child


def main():
    root = tk.Tk()
    WorkspaceWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
