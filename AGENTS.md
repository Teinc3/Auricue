# Agent Instructions

- Always ensure Ponytail is enabled.
- Always re-read relevant files and override the existing cached state after the user asks for modifications, as the user may also have implemented edits that will be overridden.
- Do not implement any functionality or edit any files unless explicitly given the permission or approval to. For example: (How would I make it such that ...: DO NOT EDIT ANY CODE, ONLY EXPLAIN; Sounds good, go forward: You may edit the code.)
- Do not run the ruff formatter. You can however run `.venv/bin/ruff check --fix` (automatic approval)
- Do not attempt to compile code with py_compile. We don't use it here.
- There must be one line between a function docstring and the start of any function implementation.
- Attempt to cram as many args/kwargs onto one line as possible without exceeding 100 char limit per line. This is to minimise line usage. Do so for items within [] and () BUT NOT DICTIONARIES. Do not add unnecessary commas at the end of the last item.
- For in-line curly braces always enforce space padding, eg. `{ "name": "John", "value": 3 }`
- Only I can add files to staged, as they signify the file is reviewed. You are not allowed to run the command. You are in fact not allowed to run any git command that modifies files, just replace files instead.
- Avoid doom-nesting by moving long logic flows to separate helpers / (internal) methods, exiting control flow if possible (if not then continue/return, instead of nesting ifs). Do not trim lines if this means more unnecessary nesting.
- Do not run any commands during the planning phase that requires manual approval, as this is unnecessary and slows down asynchronous workflows.
- Always do imports at the start of each file, you are not allowed to use lazy imports unless not doing so will lead to circular dependencies (a comment should be left explaining such case)
- ALWAYS ADD __all__ exports at the end of the file, with the exception of the entry point (main.py) and ALL __init__.py files (which imports must be immediately reexported under the same name using the "as" syntax). If a particular module exports too many files, it is preferred to just do a start import in the __init__.py for batch reexport.
- No need to run pytests if the current scope of the job is unrelated to the test contents.
