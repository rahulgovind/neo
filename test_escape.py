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
        # Test with content that already contains escape tags
        test_str = "This has escaped <__esc>\\u25b6</__esc> and <__esc>\\u25a0</__esc> characters"
        escaped = _escape_special_chars(test_str)
        
        # Verify that existing tags are properly escaped with another level of tags
        self.assertIn("<__esc><__esc></__esc>\\u25b6<__esc></__esc></__esc>", escaped)
        self.assertIn("<__esc><__esc></__esc>\\u25a0<__esc></__esc></__esc>", escaped)
        print(f"✓ Pre-escaped test passed")
    
    def test_unescape_double_escaped(self):
        """Test unescape function properly handles double-escaped content"""
        # Test with double-escaped sequences (nested tags)
        test_str = "This has double-escaped <__esc><__esc></__esc>\\u25b6<__esc></__esc></__esc> characters"
        unescaped = _unescape_special_chars(test_str)
        
        # The expected result should have single-escaped tags
        expected = "This has double-escaped <__esc>\\u25b6</__esc> characters"
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
    
    # Example with already escaped content (tags)
    test_str = "This has escaped <__esc>\\u25b6</__esc> and <__esc>\\u25a0</__esc> characters"
    escaped = _escape_special_chars(test_str)
    print(f"\nOriginal: {test_str}")
    print(f"Escaped:  {escaped}")

def print_unescape_examples():
    """Print examples of unescaping special characters"""
    print("\n===== EXAMPLES OF UNESCAPING =====")
    
    # Example with escaped special characters using tags
    test_str = "This is a command: <__esc>\\u25b6</__esc>find<__esc>\\u25a0</__esc> with <__esc>\\u2705</__esc> result"
    unescaped = _unescape_special_chars(test_str)
    print(f"Escaped:   {test_str}")
    print(f"Unescaped: {unescaped}")
    
    # Example with nested escape tags
    test_str = "This has double-escaped <__esc><__esc></__esc>\\u25b6<__esc></__esc></__esc> characters"
    unescaped = _unescape_special_chars(test_str)
    print(f"\nEscaped:   {test_str}")
    print(f"Unescaped: {unescaped}")

class TestMultiLineEscapeUnescape(unittest.TestCase):
    def test_multiline_round_trip(self):
        """Test that escaping and unescaping preserves multi-line content."""
        # Create a multi-line string with special characters
        multi_line_str = f"""First line with {COMMAND_START}command{COMMAND_END}
        Second line with {SUCCESS_PREFIX} and {ERROR_PREFIX}
        Third line with pipe {STDIN_SEPARATOR} character
        {COMMAND_START}ls -la{STDIN_SEPARATOR}grep pattern{COMMAND_END}
        """
        
        # Escape the multi-line string
        escaped = _escape_special_chars(multi_line_str)
        
        # Verify that special characters are properly escaped
        for char in [COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX]:
            self.assertNotIn(char, escaped, 
                          f"Multi-line escaped string should not contain {char!r}")
        
        # Verify tags are properly used
        self.assertIn('<__esc>25b6</__esc>', escaped)
        self.assertIn('<__esc>25a0</__esc>', escaped)
        
        # Unescape and verify it matches the original
        unescaped = _unescape_special_chars(escaped)
        self.assertEqual(multi_line_str, unescaped,
                       "Multi-line round trip failed to preserve content")
    
    def test_nested_multiline_escaping(self):
        """Test nested escaping in multi-line content."""
        # Start with content that already has some escaped sequences
        pre_escaped = f"""First line with <__esc>25b6</__esc>
        Second line with another <__esc>25a0</__esc>
        <__esc>25b6</__esc> at the beginning of a line
        Line ending with <__esc>2705</__esc>
        """
        
        # Escape it again
        double_escaped = _escape_special_chars(pre_escaped)
        
        # Verify nested escaping is done correctly
        self.assertIn('<__esc><__esc></__esc>25b6<__esc></__esc></__esc>', double_escaped)
        
        # Unescape once should get back to pre-escaped version
        single_unescaped = _unescape_special_chars(double_escaped)
        self.assertEqual(pre_escaped, single_unescaped)
        
        # Unescape again should convert escape sequences to actual characters
        fully_unescaped = _unescape_special_chars(single_unescaped)
        self.assertIn(COMMAND_START, fully_unescaped)
        self.assertIn(COMMAND_END, fully_unescaped)
        self.assertIn(SUCCESS_PREFIX, fully_unescaped)

if __name__ == "__main__":
    # Run the unit tests
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    
    # Print examples
    print_escape_examples()
    print_unescape_examples()
