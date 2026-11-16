# Docker Compose

Part of [[Home]]. Introduced in [[V3 - First RAG System]] (step 1). Commands are wrapped by [[poethepoet]] (`poe up`, `poe down`, `poe psql`).

## What it is / problem it solves

A declarative file (`compose.yaml`) that says which containers this project needs, with which image, ports, environment and storage, and a CLI (`docker compose`) that makes reality match it. **The Java analogy: `pom.xml` for infrastructure.** You declare *what* is needed — "Postgres 18 with pgvector 0.8.7" — and the tool fetches and runs it; nobody installs it by hand, so every machine gets the same thing.

Vocabulary, mapped:

| Compose | Means | Java-world analogue |
| --- | --- | --- |
| image | a frozen, versioned filesystem + start command | a released artifact (`groupId:artifactId:version`) |
| container | a running instance of an image | a running JVM started from that jar |
| service | a named container definition in `compose.yaml` | a `<dependency>` entry, but for a process |
| volume | storage that outlives the container | a database's data directory on disk |
| healthcheck | a command Docker runs to decide "ready", not just "started" | a Spring Boot actuator `/health` probe |

## Why we're using it here

### Decision (2026-11-16, V3 step 1): one service, pgvector's image, pinned

- **Image `pgvector/pgvector:0.8.7-pg18`** — official Postgres with pgvector prebuilt (option A). Building pgvector into the official `postgres` image ourselves (B) re-does published work; a Homebrew install (C) breaks reproducibility. Tag found 2026-11-16 by listing tags: `curl -s "https://hub.docker.com/v2/repositories/pgvector/pgvector/tags?page_size=100&ordering=last_updated"`.
- **Pinned to `<pgvector version>-pg<major>`, never `latest`.** The tag is still *rebuilt* upstream for OS patches; byte-level immutability would need a `@sha256:` digest. Not worth it for local dev — the pgvector and Postgres versions are what change results.
- **Named volume, not a bind mount into `data/`.** Database files stay out of the repo tree and away from Spotlight/backup tools that touch files under a running Postgres.
- **Port bound to `127.0.0.1`.** The password is committed; binding to localhost is what makes that harmless.
- **`CREATE EXTENSION` lives in the schema SQL, not in an init script** — the learner's choice. `/docker-entrypoint-initdb.d/` scripts run only when the volume is first created and are silently skipped afterwards.

## Alternatives considered

- Dedicated vector DB (Qdrant, Chroma, …) — rejected 2026-08-22, see [[V3 - First RAG System]] Decisions.
- Testcontainers (start a throwaway DB per test run) — the JUnit-world habit; deferred until a test actually needs a live database.

## Used in

- [[V3 - First RAG System]] — Postgres + pgvector.
- Expected: [[V12 - Production-Oriented System]] — containerising the application itself.

## Notes

- **Postgres 18 moved the data directory.** From the 18 image on, `PGDATA` is `/var/lib/postgresql/18/docker` and the volume belongs at `/var/lib/postgresql`. Mounting at the old `/var/lib/postgresql/data` is the pre-18 habit found in most tutorials. Source: the "PGDATA" section of hub.docker.com/_/postgres.
- **`docker compose down` keeps the volume; `down -v` deletes the data.** There is deliberately no poe task for `-v`.
