# 02 — Docker and PostgreSQL

## PostgreSQL

A relational database server: data lives in **tables** (rows and columns), queried with SQL. We
use version 16. It stores venues, zones, events, crowd observations, predictions and alerts
(doc 13). Unlike a CSV file, it enforces rules (note 03), lets many parts of the app read and
write safely at the same time (transactions, note 04), and answers queries quickly using indexes.

## Docker in four words: image, container, volume, port

| Term | Meaning | In CROWDCAST |
|---|---|---|
| **Image** | A read-only package of a program plus everything it needs | `postgres:16-alpine` (official Postgres on a small Linux) |
| **Container** | A running instance of an image, isolated from your system | `crowdcast-db` |
| **Volume** | Storage that survives when the container is deleted | `crowdcast-pgdata` holds the database files |
| **Port mapping** | Connects a port on your PC to a port in the container | `127.0.0.1:5432 → 5432` |

`docker-compose.yml` describes all of this in one file, so `docker compose up -d db` starts the
database the same way every time.

## Why run Postgres in Docker but Python natively?

- Installing Postgres on Windows directly is fiddly and leaves a background service running;
  in Docker it is one command to start, stop or throw away.
- Python runs natively because the CV and ML code needs direct, fast access to the CPU and files,
  and debugging is simpler.

## Two details worth knowing

- **Bound to `127.0.0.1`:** the database is reachable only from this computer, not from the
  network. Safer, since the credentials are simple development ones.
- **`127.0.0.1` instead of `localhost`:** on this machine `localhost` is tried as IPv6 first,
  Docker listens on IPv4 only, and the connection stalled. Using the IPv4 address directly
  avoids it (recorded in `CLAUDE.md` §10).
- The container's time zone is UTC (`TZ`, `PGTZ`), matching note 05.

## Viva questions

- **What happens to the data if the container is deleted?** Nothing; it lives in the named volume.
  Deleting the volume deletes the data.
- **Is Docker a virtual machine?** No. Containers share the host's kernel and isolate processes
  and files; they are lighter than a VM. (On Windows, Docker Desktop runs them inside a small
  Linux VM via WSL 2.)
