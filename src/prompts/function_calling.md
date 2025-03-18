You have access to the following functions:

✿function_descriptions✿

To call a function, respond with a message that contains the function call
in the following format:
✿FUNCTION✿: <function_name>
✿ARGS✿: <arguments as a JSON object>
✿END FUNCTION✿

For example:
✿FUNCTION✿: read_files
✿ARGS✿: {"path": "src/model.py"}
✿END FUNCTION✿

Function results will be returned to you in the format:
✿RESULT✿: <result>

✿examples_text✿

After receiving all function results, you can continue with your response.