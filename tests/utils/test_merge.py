import pytest
from textwrap import dedent
from dataclasses import dataclass
from typing import Optional

from src.utils.merge import merge


@dataclass
class MergeTestCase:
    """Data class representing a test case for the merge function."""
    name: str
    initial_content: str
    changes: str
    expected_output: str


# Define test cases
test_cases = [
    # Basic merge test - replace one line
    MergeTestCase(
        name="basic_update",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        changes=dedent("""\
            @ UPDATE
            @@ BEFORE
            3:line 3
            @@ AFTER
            3:new line 3
        """),
        expected_output=dedent("""\
            line 1
            line 2
            new line 3
            line 4
            line 5
        """),
    ),
    # Deletion test - remove a line
    MergeTestCase(
        name="deletion",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        changes=dedent("""\
            @ DELETE
            3:line 3
        """),
        expected_output=dedent("""\
            line 1
            line 2
            line 4
            line 5
        """),
    ),
    # Update test with multiple lines
    MergeTestCase(
        name="multi_line_update",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        changes=dedent("""\
            @ UPDATE
            @@ BEFORE
            2:line 2
            3:line 3
            @@ AFTER
            2:new line 2
            3:new line 3
            4:extra line
        """),
        expected_output=dedent("""\
            line 1
            new line 2
            new line 3
            extra line
            line 4
            line 5
        """),
    ),
    # Empty line content test - handling blank lines
    MergeTestCase(
        name="empty_line_content",
        initial_content=dedent("""\
            Header
            
            The Agent builds on top of the Model:
            
            - Feature 1
            - Feature 2
        """),
        changes=dedent("""\
            @ UPDATE
            @@ BEFORE
            3:The Agent builds on top of the Model:
            @@ AFTER
            3:The Agent builds on top of the Shell:"""),
        expected_output=dedent("""\
            Header
            
            The Agent builds on top of the Shell:
            
            - Feature 1
            - Feature 2
        """),
    ),
    # Multiple operations test
    MergeTestCase(
        name="multiple_operations",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        changes=dedent("""\
            @ UPDATE
            @@ BEFORE
            1:line 1
            2:line 2
            @@ AFTER
            1:new line 1
            2:new line 2
            3:inserted line
            
            @ DELETE
            4:line 4
            
            @ UPDATE
            @@ BEFORE
            5:line 5
            @@ AFTER
            5:new line 5
            6:appended line
        """),
        expected_output=dedent("""\
            new line 1
            new line 2
            inserted line
            line 3
            new line 5
            appended line
        """),
    ),
    # Test with no line numbers in changes
    MergeTestCase(
        name="no_line_numbers",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        changes=dedent("""\
            @ UPDATE
            @@ BEFORE
            line 1
            line 2
            @@ AFTER
            new line 1
            new line 2"""),
        expected_output=dedent("""\
            new line 1
            new line 2
            line 3
            line 4
            line 5
        """),
    ),
]


@dataclass
class MergeErrorTestCase:
    """Data class representing an error test case for the merge function."""

    name: str
    initial_content: str
    changes: str
    expected_error: str


# Define error test cases
error_test_cases = [
    # Invalid update format test - missing @@AFTER section
    MergeErrorTestCase(
        name="invalid_update_format",
        initial_content="line 1\nline 2\nline 3\n",
        changes=dedent("""\
            @ UPDATE
            
            @@ BEFORE
            line 1
        """),
        expected_error="UPDATE chunk must have @@AFTER section",
    ),
    # Invalid content match
    MergeErrorTestCase(
        name="invalid_content_match",
        initial_content="line 1\nline 2\nline 3\n",
        changes=dedent("""\
            @ UPDATE
            
            @@ BEFORE
            nonexistent line
            @@ AFTER
            new content
        """),
        expected_error="do not match existing content",
    ),
    # Unknown operation type
    MergeErrorTestCase(
        name="unknown_operation",
        initial_content="line 1\nline 2\nline 3\n",
        changes=dedent("""\
            @ MODIFY
            
            line 1
            new line
        """),
        expected_error="not associated with an operation",
    ),
    # Multiple @@AFTER sections
    MergeErrorTestCase(
        name="multiple_after_sections",
        initial_content="line 1\nline 2\nline 3\n",
        changes=dedent("""\
            @ UPDATE
            
            @@ BEFORE
            line 1
            @@ AFTER
            new line 1
            @@ AFTER
            another new line 1
        """),
        expected_error="UPDATE chunk cannot have multiple @@AFTER sections",
    ),
    # Overlapping chunks
    MergeErrorTestCase(
        name="overlapping_chunks",
        initial_content="line 1\nline 2\nline 3\nline 4\n",
        changes=dedent("""\
            @ UPDATE
            
            @@ BEFORE
            line 1
            line 2
            @@ AFTER
            new line 1
            new line 2
            
            @ UPDATE
            
            @@ BEFORE
            line 2
            line 3
            @@ AFTER
            another new line 2
            another new line 3
        """),
        expected_error="Invalid chunk order",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_merge_function(test_case):
    """Test successful merge operations using the defined test cases."""
    # Apply the merge
    # Note: No need to manually split the changes string, as the merge function now does that
    result = merge(test_case.initial_content, test_case.changes)

    # Verify the merge was applied correctly
    if result != test_case.expected_output:
        # Create a detailed error message with actual and expected content
        error_msg = f"\nTest case: '{test_case.name}'\n"
        error_msg += f"\nACTUAL OUTPUT (repr):\n{repr(result)}\n"
        error_msg += f"\nEXPECTED OUTPUT (repr):\n{repr(test_case.expected_output)}\n"
        
        # Show line-by-line comparison for debugging
        error_msg += "\nLINE-BY-LINE COMPARISON:\n"
        actual_lines = result.split('\n')
        expected_lines = test_case.expected_output.split('\n')
        
        # Calculate max line count for iteration
        max_lines = max(len(actual_lines), len(expected_lines))
        
        for i in range(max_lines):
            if i < len(actual_lines) and i < len(expected_lines):
                if actual_lines[i] != expected_lines[i]:
                    error_msg += f"Line {i+1}: MISMATCH\n"
                    error_msg += f"  Actual:   '{actual_lines[i]}'\n"
                    error_msg += f"  Expected: '{expected_lines[i]}'\n"
            elif i < len(actual_lines):
                error_msg += f"Line {i+1}: EXTRA in actual\n"
                error_msg += f"  Actual:   '{actual_lines[i]}'\n"
                error_msg += f"  Expected: <no line>\n"
            else:  # i < len(expected_lines)
                error_msg += f"Line {i+1}: MISSING in actual\n"
                error_msg += f"  Actual:   <no line>\n"
                error_msg += f"  Expected: '{expected_lines[i]}'\n"
        
        # Include test case input information
        error_msg += f"\nINITIAL CONTENT (repr):\n{repr(test_case.initial_content)}\n"
        error_msg += f"\nCHANGES (repr):\n{repr(test_case.changes)}\n"
        
        assert result == test_case.expected_output, error_msg


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_merge_errors(test_case):
    """Test error conditions in merge operations using the defined error test cases."""
    # Expect a ValueError when applying the merge
    with pytest.raises(ValueError) as excinfo:
        # Note: No need to manually split the changes string, as the merge function now does that
        merge(test_case.initial_content, test_case.changes)

    # Verify the error message contains the expected text
    error_message = str(excinfo.value)
    if test_case.expected_error not in error_message:
        # Create a detailed error message
        error_msg = f"\nTest case: '{test_case.name}'\n"
        error_msg += f"\nACTUAL ERROR MESSAGE:\n{error_message}\n"
        error_msg += f"\nEXPECTED TO CONTAIN:\n{test_case.expected_error}\n"
        error_msg += f"\nINITIAL CONTENT (repr):\n{repr(test_case.initial_content)}\n"
        error_msg += f"\nCHANGES (repr):\n{repr(test_case.changes)}\n"
        
        assert test_case.expected_error in error_message, error_msg
