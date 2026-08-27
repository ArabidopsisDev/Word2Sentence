param(
    [string]$Python = "python",
    [ValidateSet("preview", "final", "release")]
    [string]$Stage = "preview"
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $true
}
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& $Python -B (Join-Path $Root "build.py") --stage $Stage
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
