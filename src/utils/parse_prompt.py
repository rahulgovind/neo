"""
Utility functions for loading and interpolating prompt templates.
"""

import os
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

def load_prompt(prompt_path: str) -> str:
    """
    Load a prompt template from a file.
    
    Args:
        prompt_path: Path to the prompt template file
        
    Returns:
        String containing the prompt template
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading prompt from {prompt_path}: {e}")
        raise

def interpolate_prompt(template: str, variables: Dict[str, Any]) -> str:
    """
    Interpolate variables into a prompt template.
    
    Variables in the template should be in the format ✿variable_name✿
    
    Args:
        template: Prompt template with placeholders
        variables: Dictionary mapping variable names to values
        
    Returns:
        Interpolated prompt string
    """
    result = template
    for key, value in variables.items():
        placeholder = f"✿{key}✿"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
        else:
            logger.warning(f"Placeholder {placeholder} not found in template")
    
    return result

def load_and_interpolate_prompt(prompt_path: str, variables: Dict[str, Any]) -> str:
    """
    Load a prompt template from a file and interpolate variables.
    
    Args:
        prompt_path: Path to the prompt template file
        variables: Dictionary mapping variable names to values
        
    Returns:
        Interpolated prompt string
    """
    template = load_prompt(prompt_path)
    return interpolate_prompt(template, variables)