# Print GitHub App manifest registration URLs.
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

$manifests = @(
    @{ File = "manifest.automation-alexson.json"; Org = "automation-alexson"; Primary = $true },
    @{ File = "manifest.infrastructure-alexson.json"; Org = "infrastructure-alexson"; Primary = $false },
    @{ File = "manifest.general-alexson.json"; Org = "general-alexson"; Primary = $false }
)

foreach ($entry in $manifests) {
    $path = Join-Path $ManifestDir $entry.File
    if (-not (Test-Path $path)) {
        Write-Error "Missing $path"
        continue
    }
    $label = if ($entry.Primary) { " (recommended)" } else { " (alternative — one app per org)" }
    Write-Output ""
    Write-Output "=== $($entry.File)$label ==="
    Write-Output (Get-ManifestUrl -ManifestPath $path)
    Write-Output "Org UI (manual): https://github.com/organizations/$($entry.Org)/settings/apps/new"
}
