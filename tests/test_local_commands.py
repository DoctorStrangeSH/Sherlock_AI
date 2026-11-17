"""Natural-language local command recognition."""
import unittest
from local_commands import parse_local_command


class LocalCommandsTests(unittest.TestCase):
    def test_search(self):
        self.assertEqual(parse_local_command("Найди установку Ollama в выбранной папке"),
                         ("search", "установку Ollama"))
        self.assertEqual(parse_local_command("Поищи «отчёт» в этой папке!"),
                         ("search", "отчёт"))

    def test_create_note_requires_explicit_prefix(self):
        self.assertEqual(parse_local_command("Создай заметку: Купить молоко"),
                         ("save_note", "Купить молоко"))
        self.assertIsNone(parse_local_command("Помоги создать заметку"))
        self.assertIsNone(parse_local_command("Создай заметку: " + "x" * 1001))

    def test_task_commands(self):
        self.assertEqual(parse_local_command("Создай задачу: Проверить проект"),
                         ("create_task", "Проверить проект"))
        self.assertEqual(parse_local_command("Покажи мои задачи"), ("list_tasks", ""))
        self.assertEqual(parse_local_command("Отметь выполненной задачу #42"),
                         ("complete_task", 42))
        self.assertIsNone(parse_local_command("Заверши задачу 0"))
        self.assertIsNone(parse_local_command("Создай задачу: " + "x" * 301))

    def test_recent(self):
        self.assertEqual(parse_local_command("Покажи недавние файлы"), ("recent", ""))
        self.assertEqual(parse_local_command("Выведи последние документы в этой папке"),
                         ("recent", ""))

    def test_ordinary_chat_is_not_command(self):
        for question in ("Найди смысл жизни", "Как найти документ?",
                         "Удалить все файлы", "покажи последние новости",
                         "найди X в папке C:\\"):
            self.assertIsNone(parse_local_command(question))


if __name__ == "__main__":
    unittest.main()
