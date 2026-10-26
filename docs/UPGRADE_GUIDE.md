# Elixir EIM - Upgrade Guide & Migration Procedures

## Zero-Downtime Upgrade Principles
1. **Semantic Versioning:** Upgrades follow SemVer (`MAJOR.MINOR.PATCH`).
2. **Expand / Contract Migrations:**
   - **Phase 1 (Add):** Add new tables, columns (nullable), and non-blocking indexes. Backward compatible with release $N$.
   - **Phase 2 (Dual Write & Backfill):** Release $N+1$ writes both formats; background job backfills existing rows.
   - **Phase 3 (Switch Reads):** Read queries point to the new schema representation.
   - **Phase 4 (Contract):** Once all instances run $N+1$, drop deprecated columns in release $N+2$.

## Step-by-Step Upgrade Procedure
1. **Preflight Check:**
   ```bash
   elixir-admin check-upgrade
   ```
2. **Run Forward Database Migrations:**
   ```bash
   elixir-admin migrate
   ```
3. **Verify Audit Chain Integrity:**
   ```bash
   elixir-admin verify-audit-chain
   ```
4. **Deploy Application Container:**
   Deploy new application containers with blue/green or rolling deployment.
5. **Reindex Search (if schema evolved):**
   ```bash
   elixir-admin reindex --all
   ```

## Rollback Procedure
If an issue occurs before the contract phase:
1. Roll back application containers to release $N$.
2. Database schema changes made during Expand phase remain compatible with release $N$.
