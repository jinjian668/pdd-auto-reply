param(
    [switch]$SkipAssets,
    [switch]$SkipSchema
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = 'D:\codex-work\pdd-auto-reply-runtime'
$CredPath = Join-Path $Runtime 'credentials.json'
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Exporter = Join-Path $Repo 'tools\export_business_assets.py'
$Mysqldump = Join-Path $Runtime 'mysql\mysql-8.0.46-winx64\bin\mysqldump.exe'
$SchemaPath = Join-Path $Repo 'database\schema.sql'

if (-not (Test-Path -LiteralPath $CredPath)) {
    throw "本地凭据文件不存在：$CredPath"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python 虚拟环境不存在：$Python"
}

$cred = Get-Content -LiteralPath $CredPath -Raw | ConvertFrom-Json
$saved = @{
    MYSQL_HOST = $env:MYSQL_HOST
    MYSQL_PORT = $env:MYSQL_PORT
    MYSQL_USER = $env:MYSQL_USER
    MYSQL_PASSWORD = $env:MYSQL_PASSWORD
    MYSQL_DATABASE = $env:MYSQL_DATABASE
    MYSQL_PWD = $env:MYSQL_PWD
}

try {
    $env:MYSQL_HOST = $cred.mysql_host
    $env:MYSQL_PORT = [string]$cred.mysql_port
    $env:MYSQL_USER = $cred.mysql_app_user
    $env:MYSQL_PASSWORD = $cred.mysql_app_password
    $env:MYSQL_DATABASE = $cred.mysql_database

    if (-not $SkipAssets) {
        & $Python $Exporter
        if ($LASTEXITCODE -ne 0) { throw "业务资产导出失败，退出码 $LASTEXITCODE" }
    }

    if (-not $SkipSchema) {
        if (-not (Test-Path -LiteralPath $Mysqldump)) {
            throw "mysqldump 不存在：$Mysqldump"
        }
        $env:MYSQL_PWD = $cred.mysql_app_password
        $dumpArgs = @(
            '--protocol=tcp',
            "--host=$($cred.mysql_host)",
            "--port=$($cred.mysql_port)",
            "--user=$($cred.mysql_app_user)",
            '--ssl-mode=DISABLED',
            '--default-character-set=utf8mb4',
            '--no-data',
            '--skip-comments',
            '--skip-dump-date',
            '--set-gtid-purged=OFF',
            '--no-tablespaces',
            '--routines=false',
            '--triggers=false',
            '--single-transaction',
            "$($cred.mysql_database)"
        )
        $body = (& $Mysqldump @dumpArgs | Out-String -Width 1000000).TrimEnd()
        if ($LASTEXITCODE -ne 0) { throw "数据库结构导出失败，退出码 $LASTEXITCODE" }
        # 清除表级自增计数器，避免从结构快照推断存量数据规模。
        $body = $body -replace '(?m)\s+AUTO_INCREMENT=\d+', ''
        $header = @"
-- PDD 自动回复系统数据库结构快照
-- 生成时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
-- 说明：仅包含 DDL，不包含业务数据或凭据。

"@
        [System.IO.File]::WriteAllText($SchemaPath, $header + $body + "`n", [System.Text.UTF8Encoding]::new($false))
        Write-Output "数据库结构已更新：$SchemaPath"
    }
} finally {
    foreach ($name in $saved.Keys) {
        if ($null -eq $saved[$name]) {
            Remove-Item "Env:$name" -ErrorAction SilentlyContinue
        } else {
            Set-Item "Env:$name" $saved[$name]
        }
    }
}
