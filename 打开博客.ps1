$ErrorActionPreference = 'SilentlyContinue'
$port = 1313
$url = "http://localhost:$port/"
$wslBlog = '/home/mcryii/myblog-new'

function Test-Port($p) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $p)
        $c.Close()
        return $true
    } catch {
        return $false
    }
}

# 若端口未响应，调用 WSL 启动后台 Hugo 服务
if (-not (Test-Port $port)) {
    Start-Process -FilePath "wsl.exe" -ArgumentList "-d", "Ubuntu-24.04", "--cd", $wslBlog, "bash", "./run.sh", "--daemon" -WindowStyle Hidden
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 600
        if (Test-Port $port) { break }
    }
}

Start-Process $url

