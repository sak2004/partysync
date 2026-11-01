<#
  One-time Git setup for PartySync on Windows.
  Run from anywhere:
    powershell -ExecutionPolicy Bypass -File scripts\setup_git.ps1
#>
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed. Get it from https://git-scm.com/download/win and run this again."
    exit 1
}

if (-not (Test-Path ".git")) {
    git init -b main
    if ($LASTEXITCODE -ne 0) {
        # Older Git without the -b flag.
        git init
        git symbolic-ref HEAD refs/heads/main
    }
} else {
    Write-Host "Repo already initialised."
}

git config core.hooksPath .githooks
git config commit.template .gitmessage

$name = git config user.name
$email = git config user.email
if (-not $name -or -not $email) {
    Write-Warning "Git identity is not set. Run:"
    Write-Host '  git config --global user.name "Your Name"'
    Write-Host '  git config --global user.email "you@example.com"'
}

git rev-parse --verify --quiet HEAD | Out-Null
if ($LASTEXITCODE -ne 0) {
    git add -A
    git commit -m "chore: scaffold PartySync project" -m "Milestone: M0"
    git tag -a v0.0.0 -m "Scaffold"
    git tag -a milestone-M0 -m "M0 Repo scaffold and version control"
} else {
    Write-Host "Repo already has commits, nothing committed."
}

Write-Host ""
Write-Host "Done. Hooks active (.githooks), commit template set."
Write-Host "Next: git switch -c m1-core-dsp   (one branch per milestone)"
