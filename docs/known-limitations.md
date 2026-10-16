# Known limitations and open issues

Last updated: 2026-10-16.

## Current state (after Phase 1)

1. **No business features yet.** There are no users, authentication, students, timetable, sessions, attendance, face
   recognition, or dashboards for students, faculty, or principals. The only working pages are the dashboard health
   view and the system-health view. Everything else is listed as "Planned" in the navigation.
2. **No authentication.** The API endpoints that exist (`/api/v1/health`, `/api/v1/health/database`) are public by design.
   They reveal only version, environment, timezone, and connectivity. They must not contain secrets. Authentication arrives in
   Phase 2, before any sensitive endpoint is added.
3. **Demo-data banner is static text.** The header says "Prototype: demo data only". It is a reminder, not a verified
   property of the data.
4. **Docker / docker-compose is not provided.** Docker is not available in the development sandbox. PostgreSQL must be
   installed locally, or the SQLite fallback must be used (documented in `installation-and-troubleshooting.md`).
5. **Windows instructions are not executed here.** The PowerShell commands in the README were written for Windows but were
   run only on Linux (Debian 12). A Windows student should report any command that differs.
6. **Tailwind pinned to 4.1.11.** Tailwind 4.0.0 with `@tailwindcss/vite` 4.0.0 failed to build in this environment because of a
   nested dependency mismatch. Both packages are pinned to 4.1.11 exactly. Re-test before upgrading.
7. **Frontend has no end-to-end (browser) tests.** Tests use Vitest with jsdom and mocked `fetch`. A Playwright
   suite is planned for Phase 7.
8. **Dependencies are pinned for reproducibility**, but these pins were chosen in this session and have not been audited for
   security advisories. Run `pip-audit` and `npm audit` before any demonstration on a shared network.

## Face-recognition and privacy (applies once Phase 4 begins)

9. **Model licence.** The InsightFace pretrained packs are documented as non-commercial research use only. See ADR-004. Any
   model used must have its weight licence recorded before use.
10. **No liveness or anti-spoofing.** A photograph or a video of a student could be presented to a camera. Basic face detection
    does not prevent this. Liveness detection is a future enhancement, and faculty review is the current safeguard.
11. **Recognition is probabilistic.** Thresholds must be chosen by measuring false acceptance and false rejection on a
    separate test set. No accuracy figure may be claimed until it has been measured.
12. **Bias and performance differences are unknown.** Performance may vary with skin tone, age, lighting, glasses, pose,
    and camera placement. A small local prototype cannot establish fairness across a population.
13. **Retention and consent are not yet implemented.** Deletion workflows and consent records are planned for Phase 4.

## Environment limitations

14. The development sandbox has no webcam, no classroom camera, and no GPU. Camera and live-recognition validation must be
    done locally by the team with consent.

## Security limitations of the Phase 1 foundation

15. **Request-size limit is partial.** The middleware rejects requests whose `Content-Length` header exceeds
    `MAX_REQUEST_BYTES`. A chunked request without `Content-Length` is not limited yet. Upload endpoints added in Phase 4
    must enforce a streamed limit.
16. **No rate limiting** on any endpoint. Login rate limiting is part of Phase 2.

## Phase 2 limitations (accounts, roles, seed data)

17. **Demo accounts are local-only.** `python -m app.cli seed-demo` creates synthetic students, faculty and users on the
    `demo.invalid` domain with the documented password `Demo-Local-2026!` (or `DEMO_PASSWORD`). Change or delete them
    before any real deployment. Never load the seed into a database that holds real records.
18. **New Phase 2 pages have not been checked in a real browser.** The sign-in, change-password, student, faculty, user
    account and dashboard screens are covered by unit tests with mocked `fetch`. Rendering, keyboard navigation and
    screen-reader behaviour still need a browser check.
19. **Login lockout is per account.** Five failed sign-ins lock an account for 15 minutes. Anyone who knows an email
    address can therefore lock out that person. There is no per-IP rate limit (see item 16). Accept this for the
    prototype and revisit before any shared deployment.
20. **No self-service password reset and no multi-factor authentication.** An administrator sets a temporary password
    and the person must change it at first sign-in. Losing the admin password needs a local command-line reset, which
    is not yet documented.
21. **Attendance rules are configurable, not official.** Thresholds such as the minimum attendance percentage and the
    late-arrival window will be stored as settings in Phase 3. They are not college regulations and must be confirmed
    by the institution before use.
22. **Session cookie `Secure` flag depends on the environment.** It is set only when `APP_ENV=production`. Local
    development uses plain HTTP. Production must sit behind HTTPS.
23. **Roll number is the student code.** The PRD speaks of roll numbers; the prototype stores one `student_code` per
    student and has no separate roll-number field.
24. **Student contact email is hidden from students themselves** in `/students/me`, returning `null`. This is a deliberate
    choice to keep the response minimal; a profile-editing screen is not implemented.
25. **PostgreSQL in the sandbox came from the `pgserver` PyPI package.** It was used only to verify the migrations and
    tests. It is not a project dependency. Local development instructions still use a standard PostgreSQL install.
