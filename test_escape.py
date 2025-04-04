import unittest
from src.utils.files import _escape_special_chars, _unescape_special_chars
from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX

class TestEscapeUnescape(unittest.TestCase):
    def test_round_trip(self):
        """Test that escaping and then unescaping preserves the original string."""
        # Test strings with various special characters
        test_strings = [
            f"Command: {COMMAND_START}find . --name \"*.py\"{COMMAND_END}",
            f"Result: {SUCCESS_PREFIX} Success or {ERROR_PREFIX} Error",
            f"Command with pipe: {COMMAND_START}grep pattern{STDIN_SEPARATOR}data{COMMAND_END}",
            "Plain text without special characters",
            f"Mixed content with {COMMAND_START} and {ERROR_PREFIX}",
            _escape_special_chars(f"Command: {COMMAND_START}find"),
            _escape_special_chars(_escape_special_chars(f"Command: {COMMAND_START}find"))
        ]
        
        # Special characters that should be escaped
        special_chars = [COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX]
        
        for test_str in test_strings:
            # Escape the string
            escaped = _escape_special_chars(test_str)
            
            # Verify the escaped string doesn't contain special characters
            for char in special_chars:
                self.assertNotIn(char, escaped, 
                                f"Escaped string should not contain {char!r}")
            
            # Unescape the string
            unescaped = _unescape_special_chars(escaped)
            
            # Verify the unescaped string matches the original
            self.assertEqual(test_str, unescaped, 
                           f"Round trip failed: {test_str!r} -> {escaped!r} -> {unescaped!r}")
            
            print(f"✓ Round trip successful: {test_str!r}")
    
    def test_escape_preescaped(self):
        """Test escape function properly handles already-escaped content"""
        # Test with already escaped sequences
        test_str = "This has escaped \\u25b6 and \\u25a0 characters"
        escaped = _escape_special_chars(test_str)
        
        # Verify that backslashes are doubled for escape sequences
        self.assertIn("\\\\u25b6", escaped)
        self.assertIn("\\\\u25a0", escaped)
        print(f"✓ Pre-escaped test passed")
    
    def test_unescape_double_escaped(self):
        """Test unescape function properly handles double-escaped content"""
        # Test with double-escaped sequences
        test_str = "This has double-escaped \\\\u25b6 and \\\\u25a0 characters"
        unescaped = _unescape_special_chars(test_str)
        
        # The expected result should have single-escaped unicode sequences
        expected = "This has double-escaped \\u25b6 and \\u25a0 characters"
        self.assertEqual(expected, unescaped)
        print(f"✓ Double-escaped test passed")

# For backwards compatibility, keep the print-based tests
def print_escape_examples():
    """Print examples of escaping special characters"""
    print("\n===== EXAMPLES OF ESCAPING =====")
    
    # Example with special characters
    test_str = f"This is a command: {COMMAND_START}find{COMMAND_END} with {SUCCESS_PREFIX} result"
    escaped = _escape_special_chars(test_str)
    print(f"Original: {test_str}")
    print(f"Escaped:  {escaped}")
    
    # Example with already escaped sequences
    test_str = "This has escaped \\u25b6 and \\u25a0 characters"
    escaped = _escape_special_chars(test_str)
    print(f"\nOriginal: {test_str}")
    print(f"Escaped:  {escaped}")

def print_unescape_examples():
    """Print examples of unescaping special characters"""
    print("\n===== EXAMPLES OF UNESCAPING =====")
    
    # Example with escaped special characters
    test_str = "This is a command: \\u25b6find\\u25a0 with \\u2705 result"
    unescaped = _unescape_special_chars(test_str)
    print(f"Escaped:   {test_str}")
    print(f"Unescaped: {unescaped}")
    
    # Example with double-escaped sequences
    test_str = "This has double-escaped \\\\u25b6 and \\\\u25a0 characters"
    unescaped = _unescape_special_chars(test_str)
    print(f"\nEscaped:   {test_str}")
    print(f"Unescaped: {unescaped}")

if __name__ == "__main__":
    # Run the unit tests
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    
    # Print examples
    print_escape_examples()
    print_unescape_examples()
