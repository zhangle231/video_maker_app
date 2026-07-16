# git_commit_push.ps1
# 用法:
#   .\git_commit_push.ps1                   交互式，检测变更后提示输入 message
#   .\git_commit_push.ps1 -m "提交信息"      指定 message
#   .\git_commit_push.ps1 -m "msg" -f       跳过确认，直接执行
#   .\git_commit_push.ps1 -m "msg" -b main  推送到指定分支（默认 master）

param(
    [string]$message = "",
    [string]$branch = "master",
    [switch]$force = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==== Git Commit & Push ====" -ForegroundColor Cyan

if ((Test-Path ".git") -eq $false) {
    Write-Host "Error: not a Git repo" -ForegroundColor Red
    exit 1
}

$remoteUrl = git remote get-url origin 2>$null
if (-not $remoteUrl) {
    Write-Host "Error: no remote origin configured" -ForegroundColor Red
    exit 1
}
Write-Host "Remote: $remoteUrl"

Write-Host "Verifying remote access..." -ForegroundColor Gray
git ls-remote origin HEAD *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: cannot access remote" -ForegroundColor Red
    exit 1
}
Write-Host "Remote accessible" -ForegroundColor Green

$status = git status --porcelain
if (-not $status) {
    Write-Host "No changes to commit" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Changes:" -ForegroundColor Cyan
foreach ($line in $status) {
    $pfx = $line.Substring(0, 2)
    $f = $line.Substring(3)
    switch -Wildcard ($pfx) {
        "??" { Write-Host "  [new] $f" -ForegroundColor Green }
        " M" { Write-Host "  [mod] $f" -ForegroundColor Yellow }
        " D" { Write-Host "  [del] $f" -ForegroundColor Red }
        "A " { Write-Host "  [idx] $f" -ForegroundColor Blue }
        default { Write-Host "  [$pfx] $f" }
    }
}

if (-not $message) {
    Write-Host ""
    $message = Read-Host "Commit message"
    if (-not $message) {
        Write-Host "Cancelled" -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "Message: $message" -ForegroundColor White
Write-Host "Branch: $branch" -ForegroundColor White

if (-not $force) {
    $confirm = Read-Host "Proceed? (y/n)"
    if ($confirm -ne 'y' -and $confirm -ne 'Y') {
        Write-Host "Cancelled" -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "[1/3] git add -A ..." -ForegroundColor Gray
git add -A
if ($LASTEXITCODE -ne 0) { Write-Host "Failed" -ForegroundColor Red; exit 1 }

Write-Host "[2/3] git commit ..." -ForegroundColor Gray
$co = git commit -m $message 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Commit failed: $co" -ForegroundColor Red
    exit 1
}
Write-Host $co

Write-Host "[3/3] git push origin $branch ..." -ForegroundColor Gray
$po = git push origin $branch 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Push failed: $po" -ForegroundColor Red
    exit 1
}

$local = git log -1 --oneline
$remote = git log "origin/$branch" -1 --oneline
Write-Host ""
Write-Host "==== Done ====" -ForegroundColor Green
Write-Host "Local : $local"
Write-Host "Remote: $remote"

if ($local -eq $remote) {
    Write-Host "In sync!" -ForegroundColor Green
} else {
    Write-Host "Warning: mismatch" -ForegroundColor Yellow
}
