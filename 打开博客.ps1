$ErrorActionPreference = 'SilentlyContinue'
$port = 1313
$url = "http://localhost:$port/"
$blog = 'D:\Downloads\Programs\myblog-new'

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

# Always restart hugo to avoid stale template cache issues
Get-Process hugo -ErrorAction SilentlyContinue | Stop-Process -Force
for ($i = 0; $i -lt 20 -and (Test-Port $port); $i++) {
    Start-Sleep -Milliseconds 300
}
Start-Process -FilePath 'hugo' -ArgumentList 'server', '-D', '--port', "$port" `
    -WorkingDirectory $blog -WindowStyle Hidden
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 1000
    if (Test-Port $port) { break }
}
Start-Process $url
