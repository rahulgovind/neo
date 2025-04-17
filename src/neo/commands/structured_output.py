"""
NeoFind command implementation.

This module provides the NeoFindCommand class for finding files based on name and type.
"""

"""
Implements the 'find' command for searching files within the workspace."""

import os
import re
import json
import logging
import subprocess
import textwrap
import jsonschema
from typing import Dict, Any, Optional, List

from src.neo.shell.command import Command, CommandTemplate, CommandParameter
from src.neo.session import Session
from src.neo.core.messages import CommandResult

# Configure logging
logger = logging.getLogger(__name__)


class StructuredOutput(Command):
    """
    Command used to output structured data.
    """

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="structured_output",
            description=textwrap.dedent(
                """
                Command used to output structured data.
                
                The command outputs structured data based on the specified criteria.
                """
            ),
            examples=textwrap.dedent(
                """
                ▶output --schema "int" ｜1■
                ✅Successfully processed output.■
                
                ▶output --schema "struct<x: int, y: str, z: array<float>>" ｜{"x": 1, "y": "test", "z": [1.0, 2.0]}■
                ✅Successfully processed output.■
                """
            ),
            parameters=[
                CommandParameter(
                    name="schema",
                    description="Expected schema for the output",
                    required=True,
                    is_positional=True,
                ),
            ],
            requires_data=True,
        )

    def _convert_to_json_schema(self, ddl_schema: str) -> dict:
        """
        Convert DDL-style schema to JSON schema.
        """
        ddl_schema = ddl_schema.strip()
        result = self._parse_type(ddl_schema)
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **result
        }
        
    def _parse_type(self, type_str: str) -> dict:
        """
        Parse a type string and return corresponding JSON schema part.
        """
        type_str = type_str.strip()
        
        # Handle arrays
        array_match = re.match(r"array\s*<(.+)>", type_str)
        if array_match:
            item_type = array_match.group(1).strip()
            return {
                "type": "array",
                "items": self._parse_type(item_type)
            }
            
        # Handle structs
        struct_match = re.match(r"struct\s*<(.+)>", type_str)
        if struct_match:
            fields_str = struct_match.group(1)
            properties = {}
            required = []
            
            # Parse field definitions with handling for nested structs
            # Split by commas, but account for nested structs that might have commas inside
            # This is a simplified approach for basic testing
            depth = 0
            current_field = ""
            fields = []
            
            for char in fields_str + ",":  # Add trailing comma to handle the last field
                if char == '<':
                    depth += 1
                    current_field += char
                elif char == '>':
                    depth -= 1
                    current_field += char
                elif char == ',' and depth == 0:
                    if current_field.strip():
                        fields.append(current_field.strip())
                    current_field = ""
                else:
                    current_field += char
            
            # Process each field
            for field in fields:
                if not field.strip():
                    continue
                parts = field.split(':', 1)
                if len(parts) == 2:
                    field_name = parts[0].strip()
                    field_type = parts[1].strip()
                    properties[field_name] = self._parse_type(field_type)
                    required.append(field_name)
                else:
                    raise ValueError(f"Invalid field format: {field}")
                
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
        
        # Handle primitive types
        primitive_types = {
            "int": {"type": "integer"},
            "integer": {"type": "integer"},
            "long": {"type": "integer"},
            "float": {"type": "number"},
            "double": {"type": "number"},
            "decimal": {"type": "number"},
            "string": {"type": "string"},
            "str": {"type": "string"},
            "char": {"type": "string"},
            "varchar": {"type": "string"},
            "text": {"type": "string"},
            "bool": {"type": "boolean"},
            "boolean": {"type": "boolean"},
            "null": {"type": "null"},
            "timestamp": {"type": "string", "format": "date-time"},
            "date": {"type": "string", "format": "date"},
        }
        
        if type_str.lower() in primitive_types:
            return primitive_types[type_str.lower()]
            
        # Unknown type
        raise ValueError(f"Unknown type format: {type_str}")

    def process(
        self, session: Session, args: Dict[str, Any], data: Optional[str] = None
    ) -> CommandResult:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            session: Application session
            args: Dictionary of parameter names to their values
            data: Optional data string 

        Returns:
            CommandResult with output validation results
        """
        # Get schema from args
        schema_str = args.get("schema")
        if not schema_str:
            logger.error("Schema not provided to output command")
            return CommandResult(success=False, content="Schema argument is required")
            
        # Check if data is provided
        if not data:
            logger.error("No data provided to validate")
            return CommandResult(success=False, content="No data provided to validate")
            
        try:
            # Convert DDL schema to JSON schema
            json_schema = self._convert_to_json_schema(schema_str)
            
            # Handle primitive types directly without using json.loads
            if json_schema["type"] in ["string", "integer", "number", "boolean"]:
                return self._process_primitive_type(data, json_schema)
            
            # For complex types (objects, arrays), use json.loads
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON data: {e}")
                return CommandResult(success=False, content=f"Invalid JSON data: {e}")

            # Validate data against schema
            try:
                jsonschema.validate(instance=parsed_data, schema=json_schema)
                return CommandResult(
                    success=True,
                    content="Successfully processed output.",
                    result=parsed_data
                )
            except jsonschema.exceptions.ValidationError as e:
                logger.error(f"Validation error: {e}")
                return CommandResult(success=False, content=f"Validation error: {e.message}")
                
        except ValueError as e:
            logger.error(f"Schema conversion error: {e}")
            return CommandResult(success=False, content=f"Schema conversion error: {e}")
    
    def _process_primitive_type(self, data: str, schema: dict) -> CommandResult:
        """
        Process and validate data for primitive types.
        
        Args:
            data: The input data as a string
            schema: The JSON schema to validate against
            
        Returns:
            CommandResult with the validation result
        """
        try:
            schema_type = schema["type"]
            
            # Convert string to appropriate type based on schema
            if schema_type == "string":
                parsed_data = data  # Keep as string
            elif schema_type == "integer":
                try:
                    parsed_data = int(data)
                except ValueError:
                    return CommandResult(
                        success=False, 
                        content=f"Invalid integer format: '{data}'"
                    )
            elif schema_type == "number":
                try:
                    parsed_data = float(data)
                except ValueError:
                    return CommandResult(
                        success=False, 
                        content=f"Invalid number format: '{data}'"
                    )
            elif schema_type == "boolean":
                if data.lower() in ["true", "yes", "1"]:
                    parsed_data = True
                elif data.lower() in ["false", "no", "0"]:
                    parsed_data = False
                else:
                    return CommandResult(
                        success=False, 
                        content=f"Invalid boolean value: '{data}'. Expected true/false, yes/no, or 1/0."
                    )
            else:
                # This shouldn't happen due to the caller's check, but just in case
                return CommandResult(
                    success=False, 
                    content=f"Unsupported primitive type: {schema_type}"
                )
                
            # Validate data against schema
            try:
                jsonschema.validate(instance=parsed_data, schema=schema)
                return CommandResult(
                    success=True,
                    content="Successfully processed output.",
                    result=parsed_data
                )
            except jsonschema.exceptions.ValidationError as e:
                logger.error(f"Schema validation error: {e}")
                return CommandResult(
                    success=False, 
                    content=f"Validation error: {e.message}"
                )
                
        except Exception as e:
            logger.error(f"Unexpected error processing primitive type: {e}")
            return CommandResult(
                success=False, 
                content=f"Error processing data: {e}"
            )