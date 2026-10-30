param(
    [string]$ShortcutName = 'PDD自动回复系统-后台服务.lnk',
    [string]$StartupDirectory = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup')
)

$ErrorActionPreference = 'Stop'

$startupPath = [System.IO.Path]::GetFullPath($StartupDirectory).TrimEnd('\')
$shortcutPath = [System.IO.Path]::GetFullPath((Join-Path $startupPath $ShortcutName))
$shortcutParent = [System.IO.Path]::GetDirectoryName($shortcutPath).TrimEnd('\')

if ($shortcutParent -ne $startupPath) {
    throw "拒绝删除启动目录之外的文件：$shortcutPath"
}

if (-not (Test-Path -LiteralPath $shortcutPath)) {
    Write-Output "未发现 PDD 登录自启动项：$shortcutPath"
    exit 0
}

Remove-Item -LiteralPath $shortcutPath -Force

if (Test-Path -LiteralPath $shortcutPath) {
    throw "自启动项仍然存在：$shortcutPath"
}

Write-Output "已移除 PDD 登录自启动项：$shortcutPath"
