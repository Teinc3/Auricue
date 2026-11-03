# Auricue
A conversational assistant providing conversational context in the form of
real-time audio cues.

## Setup
1. Create and fill in the .env file with the appropriate API keys (there is a
    .env.example file for reference)
2. Create a virtual environment using `python3 -m venv .venv`
3. Activate the environment using `.venv/bin/activate`
    (or `.\.venv\Scripts\Activate.ps1` on windows)

## Run
To run the entire suite, including the UI, server and controller:
```py
python3 -m src.main
```

To run only the controller via terminal:
```py
python3 -m src.main --cli
```

## Design/Technical Specification
See [design.md](/docs/design.md) for full specification.

## Authors/Credits
This is my personal submission for the Hiya Voice AI Challenge
(starting from 27/10 to 03/11 of 2026). There are no other contributors.

## Declaration of AI use
Declaration of AI use is included in the [ai.md](/docs/AI.md) file.
