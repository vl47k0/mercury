# mercury

Per-user email store — Django + DRF + PostgreSQL, behind the authd edge.
Preserves the original RFC822 bytes and extracts normalized fields for
search/filter/threading. Model adapted from the reference `stored_email`
design with owner scoping (phoebe sub) + a Postgres tsvector.

- **Import**: `POST /api/v1/messages/` (multipart `files` = .eml), or
  `manage.py import_mail <owner> <path...> [--recursive]` (.eml dirs / .mbox).
- **Search**: tsvector over subject/from/preview/body + structured filters
  (from, read/archived/spam, has_attachments, label, mailbox, date range).
- **Auth**: authd validates the phoebe JWT and injects `X-JWT-Sub`; every
  message is scoped to that owner (dedup is per-owner by Message-ID).

## API (`/api/v1/`, behind authd at `/mail/`)
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `messages/` | list (filter/search) / import .eml |
| GET/PATCH/DELETE | `messages/<id>/` | detail / flags+labels / delete |
| GET | `messages/<id>/raw/` | download the original .eml |
| GET | `stats/` | totals (unread/archived/attachments) |

Query params: `q`, `from`, `is_read`, `is_archived`, `is_spam`,
`has_attachments`, `label`, `mailbox`, `list_id`, `after`, `before` (ISO).
