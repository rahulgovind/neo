"""
End-to-end test for the Model class using a real LLM.

This test validates the complete function calling flow with an actual LLM:
1. Sending a message requesting a function call
2. Extracting function arguments from the response
3. Sending function results back to the LLM
4. Verifying the LLM can correctly process the results
"""

import os
import unittest
import logging

from src.core.model import Model, Message, TextBlock, FunctionResult

# Configure logging for the test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestModelE2E(unittest.TestCase):
    """End-to-end test for Model's function calling capabilities using a real LLM."""
    
    @unittest.skipIf(
        not (os.environ.get("API_KEY") and os.environ.get("RUN_E2E_TESTS", True)), 
        "Skipping E2E test: Set API_KEY and RUN_E2E_TESTS env vars to run"
    )
    def test_function_calling_flow(self):
        """
        Test the complete function calling flow with an actual LLM.
        
        This test requires API_KEY environment variable to be set.
        Set RUN_E2E_TESTS=1 to run this test.
        """
        try:
            # Initialize the model - this will use the actual API credentials
            model = Model()
            logger.info("Model initialized for E2E test")
            
            # Create a system message with detailed instructions on function call format
            system_message = Message(role="system")
            system_message.add_content(TextBlock(
                "You are a helpful assistant that can call functions. "
                "When asked to call a function, you should do so with the exact arguments provided. "
                "Format your function calls using this exact syntax:\n\n"
                "✿FUNCTION✿: function_name\n"
                "✿ARGS✿: {\"arg1\": value1, \"arg2\": value2}\n"
                "✿END FUNCTION✿\n\n"
                "The ARGS section must contain a valid JSON object with the function arguments. "
                "Do not add any explanation inside the function call block. "
                "You may provide explanations before or after the function call block."
            ))
            
            # Create a user message asking the LLM to call a specific function
            user_message = Message(role="user")
            user_message.add_content(TextBlock(
                "Please call function_x with arguments a=1111 and b=2222. "
                "Format the arguments as a proper JSON object."
            ))
            
            # Send the messages to the LLM
            logger.info("Sending initial request to LLM")
            response = model.process([system_message, user_message])
            
            # Log the complete response for debugging
            logger.info(f"Received response from LLM: {response}")
            
            # Check if response has function calls
            self.assertTrue(
                response.has_function_calls(), 
                "LLM response should contain function calls"
            )
            
            # Extract the function calls
            function_calls = response.get_function_calls()
            self.assertEqual(
                len(function_calls), 1,
                "Expected exactly one function call in the response"
            )
            
            # Verify function name and arguments
            function_call = function_calls[0]
            self.assertEqual(
                function_call.name, "function_x",
                f"Expected function_x but got {function_call.name}"
            )
            self.assertIn(
                "a", function_call.args,
                "Expected argument 'a' in function call"
            )
            self.assertIn(
                "b", function_call.args,
                "Expected argument 'b' in function call"
            )
            self.assertEqual(
                function_call.args["a"], 1111,
                f"Expected a=1111 but got a={function_call.args['a']}"
            )
            self.assertEqual(
                function_call.args["b"], 2222,
                f"Expected b=2222 but got b={function_call.args['b']}"
            )
            
            logger.info("Function call validation passed")
            
            # Now create a message with the function result
            function_result_message = Message(role="function")
            function_result_message.add_content(FunctionResult("3333"))
            
            # Create a follow-up user message
            second_user_message = Message(role="user")
            second_user_message.add_content(TextBlock(
                "The result from function_x was 3333. Please add 1 to this result and tell me the answer."
            ))
            
            # Create a new conversation with all previous messages plus the new ones
            all_messages = [
                system_message, 
                user_message, 
                response,  
                function_result_message,
                second_user_message
            ]
            
            # Send the follow-up conversation to the LLM
            logger.info("Sending follow-up request to LLM")
            second_response = model.process(all_messages)
            
            # Extract the text from the response
            response_text = "".join(
                str(block.text) for block in second_response.content 
                if hasattr(block, 'text')
            )
            
            logger.info(f"Follow-up response text: {response_text}")
            
            # Verify the response contains the expected calculation result
            self.assertIn(
                "3334", response_text,
                "LLM response should contain the value 3334 (3333 + 1)"
            )
            
            logger.info("End-to-end test successfully completed")
            
        except Exception as e:
            logger.error(f"E2E test failed: {e}")
            raise