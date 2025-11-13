@echo off
REM run-tests.cmd - simple wrapper to run pytest on Windows (cmd)
REM Usage: run-tests.cmd [pytest-args]

py -3 -m pytest -q %*
exit /b %ERRORLEVEL%
