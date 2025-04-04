"""
Update file command implementation.

This module provides the UpdateFile class for updating files based on natural language instructions.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional, List

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.exceptions import FatalError
from src.core.messages import Message, TextBlock
from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)


class UpdateFileCommand(Command):
    """
    Command for updating files based on natural language instructions.
    
    Takes a file path as a parameter and natural language instructions as data,
    then uses the model to read the file and generate updated content based on
    the instructions.
    """
    
    def template(self) -> CommandTemplate:
        """Command template with parameter definitions"""
        return CommandTemplate(
            name="update_file",
            requires_data=True,
            description=textwrap.dedent("""
                Update a file based on natural language instructions.
                Instructions must be explicit and clear for optimal results.
                
                Example:
                ▶update_file path/to/file.py｜Add a docstring to the main function that explains it processes user input■
                ✅File updated successfully■
                
                ▶update_file config.json｜Change the port number in the server section from 8080 to 9000■
                ✅File updated successfully■
            """).strip(),
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to update",
                    required=True,
                    is_positional=True
                )
            ],
            manual=textwrap.dedent("""
                The update_file command modifies an existing file based on natural language instructions.
                
                It reads the current content of the file, processes your instructions, and then
                updates the file with the modified content.
                
                Usage:
                  update_file <path> | <instructions>
                
                Arguments:
                  path       Path to the file to update (required)
                
                Instructions:
                  Provide natural language instructions for how to modify the file.
                  Instructions must be as explicit and clear as possible for optimal results.
                  Specify exactly what needs to be changed, where the changes should be made,
                  and how the code should be modified.
                
                Examples:
                  ▶update_file path/to/file.py｜Add a docstring to the main function■
                  ✅File updated successfully■
                
                  ▶update_file config.json｜Change the port to 9000■
                  ✅File updated successfully■
                
                  ▶update_file src/app.js｜Fix the error in the login function■
                  ❌Error: No such file or directory■
            """).strip()
        )
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the model"""
        return textwrap.dedent("""
            You are a specialized file updating assistant. Your task is to modify a file based on 
            natural language instructions.
            
            1. You have been provided with the current content of a file and instructions for how to update it.
            2. Carefully analyze the file content and understand what changes are requested.
            3. Make only the changes specified in the instructions, preserving everything else.
            4. Use the write_file command to save the updated content.
            5. Be precise and maintain the original formatting and style of the file.
            6. If the instructions are unclear or would result in invalid code/content, explain the issue.
            
            Remember to:
            - Preserve indentation, spacing, and code style
            - Only make the changes specified in the instructions
            - Use the write_file command with the same path to save the updated file
            - If the instructions are ambiguous, ask for clarification before making changes
        """).strip()
    
    def process(self, ctx: Context, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """Process the update file command"""
        # Get the file path from arguments
        file_path = args.get("path")
        if not file_path:
            raise FatalError("No file path provided")
        
        # Get the update instructions from data
        instructions = data
        if not instructions:
            raise FatalError("No update instructions provided")
        
        # Get model and shell from context
        model = ctx.model
        shell = ctx.shell
        
        # First, read the file directly using the shell
        read_result = shell.execute("read_file", parameters={"path": file_path})
        if not read_result.success:
            return f"❌{read_result.error}"
        
        file_content = read_result.result
        
        # Build the initial message with file content and update instructions
        initial_message = (
            f"I need to update the file at '{file_path}' with these instructions: {instructions}.\n\n"
            f"Here is the current content of the file:\n\n{file_content}\n\n"
            f"Please make the necessary changes as specified in the instructions and use the write_file command to save the updated content."
        )
        
        # Create messages
        user_msg = Message(role="user")
        user_msg.add_content(TextBlock(initial_message))
        messages = [user_msg]
        
        # Process the message with the model - only allowing write_file command
        system_prompt = self._get_system_prompt()
        response = model.process(
            system=system_prompt,
            messages=messages,
            commands=["write_file"],
            auto_execute_commands=True
        )
        
        # Check if any write_file command was executed successfully
        for message in messages:
            if message.role == "user" and message.has_command_executions():
                # Check for success message in the results
                if "File written successfully" in message.text:
                    logger.info(f"File update process completed for {file_path}")
                    return f"✅File updated successfully"
        
        logger.info(f"File update process completed for {file_path}")
        # If we got here without finding a successful write, return the model response
        return response.text
