with open('start.ps1', 'r', encoding='utf-8') as f:
    c = f.read()

old_param = """param(
    [switch]$SkipDocker,       # Skip Docker container checks (for CI environments)
    [switch]$NoBrowser,        # Don't auto-open browser
    [switch]$Test              # Run test suite with REQUIRE_POSTGRES=1 and exit
)"""

new_param = """param(
    [switch]$SkipDocker,       # Skip Docker container checks (for CI environments)
    [switch]$NoBrowser,        # Don't auto-open browser
    [switch]$Test,             # Run test suite with REQUIRE_POSTGRES=1 and exit
    [switch]$Demo,             # Seed 7 demo GST invoices + EICAR test via live upload API
    [switch]$ResetDemo         # Wipe capture_jobs and re-seed clean IDP demo state
)"""

c = c.replace(old_param, new_param)

old_launch = 'Write-Header "Elixir EIM is running - press Ctrl+C in the frontend window to stop"'
new_launch = """if ($ResetDemo -or $Demo) {
    Write-Host "`n  [*] Seeding live IDP demo invoices via API..." -ForegroundColor Cyan
    & $PythonCmd -m cli.elixir_admin.main seed-idp-demo
}

Write-Header "Elixir EIM is running - press Ctrl+C in the frontend window to stop\""""

c = c.replace(old_launch, new_launch)

with open('start.ps1', 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print('Updated start.ps1 successfully')

