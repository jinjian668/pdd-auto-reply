$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$files = @(git diff --cached --name-only --diff-filter=ACMR)
if ($files.Count -eq 0) {
    Write-Output '安全检查通过：没有暂存文件。'
    exit 0
}

$blocked = @()
$pathRules = @(
    @{ Name = '环境变量文件'; Pattern = '(^|/)\.env$' },
    @{ Name = '环境变量覆盖文件'; Pattern = '(^|/)\.env\.(?!example$)[^/]+$' },
    @{ Name = '凭据文件'; Pattern = '(^|/)(credentials?|secrets?)([._-][^/]*)?\.json$' },
    @{ Name = 'Cookie / 登录态'; Pattern = '(^|/)(cookies?|storage_state|auth_state)([._-][^/]*)?\.json$' },
    @{ Name = '认证/会话状态'; Pattern = '(^|/)(auth|sessions?|states?)[^/]*\.json$' },
    @{ Name = '浏览器抓包'; Pattern = '\.har$' },
    @{ Name = '客户端凭据配置'; Pattern = '(^|/)(\.npmrc|\.pypirc|\.netrc)$' },
    @{ Name = '浏览器数据目录'; Pattern = '(^|/)(browser_data|user_data)/' },
    @{ Name = '上传或截图目录'; Pattern = '(^|/)(uploads?|screenshots?)/' },
    @{ Name = '备份目录'; Pattern = '(^|/)(backups?)/' },
    @{ Name = '根目录导出的运行数据'; Pattern = '^(data|exports)/' },
    @{ Name = 'MySQL 数据目录'; Pattern = '(^|/)mysql-data/' },
    @{ Name = '日志目录或文件'; Pattern = '(^|/)logs?/|\.log(\.|$)' },
    @{ Name = '数据库文件'; Pattern = '\.(sqlite3?|db|ibd|frm|myd|myi)(-wal|-shm)?$' },
    @{ Name = '私钥、证书或密钥库'; Pattern = '\.(pem|key|pfx|p12|jks|keystore|crt)$' },
    @{ Name = '整库导出'; Pattern = '\.dump$' },
    @{ Name = '非结构快照 SQL'; Pattern = '(^|/)database/(?!schema\.sql$)[^/]+\.sql$' },
    @{ Name = '项目私有资产'; Pattern = '(^|/)project-assets/private/' },
    @{ Name = '临时压缩包'; Pattern = '\.(zip|tar|tgz|gz|7z|rar)$' }
)

foreach ($file in $files) {
    $normalized = $file -replace '\\', '/'
    foreach ($rule in $pathRules) {
        if ($normalized -match $rule.Pattern) {
            $blocked += "[$($rule.Name)] $file"
        }
    }
}

function Get-StagedText([string]$File) {
    $content = @(git show ":$File" 2>$null)
    if ($LASTEXITCODE -ne 0) {
        return ''
    }
    return ($content -join "`n")
}

$binaryExtensions = '\.(png|jpe?g|gif|webp|ico|bmp|tiff?|pdf|woff2?|ttf|otf|eot|mp3|mp4|wav|ogg|mov|avi|zip|tar|tgz|gz|7z|rar)$'
$stagedTextParts = @()
foreach ($file in $files) {
    if (($file -replace '\\', '/') -notmatch $binaryExtensions) {
        $stagedTextParts += Get-StagedText $file
    }
}
$stagedText = $stagedTextParts -join "`n"

$secretPatterns = [ordered]@{
    'GitHub Token' = 'github_pat_[A-Za-z0-9_]{20,}'
    'GitHub 经典 Token' = 'gh[pousr]_[A-Za-z0-9]{20,}'
    'OpenAI 风格密钥' = 'sk-[A-Za-z0-9_-]{20,}'
    'AWS Access Key' = 'AKIA[0-9A-Z]{16}'
    'Slack Token' = 'xox[baprs]-[A-Za-z0-9-]{10,}'
    'Google API Key' = 'AIza[0-9A-Za-z_-]{35}'
    '私钥内容' = '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
}
foreach ($name in $secretPatterns.Keys) {
    if ($stagedText -match $secretPatterns[$name]) {
        $blocked += "[疑似$name] 暂存文件完整内容包含密钥特征"
    }
}

$assetFiles = @($files | Where-Object { ($_ -replace '\\', '/') -like 'project-assets/exports/*.json' })
if ($assetFiles.Count -gt 0) {
    $assetText = (@($assetFiles | ForEach-Object { Get-StagedText $_ }) -join "`n")
    $sensitiveKeys = '"(customer_uid|buyer_id|buyer_name|nickname|order_id|order_sn|receiver[^"]*|phone|mobile|email|address|contact|cookie|token|password|secret|api_key[^"]*|authorization|credential|thumb_url|image_url|avatar|raw_payload|login_state)"\s*:'
    if ($assetText -match $sensitiveKeys) {
        $blocked += '[客户隐私/凭据] 业务资产 JSON 包含禁止导出的字段键'
    }
    $assetValuePatterns = [ordered]@{
        '手机号' = '(?<!\d)1[3-9]\d{9}(?!\d)'
        '邮箱地址' = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
        'Cookie 请求头' = '(?i)Cookie\s*:'
        'Bearer 凭据' = '(?i)Authorization\s*:\s*Bearer'
        '带密钥的 URL 参数' = '(?i)[?&](token|access_token|api_key|key|secret|signature|sig)='
    }
    foreach ($name in $assetValuePatterns.Keys) {
        if ($assetText -match $assetValuePatterns[$name]) {
            $blocked += "[客户隐私/凭据] 业务资产 JSON 包含疑似$name"
        }
    }
}

$sqlFiles = @($files | Where-Object { ($_ -replace '\\', '/') -like 'database/*.sql' })
if ($sqlFiles.Count -gt 0) {
    $sqlText = (@($sqlFiles | ForEach-Object { Get-StagedText $_ }) -join "`n")
    if ($sqlText -match '(?im)^\s*(INSERT|REPLACE)\s+INTO\b|^\s*(LOAD\s+DATA|COPY)\b') {
        $blocked += '[数据库数据] database SQL 中包含业务数据写入语句'
    }
    if ($sqlText -match '(?im)\bAUTO_INCREMENT\s*=\s*\d+') {
        $blocked += '[数据库元数据] database SQL 包含自增计数，请重新生成结构快照'
    }
}

if ($blocked.Count -gt 0) {
    Write-Output '安全检查失败，请处理以下问题：'
    $blocked | Sort-Object -Unique | ForEach-Object { Write-Output " - $_" }
    exit 1
}

Write-Output "安全检查通过：$($files.Count) 个暂存文件。"
