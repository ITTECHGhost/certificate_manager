# The Cerebrum

## Architectural Rules
- Always use the predefined UI themes and color palettes defined in `config.py`.
- Keep database interaction logic within `db.py` or use centralized queries from `data/queries.py` instead of scattering SQL throughout UI files.
- UI components should use `customtkinter` (CTk) classes where possible to maintain the modern appearance.
- Follow the established standard for creating screens (using the `SidePanel` and `RecordList` patterns as seen in other screens).
- Ensure new data models and tables are correctly versioned/migrated if the schema changes.

## Bug Ledger
-
