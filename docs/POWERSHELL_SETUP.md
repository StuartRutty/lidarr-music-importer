# PowerShell Profile Setup for Lidarr Import Script

This guide shows how to set up convenient PowerShell shortcuts for the Lidarr album import script.

## Quick Setup

### 1. Open Your PowerShell Profile

```powershell
notepad $PROFILE
```

If you get an error that the file doesn't exist, create it first:

```powershell
New-Item -Path $PROFILE -Type File -Force
notepad $PROFILE
```

### 2. Add the Shortcuts

Paste this into your profile (replace `C:\path\to\scripts` with your actual path):

```powershell
# Lidarr Album Import Shortcuts
# Edit this to point to your local project path, or set it dynamically.
# Example (placeholder):
$lidarrScriptPath = "C:\\path\\to\\lidarr-music-importer\\scripts"  # <-- set this to your path

# Example dynamic: derive path from this profile location if you keep scripts next to profile
# $lidarrScriptPath = Join-Path (Split-Path -Parent $PROFILE) "..\lidarr-music-importer\scripts"

function lidarr-import {
    <#
    .SYNOPSIS
    Run full Lidarr album import with default settings
    .EXAMPLE
    lidarr-import albums.csv
    #>
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args
}

function lidarr-test {
    <#
    .SYNOPSIS
    Test import on first 5 items (dry-run)
    .EXAMPLE
    lidarr-test albums.csv
    #>
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args[0] --dry-run --max-items 5
}

function lidarr-retry {
    <#
    .SYNOPSIS
    Retry only failed items
    .EXAMPLE
    lidarr-retry albums.csv
    #>
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args[0] --status failed
}

function lidarr-refresh {
    <#
    .SYNOPSIS
    Process items with pending_refresh status
    .EXAMPLE
    lidarr-refresh albums.csv
    #>
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args[0] --status pending_refresh
}

function lidarr-artist {
    <#
    .SYNOPSIS
    Process albums by specific artist
    .EXAMPLE
    lidarr-artist albums.csv "Kanye West"
    #>
    if ($args.Count -lt 2) {
        Write-Host "Usage: lidarr-artist <csv> <artist_name>" -ForegroundColor Yellow
        return
    }
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args[0] --artist $args[1]
}

function lidarr-quick {
    <#
    .SYNOPSIS
    Fast import (skip existing artists, no batch pauses)
    .EXAMPLE
    lidarr-quick albums.csv
    #>
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args[0] --skip-existing --no-batch-pause
}

function lidarr-help {
    <#
    .SYNOPSIS
    Show help for Lidarr import shortcuts
    #>
    Write-Host "`nLidarr Album Import Shortcuts:" -ForegroundColor Cyan
    Write-Host "  lidarr-import <csv>          " -ForegroundColor Green -NoNewline
    Write-Host "- Run full import with default settings"
    Write-Host "  lidarr-test <csv>            " -ForegroundColor Green -NoNewline
    Write-Host "- Dry-run test on first 5 items"
    Write-Host "  lidarr-retry <csv>           " -ForegroundColor Green -NoNewline
    Write-Host "- Retry only failed items"
    Write-Host "  lidarr-refresh <csv>         " -ForegroundColor Green -NoNewline
    Write-Host "- Process pending_refresh status items"
    Write-Host "  lidarr-artist <csv> <name>   " -ForegroundColor Green -NoNewline
    Write-Host "- Process albums by specific artist"
    Write-Host "  lidarr-quick <csv>           " -ForegroundColor Green -NoNewline
    Write-Host "- Fast import (no pauses, skip existing)"
    Write-Host "  lidarr-help                  " -ForegroundColor Green -NoNewline
    Write-Host "- Show this help message"
    Write-Host "`nFor full script help, run:" -ForegroundColor Cyan
    Write-Host "  py -3 add_albums_to_lidarr.py --help`n"
}

Write-Host "Lidarr shortcuts loaded! Type 'lidarr-help' for available commands." -ForegroundColor Green
```

### 3. Reload Your Profile

After saving the file, reload your profile:

```powershell
. $PROFILE
```

Or restart PowerShell.

## Available Commands

Once set up, you can use these shortcuts from any directory:

| Command | Description | Example |
|---------|-------------|---------|
| `lidarr-import <csv>` | Run full import with default settings | `lidarr-import albums.csv` |
| `lidarr-test <csv>` | Dry-run test on first 5 items | `lidarr-test albums.csv` |
| `lidarr-retry <csv>` | Retry only failed items | `lidarr-retry albums.csv` |
| `lidarr-refresh <csv>` | Process pending_refresh status items | `lidarr-refresh albums.csv` |
| `lidarr-artist <csv> <name>` | Process albums by specific artist | `lidarr-artist albums.csv "Drake"` |
| `lidarr-quick <csv>` | Fast import (skip existing, no pauses) | `lidarr-quick albums.csv` |
| `lidarr-help` | Show help for shortcuts | `lidarr-help` |

## Usage Examples

### Test before importing
```powershell
cd C:\path\to\your\csv
lidarr-test albums.csv
```

### Import everything
```powershell
lidarr-import albums.csv
```

### Retry failures
```powershell
lidarr-retry albums.csv
```

### Process specific artist
```powershell
lidarr-artist albums.csv "Travis Scott"
```

### Process pending albums (after metadata refresh)
```powershell
lidarr-refresh albums.csv
```

### Fast bulk import
```powershell
lidarr-quick albums.csv
```

## Troubleshooting

### Profile doesn't load on new terminals

Run this once to allow script execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Commands not found

Make sure you reloaded the profile:
```powershell
. $PROFILE
```

### Wrong path to script

Edit your profile and update the `$lidarrScriptPath` variable:
```powershell
notepad $PROFILE
```

### Need help with a specific command

Use the built-in help:
```powershell
Get-Help lidarr-import
Get-Help lidarr-artist
```

Or show all shortcuts:
```powershell
lidarr-help
```

## Advanced Usage

### Add custom shortcuts

You can add your own shortcuts to the profile:

```powershell
function lidarr-myworkflow {
    py -3 "$lidarrScriptPath\add_albums_to_lidarr.py" $args[0] --status pending_refresh --max-items 10
}
```

### Chain commands

Process pending items, then retry failures:
```powershell
lidarr-refresh albums.csv; lidarr-retry albums.csv
```

### Use with logging

Add logging to any command:
```powershell
lidarr-import albums.csv --log-file import.log
```

## Benefits of Using Shortcuts

- ✅ **Faster**: Type `lidarr-test albums.csv` instead of long command
- ✅ **Easier**: Remember simple command names
- ✅ **Consistent**: Same commands across all projects
- ✅ **Discoverable**: Use `lidarr-help` to see options
- ✅ **Flexible**: Still supports all original script arguments
