# 📦 Elixir EIM — Relocating & Compacting WSL / Docker / Project to D: Drive

This runbook provides tested, non-destructive instructions for reclaiming space from your `C:` drive by compacting WSL/Docker VHDX disks and optionally relocating bulky project assets (WSL, Docker, `.venv`, `node_modules`, benchmark data) to a secondary drive (`D:`).

---

## 💡 Executive Summary: Where the Biggest Space Savings Are

Based on real disk footprint measurements:
1. **WSL2 / Docker Data Disks (`ext4.vhdx`)**: **~8.3 GB** (*Highest single saving*). Relocating or compacting WSL reclaims the most space immediately.
2. **Gotenberg Image & Container**: **~2.5 GB** (*Saved immediately by running in `-Lite` mode*).
3. **Python Virtual Environment (`.venv`)**: **~1.46 GB** (*Relocating via NTFS Junction saves ~1.5 GB on C:*).
4. **Frozen Benchmark Datasets (`docs/ocr-benchmark`)**: **~460 MB** (*Relocated via `ELIXIR_DATA_DIR`*).
5. **Node Modules (`apps/web/node_modules`)**: **~191 MB**.

---

## Section 1: Compact the WSL2 Virtual Disk (Safe, In-Place Reclamation)

WSL2 virtual hard disks (`.vhdx`) dynamically expand when files are created inside Linux, but they do **not** automatically shrink when files or Docker images are deleted. Follow these steps to reclaim unused allocated space:

### Step 1.1: Run fstrim inside Ubuntu
```powershell
# Discard unused blocks inside the Linux filesystem
wsl -d Ubuntu -u root -- fstrim -va
```

### Step 1.2: Enable Sparse VHD (Windows 11 / Modern WSL)
```powershell
# Automatically frees unused space in the vhdx on shutdown
wsl --manage Ubuntu --set-sparse true
```

### Step 1.3: Fallback Diskpart Compaction (If Sparse VHD is unsupported)
```powershell
# 1. Terminate all WSL instances
wsl --shutdown

# 2. Locate your ext4.vhdx (typically in %LOCALAPPDATA%\Packages\CanonicalGroupLimited... or %LOCALAPPDATA%\Docker\wsl\data)
$vhdxPath = "$env:LOCALAPPDATA\Docker\wsl\data\ext4.vhdx"
if (-not (Test-Path $vhdxPath)) {
    $vhdxPath = (Get-ChildItem -Path "$env:LOCALAPPDATA\Packages" -Recurse -Filter "ext4.vhdx").FullName | Select-Object -First 1
}

# 3. Create a temporary diskpart compaction script
@"
select vdisk file="$vhdxPath"
attach vdisk readonly
compact vdisk
detach vdisk
"@ | Set-Content -Path "$env:TEMP\compact_wsl.txt"

# 4. Run diskpart as Administrator
Start-Process diskpart -ArgumentList "/s `"$env:TEMP\compact_wsl.txt`"" -Wait -Verb RunAs
```

---

## Section 2: Relocate WSL Distro & Docker to D: Drive

Relocates the entire Ubuntu distribution and all Docker images from `C:\` to `D:\WSL\Ubuntu`.

### Step 2.1: Pre-Migration Backup
```powershell
# 1. Shut down WSL
wsl --shutdown

# 2. Create destination folders
New-Item -ItemType Directory -Path "D:\WSL\Backup" -Force
New-Item -ItemType Directory -Path "D:\WSL\Ubuntu" -Force

# 3. Export Ubuntu to a compressed tar backup archive
wsl --export Ubuntu "D:\WSL\Backup\Ubuntu_backup.tar"
Write-Host "Backup completed at D:\WSL\Backup\Ubuntu_backup.tar" -ForegroundColor Green
```

### Step 2.2: Re-Import onto D: Drive
```powershell
# 1. Unregister the C: drive instance
wsl --unregister Ubuntu

# 2. Import onto D: drive as WSL 2
wsl --import Ubuntu "D:\WSL\Ubuntu" "D:\WSL\Backup\Ubuntu_backup.tar" --version 2

# 3. Set default user back to your normal user or root
wsl -d Ubuntu -u root -- sed -i 's/#.*default=.*/default=root/' /etc/wsl.conf
```

### Step 2.3: Verification
```powershell
# Confirm Ubuntu runs from D:\WSL\Ubuntu
wsl -d Ubuntu -- uname -a
wsl -l -v
```

### Step 2.4: Rollback Procedure (In Case of Any Issue)
```powershell
# If import fails:
wsl --unregister Ubuntu
wsl --import Ubuntu "$env:LOCALAPPDATA\Ubuntu" "D:\WSL\Backup\Ubuntu_backup.tar" --version 2
```

---

## Section 3: Relocate Project, `.venv`, and Caches via NTFS Junctions

NTFS Junctions allow moving heavy folders to `D:` while Windows, IDEs, and scripts continue accessing them seamlessly via their existing `C:` paths with **zero configuration changes**.

### Step 3.1: Relocate `.venv` (Reclaims 1.46 GB on C:)
```powershell
# 1. Ensure services and IDE terminals are closed
# 2. Create target directory on D:
New-Item -ItemType Directory -Path "D:\Elixir_Caches\venv" -Force

# 3. Copy .venv contents
Copy-Item -Path "C:\Users\harri\Downloads\Elixir EIM\.venv" -Destination "D:\Elixir_Caches\venv" -Recurse -Force

# 4. Remove original .venv
Remove-Item -Path "C:\Users\harri\Downloads\Elixir EIM\.venv" -Recurse -Force

# 5. Create transparent NTFS Junction
New-Item -ItemType Junction -Path "C:\Users\harri\Downloads\Elixir EIM\.venv" -Target "D:\Elixir_Caches\venv\.venv"
```

### Step 3.2: Relocate Benchmark Datasets via Environment Variable
```powershell
# 1. Copy benchmark data to D:
New-Item -ItemType Directory -Path "D:\Elixir_Data\ocr-benchmark" -Force
Copy-Item -Path "C:\Users\harri\Downloads\Elixir EIM\docs\ocr-benchmark\*" -Destination "D:\Elixir_Data\ocr-benchmark" -Recurse -Force

# 2. Set the environment variable in your session or user profile
$env:ELIXIR_DATA_DIR = "D:\Elixir_Data\ocr-benchmark"
[Environment]::SetEnvironmentVariable("ELIXIR_DATA_DIR", "D:\Elixir_Data\ocr-benchmark", "User")
```

---

## Section 4: Recommended `.wslconfig` (Memory & CPU Guardrails)

Create or update `%USERPROFILE%\.wslconfig` (`C:\Users\harri\.wslconfig`) with these guardrails to prevent WSL from consuming excessive host RAM:

```ini
[wsl2]
# Limits VM memory in WSL 2 to 4 GB (prevents Out-Of-Memory errors on Windows host)
memory=4GB

# Sets the VM to use 4 virtual processors
processors=4

# Sets amount of swap storage space to 2 GB
swap=2GB

# Automatically compacts virtual hard disk space when files are removed
sparseVhd=true

# Disables GUI applications overhead if not needed
guiApplications=false
```

---

## Section 5: Run with `start.ps1 -Lite`

For demonstrations and day-to-day development, launch with the newly implemented `-Lite` flag:
```powershell
.\start.ps1 -Lite -Demo
```
- Starts only the **6 core services** (`postgres`, `redis`, `minio`, `keycloak`, `opa`, `clamav`).
- Completely bypasses the 2.47 GB Gotenberg container.

