"""
Core function module defining the Function interface and registry.

This module provides the foundation for all callable functions in the system:
- Abstract Function interface that all concrete functions must implement
- FunctionRegistry that manages function registration and invocation
- Example class for storing function usage examples
"""

import os
import importlib
import inspect
import pkgutil
import logging
import textwrap
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Union, Optional, Type

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Example:
    """Example usage of a function with inputs and expected outputs."""
    
    description: str
    args: Dict[str, Any]
    result: Any
    
    def to_function_call_format(self) -> str:
        """
        Convert the example to the formatted string representation of a function call.
        
        Returns:
            String representation of the function call as it would appear during execution
        """
        args_str = str(self.args).replace("'", '"')
        return f"✿FUNCTION✿: <function_name>\n✿ARGS✿: {args_str}\n✿END FUNCTION✿"
    
    def to_function_result_format(self) -> str:
        """
        Convert the example result to the formatted string representation of a function result.
        
        Returns:
            String representation of the function result as it would appear during execution
        """
        return f"✿RESULT✿: {self.result}"


class Function(ABC):
    """
    Abstract base class for functions callable by the LLM.
    """
    
    @abstractmethod
    def name(self) -> str:
        """Returns the unique identifier for this function."""
        pass
    
    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """
        Returns a structured description of the function and its parameters.
        
        Returns:
            Dict containing name, description, and parameters schema
        """
        pass
    
    @abstractmethod
    def invoke(self, args: Dict[str, Any]) -> Any:
        """
        Executes the function with the provided arguments.
        
        Raises:
            ValueError: If required arguments are missing or invalid
        """
        pass
    
    def examples(self) -> List[Example]:
        """
        Returns a list of usage examples for this function.
        
        Examples help the LLM understand how to use the function and what
        to expect in return.
        
        Returns:
            List of Example objects demonstrating function usage
        """
        return []  # Default implementation returns an empty list


class FunctionRegistry:
    """
    Registry for functions that can be invoked by the LLM.
    """
    
    def __init__(self):
        """Initializes an empty registry."""
        self.functions = {}
    
    def add(self, function: Function) -> None:
        """Registers a function in the registry."""
        name = function.name()
        if name in self.functions:
            logger.warning(f"Replacing existing function '{name}' in registry")
        else:
            logger.info(f"Registering function '{name}' in registry")
            
        self.functions[name] = function
    
    def describe(self, name: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Gets the description for a specific function or all functions.
        
        Raises:
            ValueError: If the specified function doesn't exist
        """
        if name:
            if name not in self.functions:
                logger.error(f"Function '{name}' not found in registry")
                raise ValueError(f"Function '{name}' not found")
            return self.functions[name].describe()
        else:
            return [func.describe() for func in self.functions.values()]
    
    def get_examples(self, name: str) -> List[Example]:
        """
        Gets usage examples for a specific function.
        
        Args:
            name: Name of the function to get examples for
            
        Returns:
            List of Example objects for the function
            
        Raises:
            ValueError: If the specified function doesn't exist
        """
        if name not in self.functions:
            logger.error(f"Function '{name}' not found in registry")
            raise ValueError(f"Function '{name}' not found")
        
        return self.functions[name].examples()
    
    def get_formatted_info(self) -> str:
        """
        Build a formatted string with function information for the LLM.
        
        This includes:
        - Function descriptions as JSON
        - Example function calls and results
        
        Returns:
            Formatted string with function information
        """
        # Check if we have any functions registered
        if not self.functions:
            logger.debug("No functions registered, returning empty function info")
            return ""
            
        try:
            # Get function descriptions as a JSON string
            function_descriptions = json.dumps(self.describe(), indent=2)
            
            # Collect examples for all functions
            examples_text = []
            for func_name, func in self.functions.items():
                func_examples = func.examples()
                if func_examples:
                    for i, example in enumerate(func_examples):
                        example_text = f"""
                        Example {i+1} for {func_name} - {example.description}:
                        ✿FUNCTION✿: {func_name}
                        ✿ARGS✿: {json.dumps(example.args, ensure_ascii=False)}
                        ✿END FUNCTION✿
                        
                        ✿RESULT✿: {example.result}
                        """
                        examples_text.append(example_text)
            
            # Build the examples section if we have examples
            examples_section = ""
            if examples_text:
                examples_section = "\nHere are some example function calls:\n\n"
                examples_section += "\n".join(examples_text)
            
            # Load the function calling prompt template and interpolate variables
            template_path = os.path.join("src", "prompts", "function_calling.md")
            from src.utils.parse_prompt import load_and_interpolate_prompt
            
            function_info = load_and_interpolate_prompt(
                template_path,
                {
                    "function_descriptions": function_descriptions,
                    "examples_text": examples_section
                }
            )
            
            logger.debug(f"Function descriptions prepared for {len(self.functions)} functions")
            return function_info
            
        except Exception as e:
            logger.error(f"Error building function information: {e}")
            raise RuntimeError(f"Failed to build function information: {e}") from e
    
    def invoke(self, name: str, args: Dict[str, Any]) -> Any:
        """
        Invokes a function with the given arguments.
        
        Raises:
            ValueError: If the specified function doesn't exist
        """
        if name not in self.functions:
            logger.error(f"Function '{name}' not found in registry")
            raise ValueError(f"Function '{name}' not found")
        
        logger.info(f"Invoking function '{name}' with args: {args}")
        try:
            result = self.functions[name].invoke(args)
            return result
        except Exception as e:
            # Log the exception but let it propagate up
            logger.error(f"Error invoking function '{name}': {e}")
            raise

    def load_functions_from_module(self, module_name: str, **kwargs) -> None:
        """
        Dynamically discovers and registers all Function subclasses from a module.
        """
        logger.info(f"Loading functions from module: {module_name}")
        try:
            # Import the module
            module = importlib.import_module(module_name)
            
            # Find all Function subclasses in the module
            function_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, Function) and 
                    obj != Function):
                    function_classes.append(obj)
            
            # Register each function
            for function_class in function_classes:
                try:
                    function_instance = function_class(**kwargs)
                    self.add(function_instance)
                    logger.debug(f"Registered function: {function_instance.name()}")
                except Exception as e:
                    logger.error(f"Failed to register function {function_class.__name__}: {e}")
                    
            logger.info(f"Loaded {len(function_classes)} functions from {module_name}")
            
        except Exception as e:
            logger.error(f"Error loading functions from module {module_name}: {e}")
            raise

    def discover_and_load_functions(self, package_name: str, **kwargs) -> None:
        """
        Recursively discovers and loads all Function implementations from a package.
        """
        logger.info(f"Discovering functions in package: {package_name}")
        
        try:
            # Import the package
            package = importlib.import_module(package_name)
            package_path = os.path.dirname(package.__file__)
            function_count = 0
            
            # Walk through all modules in the package
            for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
                full_module_name = f"{package_name}.{module_name}"
                
                if is_pkg:
                    # Recursively process subpackages
                    self.discover_and_load_functions(full_module_name, **kwargs)
                else:
                    # Load functions from this module
                    prev_count = len(self.functions)
                    self.load_functions_from_module(full_module_name, **kwargs)
                    function_count += len(self.functions) - prev_count
            
            logger.info(f"Discovered {function_count} functions in package {package_name}")
            
        except Exception as e:
            logger.error(f"Error discovering functions in package {package_name}: {e}")
            raise