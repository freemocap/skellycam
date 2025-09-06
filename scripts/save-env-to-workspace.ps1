# build.ps1
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    if ($name -and $value) {
        Set-Item -Path env:$name -Value $value
    }
}

