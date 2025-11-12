Running tests (pytest) in this workspace

Quick start (Windows)

1. Install dependencies in your chosen Python env. The project expects Python 3.x.

   py -3 -m pip install -r requirements.txt

2. Run all tests from the workspace root:

   py -3 -m pytest -q

VS Code integration

- Open the workspace in VS Code. Install the recommended extensions if prompted (Python, Pylance).
- The workspace includes .vscode/settings.json which enables pytest discovery for the `tests` folder.
- Use `Terminal > Run Task...` and choose "pytest: all" to run the full test suite.
- Use Run/Debug (F5) and choose one of the "Python: Pytest ..." configurations to debug tests.

Troubleshooting

- If tests don't discover, confirm the Python interpreter selected at the bottom-right of VS Code.
- If you use a virtualenv, activate it and reinstall requirements.
- On Windows use `py -3 -m pytest ...` to ensure the correct Python is used.
