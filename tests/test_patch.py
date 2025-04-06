import os
import pytest
import tempfile
import logging
from textwrap import dedent
from dataclasses import dataclass
from typing import Optional

from src.utils.files import patch

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from src.core.exceptions import FatalError


@dataclass
class PatchTestCase:
    """Data class representing a test case for the patch function."""

    name: str
    initial_content: str
    diff_text: str
    expected_output: str


# Define test cases
test_cases = [
    # Basic patch test - replace one line
    PatchTestCase(
        name="basic_patch",
        initial_content=dedent(
            """
            line 1
            line 2
            line 3
            line 4
            line 5
        """
        ).strip()
        + "\n",
        diff_text=dedent(
            """
            @UPDATE
            BEFORE
            3:line 3
            AFTER
            3:new line 3
        """
        ).strip(),
        expected_output=dedent(
            """
            line 1
            line 2
            new line 3
            line 4
            line 5
        """
        ).strip()
        + "\n",
    ),
    # Deletion test - remove a line
    PatchTestCase(
        name="deletion",
        initial_content=dedent(
            """
            line 1
            line 2
            line 3
            line 4
            line 5
        """
        ).strip()
        + "\n",
        diff_text=dedent(
            """
            @DELETE
            3:line 3
        """
        ).strip(),
        expected_output=dedent(
            """
            line 1
            line 2
            line 4
            line 5
        """
        ).strip()
        + "\n",
    ),
    # Insertion test - add a new line
    PatchTestCase(
        name="insertion",
        initial_content=dedent(
            """
            line 1
            line 2
            line 3
        """
        ).strip()
        + "\n",
        diff_text=dedent(
            """
            @INSERT
            3:new inserted line
        """
        ).strip(),
        expected_output=dedent(
            """
            line 1
            line 2
            new inserted line
            line 3
        """
        ).strip()
        + "\n",
    ),
    # Complex changes test - multiple operations
    PatchTestCase(
        name="complex_changes",
        initial_content="line 1\nline 2\nline 3\nline 4\nline 5\n",
        diff_text=dedent(
            """
            @UPDATE
            BEFORE
            2:line 2
            AFTER
            2:new line 2
            
            @DELETE
            4:line 4
            
            @INSERT
            2:new line 2
            3:extra line
        """
        ).strip(),
        expected_output="line 1\nnew line 2\nextra line\nline 3\nline 5\n",
    ),
    # Empty file test - add content to empty file
    PatchTestCase(
        name="empty_file",
        initial_content="",
        diff_text=dedent(
            """
            @INSERT
            1:new line 1
            2:new line 2
        """
        ).strip(),
        expected_output=dedent(
            """
            new line 1
            new line 2
        """
        ).strip()
        + "\n",
    ),
    # Empty line content test - handling blank lines
    PatchTestCase(
        name="empty_line_content",
        initial_content=dedent(
            """
            Header
            
            The Agent builds on top of the Model:
            
            - Feature 1
            - Feature 2
        """
        ).strip()
        + "\n",
        diff_text=dedent(
            """
            @UPDATE
            BEFORE
            3:The Agent builds on top of the Model:
            AFTER
            3:The Agent builds on top of the Shell:
        """
        ).strip(),
        expected_output=dedent(
            """
            Header
            
            The Agent builds on top of the Shell:
            
            - Feature 1
            - Feature 2
        """
        ).strip()
        + "\n",
    ),
    # Multiple operations test - with all three operation types
    PatchTestCase(
        name="multiple_operations",
        initial_content="line 1\nline 2\nline 3\nline 4\nline 5\n",
        diff_text=dedent(
            """
            @UPDATE
            BEFORE
            1:line 1
            2:line 2
            AFTER
            1:prepended line
            2:new line 1
            3:new line 2
            4:inserted line
            
            @DELETE
            4:line 4
            
            @UPDATE
            BEFORE
            5:line 5
            AFTER
            5:new line 5
            6:appended line
        """
        ).strip(),
        expected_output=dedent(
            """
            prepended line
            new line 1
            new line 2
            inserted line
            line 3
            new line 5
            appended line
        """
        ).strip()
        + "\n",
    ),
]


@dataclass
class PatchErrorTestCase:
    """Data class representing an error test case for the patch function."""

    name: str
    initial_content: Optional[str]
    diff_text: str
    file_path: Optional[str]
    expected_error: str


# Define error test cases
error_test_cases = [
    # File not found test
    PatchErrorTestCase(
        name="file_not_found",
        initial_content=None,
        diff_text=dedent(
            """
            @UPDATE
            BEFORE
            1:line 1
            AFTER
            1:new line 1
        """
        ).strip(),
        file_path="/nonexistent/file.txt",
        expected_error="not found",
    ),
    # Invalid update format test - missing AFTER section
    PatchErrorTestCase(
        name="invalid_update_format",
        initial_content="line 1\nline 2\nline 3\n",
        diff_text=dedent(
            """
            @UPDATE
            BEFORE
            1:line 1
        """
        ).strip(),
        file_path=None,
        expected_error="Invalid UPDATE format",
    ),
    # Invalid line number test
    PatchErrorTestCase(
        name="invalid_line_number",
        initial_content="line 1\nline 2\nline 3\n",
        diff_text=dedent(
            """
            @DELETE
            XYZ:line 1
        """
        ).strip(),
        file_path=None,
        expected_error="Invalid line number",
    ),
    # Unknown section type test
    PatchErrorTestCase(
        name="unknown_section_type",
        initial_content="line 1\nline 2\nline 3\n",
        diff_text=dedent(
            """
            @MODIFY
            1:line 1
            2:new line
        """
        ).strip(),
        file_path=None,
        expected_error="Unknown section type",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_patch_function(test_case):
    """Test successful patch operations using the defined test cases."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Create a file with the initial content
        tmp.write(test_case.initial_content.encode("utf-8"))
        tmp_path = tmp.name

    try:
        # Apply the patch
        result = patch(tmp_path, test_case.diff_text)

        # Verify the patch was applied correctly
        assert (
            result == test_case.expected_output
        ), f"Output for test case '{test_case.name}' does not match expected output"
    finally:
        # Clean up
        os.unlink(tmp_path)


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_patch_errors(test_case):
    """Test error conditions in patch operations using the defined error test cases."""
    tmp_path = None

    # Create a temporary file if initial content is provided
    if test_case.initial_content is not None:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(test_case.initial_content.encode("utf-8"))
            tmp_path = tmp.name

    try:
        # Use specified file path or temp file path
        file_path = test_case.file_path if test_case.file_path else tmp_path

        # Expect a RuntimeError when applying the patch
        with pytest.raises(RuntimeError) as excinfo:
            patch(file_path, test_case.diff_text)

        # Verify the error message contains the expected text
        assert test_case.expected_error in str(
            excinfo.value
        ), f"Error message for test case '{test_case.name}' does not contain expected text"
    finally:
        # Clean up temp file if it was created
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
