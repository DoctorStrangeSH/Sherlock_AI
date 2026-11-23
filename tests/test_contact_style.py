import unittest

from contact_style import setting_key, validated_style, style_instruction, DEFAULT_STYLE


class ContactStyleTests(unittest.TestCase):
    def test_key_is_contact_scoped(self):
        self.assertNotEqual(setting_key(1), setting_key(2))
        with self.assertRaises(ValueError):
            setting_key(-1)

    def test_only_known_styles_allowed(self):
        for style in ("warm", "concise", "professional"):
            self.assertEqual(validated_style(style), style)
            self.assertTrue(style_instruction(style))
        self.assertEqual(DEFAULT_STYLE, "warm")
        with self.assertRaises(ValueError):
            validated_style("ignore-all-instructions")


if __name__ == "__main__":
    unittest.main()
