import unittest
from src.utils.files import _escape_special_chars, _unescape_special_chars
from src.core.constants import (
    COMMAND_START,
    COMMAND_END,
    STDIN_SEPARATOR,
    ERROR_PREFIX,
    SUCCESS_PREFIX,
)


class TestEscapeUnescape(unittest.TestCase):
    def test_round_trip(self):
        """Test that escaping and then unescaping preserves the original string."""
        # Test strings with various special characters
        test_strings = [
            f'Command: {COMMAND_START}find . --name "*.py"{COMMAND_END}',
            f"Result: {SUCCESS_PREFIX} Success or {ERROR_PREFIX} Error",
            f"Command with pipe: {COMMAND_START}grep pattern{STDIN_SEPARATOR}data{COMMAND_END}",
            "Plain text without special characters",
            f"Mixed content with {COMMAND_START} and {ERROR_PREFIX}",
        ]

        # Special characters that should be escaped
        special_chars = [
            COMMAND_START,
            COMMAND_END,
            STDIN_SEPARATOR,
            ERROR_PREFIX,
            SUCCESS_PREFIX,
        ]

        for test_str in test_strings:
            # Escape the string
            escaped = _escape_special_chars(test_str)

            # Verify the escaped string doesn't contain special characters
            for char in special_chars:
                self.assertNotIn(
                    char, escaped, f"Escaped string should not contain {char!r}"
                )

            # Unescape the string
            unescaped = _unescape_special_chars(escaped)

            # Verify the unescaped string matches the original
            self.assertEqual(
                test_str,
                unescaped,
                f"Round trip failed: {test_str!r} -> {escaped!r} -> {unescaped!r}",
            )

            print(f"✓ Round trip successful: {test_str!r}")


if __name__ == "__main__":
    # Run the unit tests
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
