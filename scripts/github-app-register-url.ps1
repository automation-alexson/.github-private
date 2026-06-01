# Print GitHub App manifest registration URLs for each org.
# Run from repo root: pwsh .github-private/scripts/github-app-register-url.ps1
param(
    [string]$ManifestDir = (Join-Path $PSScriptRoot ".." "github-app")
)

function Get-ManifestUrl {
    param([string]$ManifestPath)
    $json = Get-Content -Raw -Path $ManifestPath
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $b64 = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    return "https://github.com/settings/apps/new?state=register&manifest=$b64"
}

foreach ($file in @(
        "manifest.infrastructure-alexson.json",
        "manifest.general-alexson.json"
    )) {
    $path = Join-Path $ManifestDir $file
    if (-not (Test-Path $path)) {
        Write-Error "Missing $path"
        continue
    }
    Write-Output ""
    Write-Output "=== $file ==="
    Write-Output (Get-ManifestUrl -ManifestPath $path)
    Write-Output "Org UI (manual): https://github.com/organizations/$(
        if ($file -match 'infrastructure') { 'infrastructure-alexson' } else { 'general-alexson' }
    )/settings/apps/new"
}
