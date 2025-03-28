You have access to the following functions:

✿function_descriptions✿

To call a function, respond with a message that contains the function call in the following format:

```
✿FUNCTION✿: <function_name>
✿ARGS✿: <arguments as a Python dictionary>
✿END FUNCTION✿
```

IMPORTANT:
- The arguments MUST be a valid Python dictionary. Invalid arguments will cause an error and the function will not be executed.
- You MUST make at most one function call in one response.
- Only the system can return function results to you.

Function results will be returned to you by the system in the format:

```
✿RESULT✿: <result>
```

✿examples_text✿

You can continue with your response after receiving the function results.