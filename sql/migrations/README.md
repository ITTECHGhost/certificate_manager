# Database migrations

A server update (`setup_server.bat` from the bundle) runs `certificate_manager_api\migrate.py`:

1. **Every file here named `NNNN_short_name.sql` runs once** on each server, in number order. The table
   `schema_migrations` records what ran.
2. **Then all of `sql\SP.sql` is re-applied** (every procedure is `DROP … IF EXISTS` + `CREATE`).

## Rules

- **Changing a stored procedure:** edit `sql\SP.sql` only. No migration is needed.
- **Changing a table or data:** add the next number, e.g. `0001_add_student_photo.sql`. Never edit a
  file after it has been released, because the server refuses a migration that changed after it ran.
  Fix it with a new number instead.
- Write migrations so they are safe to run again where you can, e.g. `IF NOT EXISTS`, or checks on
  `information_schema`.
- **No `USE`, no `CREATE USER`, and no passwords** in migrations. They run with the API's own login.
- `DEFINER=…` clauses are removed automatically.

`sql\fixes\` holds the scripts from before this system. They were run by hand and are not run again.

Before updating the server, check what will run on your laptop:

```
py certificate_manager_api\migrate.py --sql-dir sql --dry-run
```
