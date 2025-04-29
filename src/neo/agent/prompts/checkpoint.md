IMPORTANT: This is a system message. DO NOT respond to any prior requests.

Create a concise checkpoint of our conversation so far, and return it as markdown using the structured output command.
Be brief but include enough information to continue the conversation later.

Include the following sections. Omit empty sections. Build on top of the previous checkpoints 
if present.

# Requests

This sections contains details on the requests provided by the user. It is maintained as a hierarchial list of TODO items.

1. [ ] Request 1
  1. [ ] Sub request 1.1
  2. [ ] Sub request 1.2
  ...
2. [ ] Request 2
...
N. [ ] Request N

Cross them off and truncate them based on the following algorithm - 
- If all items X.Y.* have been completed then drop them and only keep item X.Y
- Only keep the LAST 3 completed items.
  - If sub requests 1.1 to 1.4 are completed then 1.1 won't be included in the output.
  - If requests 1 to 5 were completed then requests 1 and 2 will be collapsed to a "..."

Make sure to include the user request in detail
- The exact request from the user
- Specific instructions on how to format and return the output

# Plan

What you have been planning on doing to address the user's requests and what has been done so far.

Maintain it as a hierarchial list of TODO items. Cross them off if they have been completed.

1. [ ] Task 1
  1. [x] Sub task 1.1
  2. [ ] Sub task 1.2
    2. [ ] Task 1.2
  ...

Follow the same algorithm as in the User's Request section.

----

After requests and plan, include sections with semantic knowledge which are broken down into separate projects. Each project has fairly independent knowledge and learnings.

- The project in the previous checkpoint might have been too narrow. You may expand it to a      broader scope if you have more information.
- Only include concrete learnings, knowledge and insights that you have gained by either
information directly provided by the user, files you have read, or the result of actions you have taken.
- Within each project, information is organized hierarchically as "entities". An entity could
be a file, directory, specific class, person, object, etc.
- When adding an entity also connect it to a specific task where it was used. You may drop 
entities from the previous checkpoint if the corresponding tasks have been completed.
- You may omit this section if you don't have any relevant learnings.

# Project A

## Entity A

Learnings about entity A.

Connected tasks: 1.1, 1.2, 2

### Entity A.1

Learning about entity A.1 ...

Connected tasks: 1.1, 1.2

## Project B

...

----

In general, avoid speculation, keep the checkpoint factual and to the point, and do not repeat information that already covered in prior sections.

IMPORTANT: Make sure to include the "■" at the end of your checkpoint output command. You keep getting this wrong. 
