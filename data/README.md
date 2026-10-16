# Local-only data folder

This folder is for **local, non-committed** data only. Everything here except this README is ignored by Git
(see the root `.gitignore`).

Intended contents (created by later phases):

| Path | What it holds | Sensitivity |
|---|---|---|
| `data/enrollment/<student_id>/` | Consented enrollment photos, if retention is enabled | Biometric - restricted |
| `data/attendance.db` | Local SQLite database, only if the SQLite fallback is used | Personal data |
| `data/exports/` | CSV reports generated for authorised users | Personal data |

Rules:

1. Never copy real student photos, embeddings, or exports into the Git repository.
2. Use synthetic data for development. Real-data testing requires documented consent and institutional approval.
3. Delete the contents of this folder when a demo or evaluation run is finished, unless retention has been approved.
