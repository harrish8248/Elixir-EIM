import os
import subprocess
from pathlib import Path

def get_dir_size_mb(path):
    p = Path(path)
    if not p.exists():
        return 0.0
    total = 0
    try:
        if p.is_file():
            return p.stat().st_size / (1024 * 1024)
        for root, dirs, files in os.walk(p):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except Exception:
        pass
    return total / (1024 * 1024)

print("--- TOP-LEVEL DIRECTORIES ---")
for entry in sorted(os.listdir(".")):
    size_mb = get_dir_size_mb(entry)
    print(f"{entry:<30} : {size_mb:>10.2f} MB")

print("\n--- OCR BENCHMARK BY SUBFOLDER ---")
bench_dir = Path("docs/ocr-benchmark")
if bench_dir.exists():
    for sub in bench_dir.iterdir():
        if sub.is_dir():
            print(f"{str(sub):<35} : {get_dir_size_mb(sub):>10.2f} MB")

print("\n--- CACHES & TEMPS ---")
caches = [
    ".venv",
    "apps/web/node_modules",
    "apps/web/dist",
    "storybook-static",
    "tessdata",
    "models",
    os.path.expanduser("~/.cache"),
    os.path.expanduser("~/.pip"),
]
for c in caches:
    print(f"{c:<45} : {get_dir_size_mb(c):>10.2f} MB")

# Check WSL ext4.vhdx
wsl_vhdx = list(Path(os.path.expanduser("~/AppData/Local/Docker/wsl/data")).glob("*.vhdx"))
if not wsl_vhdx:
    wsl_vhdx = list(Path(os.path.expanduser("~/AppData/Local/Packages")).glob("**/ext4.vhdx"))
print("\n--- WSL VHDX FILES ---")
for v in wsl_vhdx:
    print(f"{str(v):<60} : {v.stat().st_size / (1024*1024):>10.2f} MB")

