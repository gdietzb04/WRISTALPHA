[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "logs", "update", "rebuild")]
    [string]$Command = "start",
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $ProjectRoot "docker-compose.yml"
$BuildComposeFile = Join-Path $ProjectRoot "docker-compose.build.yml"
$SecretDirectory = Join-Path $ProjectRoot ".wristalpha\secrets"
$SecretFile = Join-Path $SecretDirectory "postgres_password"
$LegacyEnvironmentFile = Join-Path $ProjectRoot ".env"
$Repository = "gdietzb04/WRISTALPHA"
$ApiImage = "ghcr.io/gdietzb04/wristalpha-api"
$FrontendImage = "ghcr.io/gdietzb04/wristalpha-frontend"
$ImageTag = if ([string]::IsNullOrWhiteSpace($env:WRISTALPHA_IMAGE_TAG)) {
    "main"
} else {
    $env:WRISTALPHA_IMAGE_TAG
}
if ($ImageTag -notmatch "^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$") {
    throw "WRISTALPHA_IMAGE_TAG is not a valid container tag."
}
$env:WRISTALPHA_IMAGE_TAG = $ImageTag
$env:WRISTALPHA_SECRET_FILE = $SecretFile
$DashboardUrl = "http://127.0.0.1:5173"
$HealthUrl = "http://127.0.0.1:8000/health"
$BaseComposeArguments = @(
    "compose",
    "--project-directory", $ProjectRoot,
    "-f", $ComposeFile
)

function Invoke-Docker {
    param([Parameter(Mandatory)][string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE."
    }
}

function Test-DockerEngine {
    & docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Assert-DockerEngine {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker Desktop is required. Install it from https://www.docker.com/products/docker-desktop/."
    }
    if (Test-DockerEngine) {
        return
    }

    Write-Host "Starting Docker Desktop..."
    & docker desktop start *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop could not be started. Start it manually and retry."
    }
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-DockerEngine) {
            return
        }
    }
    throw "Docker Desktop did not become ready within 120 seconds."
}

function Protect-SecretFile {
    if ($env:OS -ne "Windows_NT") {
        return
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $systemSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-18")
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetOwner($identity.User)
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule(
        (New-Object System.Security.AccessControl.FileSystemAccessRule(
            $identity.User,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        ))
    )
    $acl.AddAccessRule(
        (New-Object System.Security.AccessControl.FileSystemAccessRule(
            $systemSid,
            [System.Security.AccessControl.FileSystemRights]::Read,
            [System.Security.AccessControl.AccessControlType]::Allow
        ))
    )
    Set-Acl -LiteralPath $SecretFile -AclObject $acl
}

function Initialize-Secret {
    if (Test-Path -LiteralPath $SecretFile) {
        $existingSecret = [System.IO.File]::ReadAllText($SecretFile).Trim()
        if ($existingSecret.Length -lt 32) {
            throw "The existing database secret is invalid. It was not overwritten."
        }
        return
    }

    $secret = $null
    if (Test-Path -LiteralPath $LegacyEnvironmentFile) {
        foreach ($line in [System.IO.File]::ReadAllLines($LegacyEnvironmentFile)) {
            if ($line.StartsWith("POSTGRES_PASSWORD=", [System.StringComparison]::Ordinal)) {
                $candidate = $line.Substring("POSTGRES_PASSWORD=".Length).Trim()
                if (
                    $candidate.Length -ge 32 -and
                    $candidate -ne "replace-with-a-long-url-safe-local-secret"
                ) {
                    $secret = $candidate
                }
                break
            }
        }
    }

    [System.IO.Directory]::CreateDirectory($SecretDirectory) | Out-Null
    if ($null -eq $secret) {
        $bytes = New-Object byte[] 32
        $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $generator.GetBytes($bytes)
        } finally {
            $generator.Dispose()
        }
        $secret = ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    } else {
        Write-Host "Migrated the existing local database password into the protected secret store."
    }
    [System.IO.File]::WriteAllText($SecretFile, $secret, [System.Text.UTF8Encoding]::new($false))
    Protect-SecretFile
    Write-Host "Created a protected local database secret."
}

function Assert-GitHubAttestationTool {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required to verify image provenance. Install it from https://cli.github.com/."
    }
    & gh auth status *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run 'gh auth login' and retry."
    }
}

function Test-ComposeConfiguration {
    Invoke-Docker -DockerArguments ($BaseComposeArguments + @("config", "--quiet"))
}

function Get-VerifiedImageDigest {
    param([Parameter(Mandatory)][string]$Image)
    $reference = "${Image}:$ImageTag"
    $digest = (& docker image inspect --format "{{index .RepoDigests 0}}" $reference).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($digest)) {
        throw "Could not resolve the pulled digest for $reference."
    }
    & gh attestation verify "oci://$digest" --repo $Repository
    if ($LASTEXITCODE -ne 0) {
        throw "Provenance verification failed for $digest. The image was not started."
    }
    return $digest
}

function Pull-And-VerifyImages {
    Assert-GitHubAttestationTool
    Invoke-Docker -DockerArguments ($BaseComposeArguments + @("pull"))
    Get-VerifiedImageDigest -Image $ApiImage | Out-Null
    Get-VerifiedImageDigest -Image $FrontendImage | Out-Null
    Write-Host "Verified GitHub build provenance for both application images."
}

function Wait-ForApi {
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
            if ($response.status -eq "ok") {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Containers started, but the API health endpoint did not report ok."
}

function Start-Stack {
    param([switch]$BuildLocally)
    Initialize-Secret
    Assert-DockerEngine
    Test-ComposeConfiguration

    if ($BuildLocally) {
        $arguments = $BaseComposeArguments + @(
            "-f", $BuildComposeFile,
            "up", "-d", "--build", "--wait", "--wait-timeout", "240", "--remove-orphans"
        )
        Invoke-Docker -DockerArguments $arguments
    } else {
        Pull-And-VerifyImages
        Invoke-Docker -DockerArguments (
            $BaseComposeArguments + @(
                "up", "-d", "--wait", "--wait-timeout", "180", "--remove-orphans"
            )
        )
    }

    Wait-ForApi
    Write-Host "WRISTALPHA is healthy: $DashboardUrl"
    if (-not $NoBrowser) {
        Start-Process $DashboardUrl
    }
}

try {
    Set-Location $ProjectRoot
    switch ($Command) {
        "start" {
            Start-Stack
        }
        "update" {
            Start-Stack
        }
        "rebuild" {
            Start-Stack -BuildLocally
        }
        "stop" {
            Assert-DockerEngine
            Invoke-Docker -DockerArguments ($BaseComposeArguments + @("stop"))
        }
        "status" {
            Assert-DockerEngine
            Invoke-Docker -DockerArguments ($BaseComposeArguments + @("ps"))
        }
        "logs" {
            Assert-DockerEngine
            Invoke-Docker -DockerArguments (
                $BaseComposeArguments + @("logs", "--tail", "200", "--follow")
            )
        }
    }
} catch {
    Write-Error $_
    exit 1
}
