# Production database backup and restore runbook

## Scope and controls

Only a designated operator may run backup/restore. Record the change ticket,
operator, checker, source database, target database, backup manifest SHA-256,
and evidence ID before touching a live system. Never restore over the source
database; restore into an isolated instance first.

## Backup

```powershell
python backend/scripts/backup_production_db.py `
  --db-url "$env:DB_URL" `
  --output "D:\secure-backups\swift\swift-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
```

The script requires a PostgreSQL URL and `pg_dump`, uses custom format with
`--no-owner --no-privileges`, and writes a sidecar manifest containing size,
timestamp and SHA-256. `[EXT-BLOCKED]` means the PostgreSQL client package is
not installed; do not substitute SQLite or a logical JSON export.

## Restore rehearsal

1. Provision an isolated PostgreSQL instance at the target version and apply
   network/credential controls.
2. Verify the dump SHA-256 against the sidecar manifest and copy it into the
   isolated host.
3. Restore without overwriting ownership or grants:

   ```bash
   createdb -h TARGET_HOST -U postgres swift_restore_rehearsal
   pg_restore --clean --if-exists --no-owner --no-privileges \
     --dbname "$TARGET_URL" swift-YYYYMMDD-HHMMSS.dump
   ```

4. Run `alembic upgrade head`, `python backend/scripts/verify_production_schema.py`
   and the read-only production audit. Compare row counts, tenant counts,
   ledger balances and evidence hashes with the pre-restore snapshot.
5. Run the two-control sign-off: maker records the restore plan and checker
   independently verifies the manifest, schema contract and reconciliation.
6. Capture RTO/RPO, validation output and evidence ID. Only then authorize a
   controlled cutover; retain the source instance unchanged until sign-off.

## Failure and rollback

If hash verification, migration, schema verification, RLS, or reconciliation
fails, stop the cutover, preserve the isolated instance and logs, and open an
incident. Rollback is traffic re-routing to the unchanged source instance;
never delete the source data as part of recovery.
