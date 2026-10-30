param(
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'status',
    [string]$RuntimeDir = '',
    [string]$PythonExecutable = '',
    [string]$WebsocketUrl = '',
    [int]$StartTimeoutSeconds = 90,
    [int]$StopTimeoutSeconds = 20
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Split-Path -Parent $ScriptDir
$EntryPath = [System.IO.Path]::GetFullPath((Join-Path $Repo 'websocket\main.py'))

if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = $env:PDD_RUNTIME_DIR }
if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = Join-Path $Repo 'runtime' }
$RuntimeDir = [System.IO.Path]::GetFullPath($RuntimeDir)
$RunDir = Join-Path $RuntimeDir 'run'
$LogDir = Join-Path $RuntimeDir 'logs'
$PidFile = Join-Path $RunDir 'websocket.pid'
$OutLog = Join-Path $LogDir 'websocket-control.out.log'
$ErrLog = Join-Path $LogDir 'websocket-control.err.log'

if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $Repo '.venv\Scripts\python.exe'
}
$PythonExecutable = [System.IO.Path]::GetFullPath($PythonExecutable)

if ([string]::IsNullOrWhiteSpace($WebsocketUrl)) {
    $WebsocketUrl = 'http://127.0.0.2:8090'
}
$WebsocketUrl = $WebsocketUrl.TrimEnd('/')
$HealthUrl = "$WebsocketUrl/health"
try {
    $uri = [System.Uri]$WebsocketUrl
    $Port = $uri.Port
    $HostName = $uri.Host
} catch {
    $Port = 8090
    $HostName = '127.0.0.2'
}

$TaskKill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
New-Item -ItemType Directory -Force -Path $RunDir, $LogDir | Out-Null

function Write-Result {
    param(
        [bool]$Success,
        [string]$Code = '',
        [int]$PidValue = 0,
        [object[]]$PidValues = @(),
        [bool]$Online = $false,
        [string]$Detail = ''
    )
    $payload = [ordered]@{
        success = $Success
        action = $Action
        code = $Code
        pid = if ($PidValue -gt 0) { $PidValue } else { $null }
        pids = @($PidValues)
        online = $Online
        detail = $Detail
    }
    Write-Output ($payload | ConvertTo-Json -Compress)
}

function Test-Health {
    $request = [System.Net.HttpWebRequest]::Create($HealthUrl)
    $request.Proxy = $null
    $request.Timeout = 2500
    $request.ReadWriteTimeout = 2500
    $request.Method = 'GET'
    try {
        $response = $request.GetResponse()
        $statusCode = [int]$response.StatusCode
        $response.Close()
        return ($statusCode -ge 200 -and $statusCode -lt 300)
    } catch {
        return $false
    }
}

function Test-TcpPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect($HostName, $Port, $null, $null)
        if ($result.AsyncWaitHandle.WaitOne(700)) {
            $client.EndConnect($result)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-ServiceProcesses {
    return @(
        Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine.IndexOf($EntryPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }
    )
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $TaskKill /PID $ProcessId /T /F 2>$null | Out-Null
    } finally {
        $ErrorActionPreference = $savedPreference
    }
}

function Wait-Health {
    param([bool]$Expected, [int]$Seconds)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $current = Test-Health
        if ($current -eq $Expected) { return $true }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

try {
    if ($Action -eq 'status') {
        $processes = @(Get-ServiceProcesses)
        $pids = @($processes | ForEach-Object { [int]$_.ProcessId })
        $online = Test-Health
        Write-Result -Success $true -Code 'status' -PidValue $(if ($pids.Count -gt 0) { $pids[0] } else { 0 }) -PidValues $pids -Online $online
        exit 0
    }

    if ($Action -eq 'start') {
        if (Test-Health) {
            $processes = @(Get-ServiceProcesses)
            $pids = @($processes | ForEach-Object { [int]$_.ProcessId })
            Write-Result -Success $true -Code 'already_online' -PidValue $(if ($pids.Count -gt 0) { $pids[0] } else { 0 }) -PidValues $pids -Online $true
            exit 0
        }
        if (Test-TcpPort) {
            Write-Result -Success $false -Code 'port_in_use' -Detail "Port $Port is in use"
            exit 1
        }
        if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
            Write-Result -Success $false -Code 'python_missing' -Detail $PythonExecutable
            exit 1
        }
        if (-not (Test-Path -LiteralPath $EntryPath -PathType Leaf)) {
            Write-Result -Success $false -Code 'control_script_missing' -Detail $EntryPath
            exit 1
        }

        $quotedEntry = '"' + $EntryPath + '"'
        $process = Start-Process -FilePath $PythonExecutable -ArgumentList $quotedEntry -WorkingDirectory $Repo -WindowStyle Hidden -PassThru -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
        $process.Id | Set-Content -LiteralPath $PidFile -Encoding ascii
        if (-not (Wait-Health -Expected $true -Seconds $StartTimeoutSeconds)) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-Result -Success $false -Code 'health_failed' -PidValue $process.Id -Detail 'Health check timed out'
            exit 1
        }
        Write-Result -Success $true -Code 'started' -PidValue $process.Id -PidValues @($process.Id) -Online $true
        exit 0
    }

    if ($Action -eq 'stop') {
        $processes = @(Get-ServiceProcesses)
        $pids = @($processes | ForEach-Object { [int]$_.ProcessId })
        $online = Test-Health
        if ($pids.Count -eq 0) {
            if ($online) {
                Write-Result -Success $false -Code 'process_not_found' -Online $true -Detail 'Health is online but no matching websocket process was found'
                exit 1
            }
            Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
            Write-Result -Success $true -Code 'already_offline' -Online $false
            exit 0
        }

        foreach ($processId in $pids) {
            Stop-ProcessTree -ProcessId $processId
        }
        $deadline = (Get-Date).AddSeconds($StopTimeoutSeconds)
        do {
            Start-Sleep -Milliseconds 700
            $remaining = @(Get-ServiceProcesses)
            $stillOnline = Test-Health
        } while ((Get-Date) -lt $deadline -and ($remaining.Count -gt 0 -or $stillOnline))

        if ($remaining.Count -gt 0 -or $stillOnline) {
            $remainingPids = @($remaining | ForEach-Object { [int]$_.ProcessId })
            Write-Result -Success $false -Code 'stop_failed' -PidValues $remainingPids -Online $stillOnline -Detail 'Process or health check still active'
            exit 1
        }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-Result -Success $true -Code 'stopped' -PidValues $pids -Online $false
        exit 0
    }
} catch {
    Write-Result -Success $false -Code 'control_script_failed' -Detail $_.Exception.Message
    exit 1
}
