<#
run-tests.ps1 - PowerShell wrapper to run pytest
Usage: .\run-tests.ps1 -- -k something
#>
param([
emainder()]$args)

# Run pytest forwarding any args and propagate the exit code
& py -3 -m pytest -q @args
exit $LASTEXITCODE
