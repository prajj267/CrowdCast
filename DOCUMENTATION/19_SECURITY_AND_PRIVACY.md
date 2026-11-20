# 19 — Security and Privacy

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed controls; legal applicability must be confirmed by the team's institution |

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
