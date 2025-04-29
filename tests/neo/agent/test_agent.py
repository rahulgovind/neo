import os
import uuid
import shutil
import pytest
from typing import List, Iterator

from src.neo.core.messages import Message, TextBlock, StructuredOutput
from src.neo.agent.agent import Agent
from src.neo.session import Session
from textwrap import dedent


def test_agent_math_structured_output():
    """Test that Agent can compute 2+2 and return a structured output."""
    session = Session.builder().initialize()

    # Create agent with ephemeral=True to avoid saving state
    agent = Agent(session=session, ephemeral=True)

    # Define the prompt for asking for a structured output calculation
    prompt = "Calculate 2+2 and return only the result as structured output. The output should be an integer."

    # Process the user message
    responses = list(agent.process(prompt))

    # Verify we got a response
    assert len(responses) > 0, "Agent should return at least one response"

    # Get the last response (to account for potential command executions)
    last_response = responses[-1]
    
    # Get the structured output
    output = last_response.structured_output()
    
    # Validate the value is 4
    assert int(output.value) == 4, f"Expected 4, got {output.value}"


def test_agent_state_persistence():
    session = Session.builder().initialize()
    # Create agent with ephemeral=False to save state to disk
    agent = Agent(session=session, ephemeral=False)

    # Define the prompt for asking for a structured output calculation
    list(agent.process("Calculate 2+2 and return only the result as an integer structured output."))

    # Create a new agent instance to load state from disk
    agent = Agent(session=session, ephemeral=False)
    result = list(
        agent.process(
            "Add 2 to the previous result and return it as an integer structured output"
        )
    )[-1]

    # Get the structured output
    output = result.structured_output()
    
    # Validate the value is 6
    assert int(output.value) == 6, f"Expected 6, got {output.value}"

def get_output(agent, message):
    response = list(agent.process(message))[-1]
    assert response.structured_output() is not None
    return response.structured_output().value

def format_agent_state(agent):
    return "\n\n".join([
        f"{msg.role}: {msg.model_text()}"
        for msg in agent.state.messages
    ])

def test_agent_checkpoint():
    """Test that the agent's checkpointing logic works correctly in-memory."""
    session = Session.builder().initialize()

    # Create agent with ephemeral=True but with minimal checkpoint thresholds
    # to force checkpointing even with few messages
    agent = Agent(
        session=session,
        ephemeral=True,
        configuration={
            "head_truncation.trigger_threshold": "0",  # Always trigger truncation
            "head_truncation.retention": "0",  # Keep minimal messages
            "checkpoint_interval": "1",  # Checkpoint after every message
        },
    )

    # First calculation

    print("====================  First calculation ====================")
    assert get_output(
            agent,
            "Calculate x^2 for numbers 2, 4, 7, 9 and 11 and return them as a structured outputs. "
            "Return them one by one. Next result N + 1 only after I have acknowledge result N"
        ) == 4

    # The previous state should be checkpointed but still available in memory
    # This verifies that in-memory checkpointing works without saving to disk
    print("====================  Second calculation ====================")
    result = get_output(agent, "continue")
    assert result == 16

    print("====================  Third calculation ====================")
    result = get_output(agent, "continue")
    assert result == 49

    print("====================  Fourth calculation ====================")
    result = get_output(agent, "continue")
    assert result == 81

    print("====================  Fifth calculation ====================")
    result = get_output(agent, "continue")
    assert result == 121

    print("====================  First calcuation. x^3 ====================")
    assert get_output(
            agent,
            "Calculate x^3 for numbers 2, 4, and 7 and return them as a structured outputs. "
            "Return them one by one. Next result N + 1 only after I have acknowledge result N"
        ) == 8

    print("====================  Second calcuation. x^3 ====================")
    assert get_output(agent, "continue") == 64

    print("====================  Third calcuation. x^3 ====================")
    assert get_output(agent, "continue") == 343


def test_agent_simple_code_fix():
    session = Session.builder().initialize()
    agent = session.agent

    # Create a python file in the session workspace which
    # calculates the 100th fibonacci number.
    # The code has a syntax error which must be fixed by the agent.
    fib_file_path = os.path.join(session.workspace, "fibonacci.py")

    # Write a file with a syntax error (missing colon after function definition)
    incorrect_code = dedent(
        """
        def calculate_fibonacci(n)
            if n <= 0:
                return 0
            elif n == 1
                return 1
            else:
                return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

        # Calculate the 100th Fibonacci number
        result = calculate_fibonacci(100
        print(f"The 100th Fibonacci number is: {result}")
        """
    )

    correct_code = dedent(
        """
        def calculate_fibonacci(n):
            if n <= 0:
                return 0
            elif n == 1:
                return 1
            else:
                return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

        # Calculate the 100th Fibonacci number
        result = calculate_fibonacci(100)
        print(f"The 100th Fibonacci number is: {result}")
        """
    )

    with open(fib_file_path, "w") as f:
        f.write(incorrect_code)

    # Process user message asking to fix the syntax error
    prompt = f"The file fibonacci.py has a syntax error. Can you fix it? Do not change anything else and do not try to run the script."
    list(agent.process(prompt))

    # Verify the file was modified and syntax error fixed
    assert os.path.exists(fib_file_path), "File should still exist after fix"

    # Read the fixed file
    with open(fib_file_path, "r") as f:
        fixed_code = f.read()

    assert fixed_code == correct_code
