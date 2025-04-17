"""
End-to-end test for the Client class using a real LLM.

This test verifies that the Client:
1. Can properly connect to the LLM service
2. Can send messages and receive responses
3. Sets the usage metadata in the response message
"""

import unittest
import logging

from src.neo.client import Client
from src.neo.core.messages import Message, TextBlock
from src.neo.session import Session

from textwrap import dedent

# Configure logging for the test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestClientPromptCache(unittest.TestCase):
    """End-to-end test for Client's basic functionality using a real LLM."""

    # Run this test by default
    @unittest.skipIf(False, "Skipping E2E test")
    def test_cache_control(self):
        """
        Test that the client properly handles cache-control metadata and token caching.

        This test does the following:
        1. Send a first message with cache-control=True
        2. Send a second message that includes the first message and adds a new one
        3. Verify that some tokens were cached in the second response

        Note: This test requires messages to be long enough to meet minimum cacheable
        prompt length (1024 tokens for Claude 3 models).
        """

        session = Session.builder().initialize()
        # Initialize the client
        client = Client(session.shell)
        logger.info("Client initialized for cache control test")

        # Programmatically generate a large list of random 8-letter word to ID mappings
        # to exceed the minimum cacheable prompt length (1024 tokens for Claude 3.7 Sonnet)
        import random
        import string

        def generate_random_word_pairs(num_pairs=2000):
            """
            Generate a list of random 8-letter words mapped to sequential IDs.

            Args:
                num_pairs: Number of word-ID pairs to generate

            Returns:
                tuple: (all_pairs_text, random_word, expected_id)
            """
            # Generate random 8-letter words
            words = []
            for _ in range(num_pairs):
                # Generate two 4-letter segments joined by a hyphen
                segment1 = "".join(random.choices(string.ascii_lowercase, k=4))
                segment2 = "".join(random.choices(string.ascii_lowercase, k=4))
                word = f"{segment1}-{segment2}"
                words.append(word)

            # Create the mapping text
            pairs_text = "Given below is a list of key-value pairs:\n"
            for i, word in enumerate(words, 1):
                pairs_text += f"{word} {i}\n"

            # Select a random word to query
            random_idx = random.randint(0, num_pairs - 1)
            query_word = words[random_idx]
            expected_id = random_idx + 1

            logger.debug(f"Generated {num_pairs} random word pairs")
            logger.debug(
                f"Selected query word: {query_word} with expected ID: {expected_id}"
            )

            return pairs_text, query_word, expected_id

        # Constants for cost calculations
        INPUT_TOKEN_COST = 3.0 * 1e-6
        OUTPUT_TOKEN_COST = 15.0 * 1e-6
        CACHE_READ_DISCOUNT = 0.9 * INPUT_TOKEN_COST
        CACHE_WRITE_DISCOUNT = -0.25 * INPUT_TOKEN_COST

        # Create system message
        system_message = Message(
            role="system",
            content=[
                TextBlock(
                    "You are a helpful assistant that provides concise, accurate responses."
                )
            ],
        )

        # Initialize variables to track across iterations
        messages = [system_message]
        previous_num_input_tokens = 0

        # Run 5 iterations of the test
        NUM_ITERATIONS = 5

        for iteration in range(1, NUM_ITERATIONS + 1):
            # Generate random word pairs for this iteration
            pairs_text, query_word, _ = generate_random_word_pairs(500)

            messages.append(
                Message(
                    role="user",
                    content=[
                        TextBlock(
                            f'{pairs_text}\n\nWhat value does the key "{query_word}" correspond to?'
                        )
                    ],
                )
            )

            messages_to_send = messages.copy()
            messages_to_send[-1] = messages_to_send[-1].copy(
                metadata={"cache-control": True}
            )
            if len(messages_to_send) >= 3:
                messages_to_send[-3] = messages_to_send[-3].copy(
                    metadata={"cache-control": True}
                )

            # Send the request
            logger.debug(
                f"Sending request {iteration} with cacheable message (length: {len(pairs_text)} characters)"
            )
            response = client.process(
                messages=messages_to_send,
                model="anthropic/claude-3.7-sonnet",
                session_id="test-cache-session",
            )

            # Extract metrics
            num_input_tokens = response.metadata["native_tokens_prompt"] - 4
            approx_num_input_tokens = response.metadata["approx_num_tokens"]
            num_output_tokens = response.metadata["native_tokens_completion"]
            actual_cache_discount = response.metadata["cache_discount"]
            total_cost = response.metadata["usage"]

            # Calculate expected cache discount
            expected_cache_discount = (
                CACHE_WRITE_DISCOUNT * (num_input_tokens - previous_num_input_tokens)
                + CACHE_READ_DISCOUNT * previous_num_input_tokens
            )
            total_input_cost = total_cost - (OUTPUT_TOKEN_COST * num_output_tokens)

            # Calculate relative error
            relative_cache_discount_difference = (
                expected_cache_discount - actual_cache_discount
            ) / total_input_cost

            # Log the results
            logger.info(
                dedent(
                    f"""
                    --- Iteration {iteration} ---
                    Approximate input tokens: {approx_num_input_tokens}
                    Actual input tokens: {num_input_tokens}

                    Actual cache discount: {(actual_cache_discount * 1e3):.2f} mUSD
                    Expected cache discount: {(expected_cache_discount * 1e3):.2f} mUSD
                    Total input cost: {(total_input_cost * 1e3):.2f} mUSD
                    Total cost: {(total_cost * 1e3):.2f} mUSD
                    Cache discount error (Relative to input cost): {(100 * relative_cache_discount_difference):.4f}%
                    """
                )
            )

            # Assert that the difference is acceptable
            assert (
                relative_cache_discount_difference < 0.01
            ), f"Cache discount error too large in iteration {iteration}"

            # Update state for next iteration
            assistant_message = Message(role="assistant", content=response.content)
            messages.append(assistant_message)
            previous_num_input_tokens = num_input_tokens
