# 19 — Security and Privacy

| Field | Value |
|---|---|
| Version | 0.2 |
| Status | §1 and §7 hold as written. **§9 lists which controls the solo prototype implements and wins over §2–§6, §8**. Legal applicability must be confirmed with the institution if recording is ever reconsidered |

---

## 1. Privacy position

CROWDCAST needs **how many** people are where, not **who** they are. The design therefore follows data minimisation:

| Principle | Design consequence |
|---|---|
| No identification | No facial recognition, no face detection, no re-identification across cameras, no demographic inference (age/gender) |
| No appearance features | ByteTrack uses motion only; no appearance embeddings are computed |
| Ephemeral tracks | Track IDs and positions exist only in CV-worker memory for seconds; never persisted (no track table — NFR-PRV-02) |
| Aggregates only | The database stores per-zone per-minute counts, flows and mean speeds |
| Video stays local | Raw frames never leave the CV worker host; the API receives only numbers |
| Short retention | Raw recordings deleted within 30 days unless consented research annotation requires longer (NFR-PRV-03) |

Note: an aggregate over a *very small* zone with 1–2 people can still reveal an individual's presence. Dashboard and exports therefore do not show sub-minute data, and the historical export rounds counts below 5 as "<5" for zones flagged `sensitive` (e.g. facilities). This is a *Should* requirement.

## 2. Threat model (prototype)

| Asset | Threat | Control |
|---|---|---|
| Camera streams / recordings | Unauthorised viewing, leakage | Stored on encrypted disk; readable only by cv-worker container (read-only mount); camera URIs encrypted in DB (Fernet) and never returned by API |
| User accounts | Credential stuffing, weak passwords | Argon2id hashing, login throttling (5 / 10 min), minimum length 12, no default passwords |
| API | Unauthorised access, privilege escalation | JWT (15-min access, 7-day refresh in HttpOnly cookie), RBAC on every route, event-assignment checks |
| Ingestion | Forged observations | SERVICE API keys (hashed in DB), scoped to observation POST and own camera config; rotation via admin |
| Data integrity | Synthetic data mixed into real events | `data_origin` enforced; SYNTHETIC only for synthetic events unless ADMIN |
| Frontend | XSS, CSRF | React escaping; uploaded SVG sanitised; CSP header; refresh cookie `SameSite=Strict`; bearer token for API calls |
| Database | Exposure | Not published outside Docker network; least-privilege DB user for app; backups encrypted |
| Dependencies | Vulnerable packages | `pip-audit` and `npm audit` in CI; pinned versions |

## 3. Role-based permissions

| Capability | ADMIN | ORGANISER | OPERATOR | SERVICE |
|---|---|---|---|---|
| Manage users | ✔ | — | — | — |
| Create/edit venues, zones, connections | ✔ | ✔ | — | — |
| Create/edit events, schedules | ✔ | ✔ (own) | — | — |
| Assign operators | ✔ | ✔ (own events) | — | — |
| Register cameras, draw regions/lines | ✔ | — | — | — |
| View live / predictions / history / alerts | ✔ | ✔ (own events) | ✔ (assigned) | — |
| Acknowledge / resolve alerts | ✔ | ✔ | ✔ (assigned) | — |
| Ingest observations | ✔ (back-fill) | CSV import (MANUAL) | — | ✔ |
| Activate models | ✔ | — | — | — |
| View camera snapshots (configuration only) | ✔ | — | — | — |

Operators never see video in CROWDCAST. Live CCTV viewing, if needed, remains in the venue's existing CCTV system under its own governance.

## 4. Encryption

| Data | In transit | At rest |
|---|---|---|
| Browser ↔ API | HTTPS (Caddy; local CA in demo) | — |
| CV worker ↔ API | HTTPS or Docker-internal network on a single host | — |
| Database | Docker-internal network | Host full-disk encryption (BitLocker / LUKS / FileVault) |
| Camera URIs / credentials | — | Fernet (AES-128-CBC + HMAC) in DB column |
| Recordings | Copied only via encrypted drives | Encrypted volume; access list of named team members |

## 5. Camera and recording governance

1. Obtain written approval from the institution (ethics committee or equivalent) and the event organiser **before** recording.
2. Comply with applicable data-protection law (for example the EU GDPR, India's Digital Personal Data Protection Act 2023, or the local equivalent) — the team must confirm which applies with their institution.
3. Post visible notices at recorded areas stating purpose, contact and retention.
4. Staged scenarios: informed written consent from every volunteer, with the right to withdraw (their segments deleted).
5. Camera placement: overhead/elevated angles that capture crowds, not close-up faces; avoid toilets, changing areas and private spaces entirely.
6. Annotation by team members only, on encrypted machines; no upload of footage to third-party annotation services.
7. Footage is never published in the repository, reports or presentations unless faces are blurred and consent covers publication.

## 6. Data retention

| Data | Retention | Deletion |
|---|---|---|
| Raw recordings | ≤ 30 days; extended only for consented, annotated research clips until project end | Scheduled job + manual verification log |
| Annotations (points/counts) | Project duration | Contain no images |
| Observations, predictions, alerts | 12 months (configurable) | Nightly job |
| Audit log | 12 months | Nightly job |
| User accounts | Until deactivated + 30 days | Admin action |

## 7. Limitations of camera-based monitoring (ethical and technical)

- **Function creep:** infrastructure built for counting could be repurposed for surveillance. Mitigation: architecture that never stores identities, documented purpose limitation, code review of any change touching M2.
- **Chilling effect:** visible cameras can change behaviour and deter attendance. Notices should explain that only counts are kept.
- **Unequal accuracy:** detectors may perform differently across clothing, lighting, or body sizes, and in dense groups; undercounting dense areas could under-warn exactly where risk is highest. Reported via density-band evaluation.
- **Coverage gaps:** absence of detections in blind spots is not evidence of absence of people.
- **Automation bias:** operators may over-trust forecasts. The UI shows intervals and fallback status, and CROWDCAST is documented as decision support, not a safety system.

## 8. Security testing

Role matrix tests (TC-API-01), negative validation tests, throttling test (TC-API-08), dependency audit, manual review against OWASP API Security Top 10 (2023) before the final demo.

## 9. Solo implementation (v0.2, 9.4 audit)

The prototype is built and run by one developer on one laptop, uses **no own recordings** (D6: public datasets and public clips only) and has **no authentication** (D7). Everything listens on `127.0.0.1` ([18](18_DEPLOYMENT_PLAN.md)). The privacy position in §1 is implemented; most of the access controls in §2–§4 protect things that do not exist in this scope.

| Control (section) | Status |
|---|---|
| No identification, no appearance features, ephemeral tracks, aggregates only (§1) | **Implemented.** YOLOX person boxes and the in-house ByteTrack use geometry and motion only; tracks live in memory during a `run_camera` run; the database has no per-person table or column. Checked over the whole git history by `scripts/privacy_check.sh` (WORKFLOW 9.3), which also runs in CI |
| Video stays local (§1) | **Implemented.** Public clips and datasets sit in git-ignored folders (`videos/`, `data/`); only per-minute aggregates are posted |
| Short retention of recordings (§1, §6) | Not applicable (no own recordings); no deletion job for database rows. Logged in the WORKFLOW Deviation log (2026-11-22) |
| "<5" rounding for `sensitive` zones in exports (§1, Should) | **Not built.** No `sensitive` zone flag exists; the History CSV export writes exact counts. The data are SYNTHETIC or counts from public footage |
| User accounts, JWT, RBAC, event assignment, login throttling (§2, §3) | **Not built (D7).** No users or roles; every endpoint is open to anyone who can reach `127.0.0.1:8000`. Acceptable only for a local, single-user prototype; required before any shared or networked deployment |
| SERVICE API keys for ingestion (§2) | **Not built (D7).** Any local process can post observations |
| `data_origin` enforcement (§2) | **Implemented** without the ADMIN exception: SYNTHETIC rows are refused for real events, REAL rows need a LIVE event and may not lie more than 2 min in the future (`ingestion/validation.py`; tests in `test_api_ingestion.py`) |
| Camera URIs encrypted (Fernet), never returned (§2, §4) | **Not built.** Camera configuration is a local YAML file pointing at a public clip; there are no camera endpoints ([14 §6](14_API_SPECIFICATION.md)) |
| Frontend XSS / CSRF (§2) | React escaping only. No CSP header, no cookies (no auth), no SVG upload |
| Database exposure (§2, §4) | Port bound to `127.0.0.1` in `docker-compose.yml`; credentials from `.env` (never committed). No separate least-privilege user, no backups ([18 §6](18_DEPLOYMENT_PLAN.md)) |
| Dependency audit (§2, §8) | **Not built.** Versions are locked (`uv.lock`, `package-lock.json`); `pip-audit` / `npm audit` are not in CI |
| HTTPS (§4) | Not used; all traffic is on the loopback interface |
| Recording governance (§5) | Not triggered (D6). If recording is ever reconsidered, §5 applies in full and approval comes first |
| Security testing (§8) | Role and throttling tests not applicable (D7). Validation tests exist ([17 §5](17_TESTING_STRATEGY.md)). No OWASP review has been done |

## 10. Change log

| Version | Date | Change |
|---|---|---|
| 0.2 | 2026-11-23 | §9 added (9.4 audit, F-19): what the solo prototype implements; auth controls out of scope (D7) |
| 0.1 | — | Team plan |
