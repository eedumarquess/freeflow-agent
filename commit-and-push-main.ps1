# commit-and-push-main.ps1
# Faz commit das atualizações básicas e envia para a branch main.
# Execução: .\commit-and-push-main.ps1

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

Set-Location $repoRoot

Write-Host "=== Status antes do commit ===" -ForegroundColor Cyan
git status --short

# Adiciona apenas os caminhos permitidos (evita surpresas)
git add AGENTS.md
git add featureflow/skills/tdd-feature-workflow/SKILL.md
git add ui/src/routes/RunDetailPage.tsx
git add web/api.py

$count = (git diff --cached --name-only | Measure-Object -Line).Lines
if ($count -eq 0) {
    Write-Host "Nenhuma alteração staged. Verifique se os arquivos existem e foram modificados." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n=== Arquivos que serao commitados ===" -ForegroundColor Cyan
git diff --cached --name-only

$msg = @"
chore: atualizacoes basicas

- AGENTS.md: regras e convencoes do projeto
- TDD skill: featureflow/skills/tdd-feature-workflow/SKILL.md
- UI: RunDetailPage.tsx
- Web API: web/api.py
"@

git commit -m $msg
if (-not $?) { exit 1 }

Write-Host "`n=== Enviando para origin main ===" -ForegroundColor Cyan
git push origin main
if (-not $?) { exit 1 }

Write-Host "`nConcluido." -ForegroundColor Green
