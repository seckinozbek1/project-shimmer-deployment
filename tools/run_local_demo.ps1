<#
.SYNOPSIS
    Run the Shimmer pipeline locally, in-process, with memory sampled to disk.

.DESCRIPTION
    A thin shell over tools/run_local_demo.py. The Python wrapper does the work:
    it imports the pipeline module and calls its entry point, so the pipeline's
    filename never appears in a shell command, and it samples RAM and VRAM every
    three seconds to a JSON file that is rewritten after every sample, so the
    peaks survive a run that is killed for memory.

    Every argument is passed through to the Python wrapper, and from there to the
    pipeline unchanged.

.EXAMPLE
    .\tools\run_local_demo.ps1 --non-interactive

.EXAMPLE
    .\tools\run_local_demo.ps1 --non-interactive --review-mode paired
#>

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$wrapper = Join-Path $PSScriptRoot "run_local_demo.py"

if (-not (Test-Path $wrapper)) {
    throw "wrapper not found at $wrapper"
}

# Prefer the repository's own virtual environment, fall back to the launcher.
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
    $pythonArgs = @("-X", "utf8", $wrapper)
} else {
    $python = "py"
    $pythonArgs = @("-3.9", "-X", "utf8", $wrapper)
}

Push-Location $root
try {
    & $python @pythonArgs @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
