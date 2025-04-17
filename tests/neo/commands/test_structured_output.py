"""
Unit tests for the StructuredOutput command class.

This test validates the StructuredOutput command functionality:
1. Validating data against simple schemas
2. Validating complex nested schemas
3. Handling invalid schemas
4. Handling invalid data
"""

import logging
import pytest
import re
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

from src.neo.session import Session
from src.neo.core.constants import COMMAND_END, STDIN_SEPARATOR
from src.neo.core.messages import CommandResult
from src.neo.commands.structured_output import StructuredOutput

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class StructuredOutputTestCase:
    """Data class representing a test case for structured output validation."""

    name: str
    schema: str  # The schema string
    data: str  # The data to validate
    expected_output: List[str]  # List of strings that should be in the output
    expected_not_in_output: Optional[List[str]] = None  # List of strings that should NOT be in the output
    expected_success: bool = True  # Whether the command is expected to succeed

    def __post_init__(self):
        if self.expected_not_in_output is None:
            self.expected_not_in_output = []


@dataclass
class StructuredOutputInternalTestCase:
    """Data class representing a test case for internal methods of StructuredOutput."""

    name: str
    schema: str  # The schema string to parse
    expected_json_schema: Dict[str, Any]  # Expected JSON schema result


# Define test cases for the full command
test_cases = [
    # Basic integer validation
    StructuredOutputTestCase(
        name="validate_integer",
        schema="int",
        data="42",
        expected_output=["Successfully processed output"],
        expected_success=True,
    ),
    # String validation
    StructuredOutputTestCase(
        name="validate_string",
        schema="str",
        data="hello world",
        expected_output=["Successfully processed output"],
        expected_success=True,
    ),
    # Array validation
    StructuredOutputTestCase(
        name="validate_array",
        schema="array<int>",
        data="[1, 2, 3, 4, 5]",
        expected_output=["Successfully processed output"],
        expected_success=True,
    ),
    # Complex struct validation
    StructuredOutputTestCase(
        name="validate_struct",
        schema="struct<id: int, name: str, scores: array<float>>",
        data='{"id": 1, "name": "test", "scores": [98.5, 87.0, 92.3]}',
        expected_output=["Successfully processed output"],
        expected_success=True,
    ),
    # Nested struct validation
    StructuredOutputTestCase(
        name="validate_nested_struct",
        schema="struct<id: int, user: struct<name: str, email: str>, tags: array<str>>",
        data='{"id": 1, "user": {"name": "John Doe", "email": "john@example.com"}, "tags": ["developer", "python"]}',
        expected_output=["Successfully processed output"],
        expected_success=True,
    ),
    # Invalid data type - expect failure
    StructuredOutputTestCase(
        name="invalid_data_type",
        schema="int",
        data='"not an integer"',
        expected_output=["Invalid integer format"],
        expected_not_in_output=["Successfully processed"],
        expected_success=False,
    ),
    # Missing required field - expect failure
    StructuredOutputTestCase(
        name="missing_required_field",
        schema="struct<id: int, name: str>",
        data='{"id": 1}',
        expected_output=["Validation error", "name"],
        expected_not_in_output=["Successfully processed"],
        expected_success=False,
    ),
    # Invalid JSON data - expect failure
    StructuredOutputTestCase(
        name="invalid_json_data",
        schema="int",
        data="not valid json",
        expected_output=["Invalid integer format"],
        expected_not_in_output=["Successfully processed"],
        expected_success=False,
    ),
    # Unknown schema type - expect failure
    StructuredOutputTestCase(
        name="unknown_schema_type",
        schema="unknown_type",
        data='"test"',
        expected_output=["Schema conversion error", "Unknown type format"],
        expected_not_in_output=["Successfully processed"],
        expected_success=False,
    ),
]

# Define test cases for internal schema conversion
internal_test_cases = [
    # Test integer conversion
    StructuredOutputInternalTestCase(
        name="convert_integer",
        schema="int",
        expected_json_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "integer"
        },
    ),
    # Test string conversion
    StructuredOutputInternalTestCase(
        name="convert_string",
        schema="str",
        expected_json_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "string"
        },
    ),
    # Test array conversion
    StructuredOutputInternalTestCase(
        name="convert_array",
        schema="array<int>",
        expected_json_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {"type": "integer"}
        },
    ),
    # Test struct conversion
    StructuredOutputInternalTestCase(
        name="convert_struct",
        schema="struct<id: int, name: str>",
        expected_json_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"}
            },
            "required": ["id", "name"]
        },
    ),
    # Test nested struct conversion
    StructuredOutputInternalTestCase(
        name="convert_nested_struct",
        schema="struct<user: struct<name: str, email: str>, active: bool>",
        expected_json_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    },
                    "required": ["name", "email"]
                },
                "active": {"type": "boolean"}
            },
            "required": ["user", "active"]
        },
    ),
    # Test nested array conversion
    StructuredOutputInternalTestCase(
        name="convert_nested_array",
        schema="array<struct<id: int, name: str>>",
        expected_json_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                },
                "required": ["id", "name"]
            }
        },
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_structured_output_command(test_case):
    """Test the structured_output command functionality using the defined test cases."""
    # Create a test session
    ctx = Session.builder().session_id("test_session_id").workspace("/tmp").initialize()
    
    # Create the command with the schema and data
    command_input = f"structured_output \"{test_case.schema}\"{STDIN_SEPARATOR}{test_case.data}"
    
    # Execute the command
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify success/failure status
    assert result.success == test_case.expected_success, f"Command {'should' if test_case.expected_success else 'should not'} execute successfully for test case {test_case.name}. Result: {result.content}"
    
    # Check for expected output strings
    for expected_str in test_case.expected_output:
        # Handle regex patterns
        if expected_str.startswith("^"):
            assert any(
                re.match(expected_str, line)
                for line in result.content.split("\n")
                if line
            ), f"Regex pattern '{expected_str}' not found in output for test case {test_case.name}"
        else:
            assert (
                expected_str in result.content
            ), f"Expected string '{expected_str}' not found in output for test case {test_case.name}: {result.content}"
    
    # Check that unwanted strings are not in the output
    for not_expected_str in test_case.expected_not_in_output:
        # Handle regex patterns
        if not_expected_str.startswith("^"):
            assert not any(
                re.match(not_expected_str, line)
                for line in result.content.split("\n")
                if line
            ), f"Regex pattern '{not_expected_str}' found in output but should not be for test case {test_case.name}"
        else:
            assert (
                not_expected_str not in result.content
            ), f"String '{not_expected_str}' found in output but should not be for test case {test_case.name}: {result.content}"
    
    # Check result field when command was successful
    if result.success:
        assert result.result is not None, f"Result field should not be None for successful command in test case {test_case.name}"
        
        # For primitive types, verify the value matches the expected type and value
        if test_case.schema == "int":
            assert isinstance(result.result, int), f"Result should be an integer for test case {test_case.name}"
            if test_case.name == "validate_integer":
                assert result.result == 42, f"Expected result value 42 for test case {test_case.name}, got {result.result}"
        
        elif test_case.schema == "str":
            assert isinstance(result.result, str), f"Result should be a string for test case {test_case.name}"
            if test_case.name == "validate_string":
                assert result.result == "hello world", f"Expected result value 'hello world' for test case {test_case.name}, got {result.result}"
        
        # For complex types, verify structure and key fields
        elif test_case.name == "validate_struct":
            assert isinstance(result.result, dict), f"Result should be a dict for test case {test_case.name}"
            assert "id" in result.result, f"Expected 'id' field in result for test case {test_case.name}"
            assert "name" in result.result, f"Expected 'name' field in result for test case {test_case.name}"
            assert "scores" in result.result, f"Expected 'scores' field in result for test case {test_case.name}"
            assert isinstance(result.result["scores"], list), f"'scores' should be a list in test case {test_case.name}"
        
        elif test_case.name == "validate_array":
            assert isinstance(result.result, list), f"Result should be a list for test case {test_case.name}"
            assert len(result.result) == 5, f"Expected 5 items in result for test case {test_case.name}, got {len(result.result)}"
            assert all(isinstance(x, int) for x in result.result), f"All items should be integers for test case {test_case.name}"


@pytest.mark.parametrize("test_case", internal_test_cases, ids=lambda tc: tc.name)
def test_schema_conversion(test_case):
    """Test the internal _convert_to_json_schema method."""
    command = StructuredOutput()
    result = command._convert_to_json_schema(test_case.schema)
    
    # Convert both to JSON strings for easier comparison
    expected_json = json.dumps(test_case.expected_json_schema, sort_keys=True)
    actual_json = json.dumps(result, sort_keys=True)
    
    assert expected_json == actual_json, f"Schema conversion for '{test_case.schema}' did not match expected result.\nExpected: {expected_json}\nActual: {actual_json}"


def test_missing_schema():
    """Test the command behavior when schema is missing."""
    # Create a test session
    ctx = Session.builder().session_id("test_session_id").workspace("/tmp").initialize()
    
    # Execute the command without a schema
    command_input = f"structured_output{STDIN_SEPARATOR}42"
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify the command failed
    assert not result.success, "Command should fail when schema is missing"
    assert "the following arguments are required: schema" in result.content


def test_missing_data():
    """Test the command behavior when data is missing."""
    # Create a test session
    ctx = Session.builder().session_id("test_session_id").workspace("/tmp").initialize()
    
    # Execute the command without data
    command_input = "structured_output \"int\""
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify the command failed
    assert not result.success, "Command should fail when data is missing"
    assert "requires data" in result.content


def test_direct_command_execution():
    """Test direct execution of the command with valid input."""
    # Create instance and test directly
    command = StructuredOutput()
    session = Session.builder().session_id("test_session_id").workspace("/tmp").initialize()
    
    # Test with valid input
    result = command.process(session, {"schema": "int"}, "42")
    assert result.success
    assert "Successfully processed output" in result.content
    assert result.result == 42, "Expected result to be integer 42"
    
    # Test with invalid schema
    result = command.process(session, {"schema": "unknown_type"}, "42")
    assert not result.success
    assert "Schema conversion error" in result.content
    assert result.result is None, "Result should be None for failed validation"
    
    # Test with invalid data
    result = command.process(session, {"schema": "int"}, "not_an_integer")
    assert not result.success
    assert "Invalid integer format" in result.content
    assert result.result is None, "Result should be None for failed validation"
    
    # Test string primitive type
    result = command.process(session, {"schema": "str"}, "hello world")
    assert result.success
    assert "Successfully processed output" in result.content
    assert result.result == "hello world", "Expected result to be string 'hello world'"
    
    # Test boolean primitive type
    result = command.process(session, {"schema": "boolean"}, "true")
    assert result.success
    assert "Successfully processed output" in result.content
    assert result.result is True, "Expected result to be boolean True"
    
    # Test number primitive type
    result = command.process(session, {"schema": "float"}, "3.14")
    assert result.success
    assert "Successfully processed output" in result.content
    assert result.result == 3.14, "Expected result to be float 3.14"
