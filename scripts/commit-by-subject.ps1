<#
.SYNOPSIS
    Cria commits separados por assunto na worktree, agrupando arquivos por diretório raiz.

.DESCRIPTION
    Lê o status da worktree (git status --porcelain), agrupa os arquivos modificados
    pelo primeiro segmento do path (ex: featureflow, tests, ui, web) e faz um commit
    por grupo com mensagem baseada no assunto.

.PARAMETER DryRun
    Apenas mostra o que seria feito, sem executar git add/commit.

.PARAMETER MessagePrefix
    Prefixo opcional para todas as mensagens de commit (ex: "fix: ").

.EXAMPLE
    .\commit-by-subject.ps1
    .\commit-by-subject.ps1 -DryRun
    .\commit-by-subject.ps1 -MessagePrefix "refactor: "
#>

param(
    [switch]$DryRun,
    [string]$MessagePrefix = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot) {
    Write-Error "Não está em um repositório git."
    exit 1
}
Set-Location $repoRoot

# Arquivos da worktree (modified, added, etc.) — ignora untracked se quiser só o que já existe
$porcelain = git status --porcelain
if (-not $porcelain) {
    Write-Host "Nenhuma alteração na worktree para commitar."
    exit 0
}

# Agrupa por "assunto" = primeiro segmento do path (featureflow, tests, ui, web, scripts, etc.)
$bySubject = @{}
foreach ($line in $porcelain) {
    $line = $line.Trim()
    if ($line.Length -lt 4) { continue }
    # Path começa após o status (2 chars) e o primeiro espaço — formato "XY path" ou "XY  path"
    $path = ($line.Substring(2) -split ' ', 2)[-1].Trim()
    # Rename: "from -> to" — usa o path de destino para add/commit
    if ($path -match ' -> ') {
        $path = ($path -split ' -> ', 2)[-1].Trim()
    }
    # Remove path entre aspas se existir (paths com espaço)
    if ($path.StartsWith('"') -and $path.EndsWith('"')) { $path = $path.Trim('"') }
    # Primeiro segmento como assunto (git usa / no path)
    $parts = $path -split '[/\\]'
    $subject = $parts[0]
    if (-not $bySubject.ContainsKey($subject)) {
        $bySubject[$subject] = [System.Collections.ArrayList]@()
    }
    [void]$bySubject[$subject].Add($path)
}

# Ordem preferida dos assuntos (opcional)
$order = @("featureflow", "web", "ui", "tests", "scripts", "cli", "outputs")
$remaining = $bySubject.Keys | Where-Object { $_ -notin $order }
$sortedSubjects = ($order | Where-Object { $bySubject.ContainsKey($_) }) + ($remaining | Sort-Object)

foreach ($subject in $sortedSubjects) {
    $paths = $bySubject[$subject]
    $msg = "${MessagePrefix}$subject"
    if ($DryRun) {
        Write-Host "[DRY-RUN] Commit: $msg" -ForegroundColor Cyan
        foreach ($p in $paths) { Write-Host "  - $p" }
        continue
    }
    foreach ($p in $paths) {
        git add -- "$p"
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Falha ao dar add em: $p"
        }
    }
    git commit -m "$msg"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Nenhuma alteração commitada para assunto '$subject' (pode estar vazio após add)."
    } else {
        Write-Host "Commit criado: $msg" -ForegroundColor Green
    }
}

if ($DryRun) {
    Write-Host "`nUse sem -DryRun para executar os commits." -ForegroundColor Yellow
}
