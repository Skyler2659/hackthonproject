param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ChronaArgs
)

$ErrorActionPreference = "Stop"

function Resolve-ChronaRoot {
    if ($env:CHRONA_ROOT) {
        return (Resolve-Path -LiteralPath $env:CHRONA_ROOT).Path
    }
    $candidate = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..\..")).Path
    if (Test-Path -LiteralPath (Join-Path $candidate "app.py")) {
        return $candidate
    }
    throw "Set CHRONA_ROOT to the Chrona project root containing app.py."
}

function Resolve-ChronaPython([string] $Root) {
    if ($env:CHRONA_PYTHON) {
        return $env:CHRONA_PYTHON
    }
    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "python",
        "py"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -like "*\*" -and (Test-Path -LiteralPath $candidate)) {
            if (Test-Python $candidate) {
                return $candidate
            }
        }
        if ($candidate -notlike "*\*" -and (Get-Command $candidate -ErrorAction SilentlyContinue)) {
            if (Test-Python $candidate) {
                return $candidate
            }
        }
    }
    throw "No Python executable found. Set CHRONA_PYTHON."
}

function Test-Python([string] $Python) {
    try {
        & $Python -c "import sys; raise SystemExit(0)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

$root = Resolve-ChronaRoot
$python = Resolve-ChronaPython $root
Push-Location $root
try {
    & $python -m chrona_cli @ChronaArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
