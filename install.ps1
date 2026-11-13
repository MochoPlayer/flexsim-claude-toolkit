# install.ps1: copy the four FlexSim skills to your Claude Code skills folder.
# Usage: .\install.ps1 [-Target <skills folder>]   (default: $HOME\.claude\skills)
# An existing skill folder with the same name is replaced.
param([string]$Target = (Join-Path $HOME ".claude\skills"))

New-Item -ItemType Directory -Force $Target | Out-Null
foreach ($name in "flexsim", "flexsim-experiment", "flexsim-charts", "flexsim-bisect") {
    $src = Join-Path $PSScriptRoot "skills\$name"
    $dst = Join-Path $Target $name
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Recurse $src $dst
    Write-Host "installed $name -> $dst"
}
