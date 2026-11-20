# 04 — SQLAlchemy and Alembic

## SQLAlchemy: Python classes ↔ database tables

An **ORM** (object-relational mapper) lets you describe a table as a Python class and work with
rows as objects:

```python
class Zone(Base):
    __tablename__ = "zones"
    zone_id: Mapped[int] = pk()
    code: Mapped[str] = mapped_column(String(16))
```

- **Engine:** knows how to connect to the database (`crowdcast/storage/db.py`, `get_engine()`).
- **Session:** a unit of work. You add/change objects, then `commit()` writes them all at once.
  `session_scope()` commits if the block succeeds and **rolls back** if it raises.

## Transactions

A transaction groups statements so they either *all* happen or *none* do. Commit = make
permanent; rollback = undo everything since it began. Tests use this: each test runs in a
transaction that is always rolled back, so the database is unchanged afterwards.

## Alembic: version control for the schema

Code changes are tracked by git; **schema** changes are tracked by Alembic **migrations** — small
Python files in `crowdcast/storage/migrations/versions/`, each with:

- `upgrade()` — apply the change (create tables, add a column...),
- `downgrade()` — undo it.

`alembic upgrade head` brings any database to the latest version. `--autogenerate` compares the
ORM models with the live database and drafts a migration — which must be **reviewed**, because
it misses some things (for example it did not drop our enum types in `downgrade`, so we added
`DROP TYPE` by hand). We verified upgrade → downgrade → upgrade works.

## A real bug we hit (good viva story)

The first migration "succeeded" but created no tables. Cause: `env.py` ran `SET TIME ZONE 'UTC'`
before Alembic started. That statement silently *opened a transaction*; Alembic then thought a
transaction was already in progress and never committed, so everything was rolled back when the
connection closed. Fix: set the time zone as a **connection option**
(`connect_args={"options": "-c TimeZone=UTC"}`), which runs no statement. Lesson: check the
result (list the tables), not just the exit message.

## Viva questions

- **Why migrations instead of `create_all()`?** Migrations record every schema change in order,
  can be undone, and upgrade an existing database without losing its data.
- **What is a session?** A short-lived workspace that tracks objects you load or change and writes
  them in one transaction on commit.
