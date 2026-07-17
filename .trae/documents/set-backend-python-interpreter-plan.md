# Set Backend Python Interpreter Plan

## Summary

Provide the exact steps to configure the IDE to use the backend virtual environment interpreter at `d:\Trae_projects\FraudSentinal\backend\venv\Scripts\python.exe`.

## Current State Analysis

- The repository contains a Python backend at `d:\Trae_projects\FraudSentinal\backend`.
- A virtual environment already exists at `d:\Trae_projects\FraudSentinal\backend\venv`.
- The interpreter executable exists at `d:\Trae_projects\FraudSentinal\backend\venv\Scripts\python.exe`.
- The virtual environment metadata file exists at `d:\Trae_projects\FraudSentinal\backend\venv\pyvenv.cfg`.
- No code changes are required for this task because the user is asking how to point the IDE to the existing interpreter.

## Proposed Changes

### No repository code changes

- Do not edit backend source files.
- Do not change route, service, CRUD, or app wiring.

### User guidance to apply in the IDE

- Open the command palette in the IDE.
- Run `Python: Select Interpreter`.
- Choose `Enter interpreter path` if the backend virtual environment is not already listed.
- Select or paste the interpreter path:
  - `d:\Trae_projects\FraudSentinal\backend\venv\Scripts\python.exe`
- Open a Python file under `backend` to confirm the selected interpreter is used for that workspace.

### Optional terminal activation guidance

- If the user also wants the terminal to use the same environment, activate:
  - `d:\Trae_projects\FraudSentinal\backend\venv\Scripts\Activate.ps1`
- If PowerShell blocks script execution, prefer using the interpreter directly instead of changing policy unless the user explicitly wants help with that.

## Assumptions & Decisions

- Assume the user is using a VS Code or Trae-style Python extension workflow where interpreter selection is done via `Python: Select Interpreter`.
- Keep the answer instructional only and avoid making environment changes automatically.
- Use the existing backend virtual environment rather than creating a new one.

## Verification Steps

- Confirm the status bar shows the selected interpreter from `backend\venv`.
- In a Python terminal, run:
  - `d:\Trae_projects\FraudSentinal\backend\venv\Scripts\python.exe --version`
- In the IDE, open a backend Python file and verify linting/import resolution uses the selected interpreter.
