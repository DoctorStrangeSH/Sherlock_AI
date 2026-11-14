"""Check Telegram command patterns without importing credentials or Telethon."""

import ast
from pathlib import Path
import re
import unittest


COMMANDS = ("drafts", "drafttone", "senddraft", "canceldraft", "editdraft", "showdraft")


class TelegramCommandPatternTests(unittest.TestCase):
    def test_draft_commands_match_literal_dot_and_whitespace(self):
        source = Path(__file__).resolve().parents[1].joinpath("secretary.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        command_patterns = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                for call in ast.walk(decorator):
                    if not isinstance(call, ast.Call):
                        continue
                    for keyword in call.keywords:
                        if keyword.arg == "pattern" and isinstance(keyword.value, ast.Constant):
                            command_patterns.append(keyword.value.value)
        for name in COMMANDS:
            matching = [pattern for pattern in command_patterns
                        if re.match(pattern, "." + name + " 123")]
            self.assertEqual(len(matching), 1, f"{name} must have one working handler")
            self.assertIsNone(re.match(matching[0], "x" + name + " 123"))
            self.assertIsNone(re.match(matching[0], "." + name + "extra"))


if __name__ == "__main__":
    unittest.main()
