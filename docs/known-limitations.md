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

9. **Model licence (partly resolved).** The project uses OpenCV YuNet (MIT) and SFace (Apache-2.0). The weight licences
   were read from the upstream folders, and the InsightFace packs are not used (ADR-004, ADR-009). The **training-data
   terms of SFace are not stated** and are unverified, and YuNet's WIDER FACE training data needs institutional review.
10. **No liveness or anti-spoofing.** A photograph or a video of a student could be presented to a camera. Basic face detection
    does not prevent this. Liveness detection is a future enhancement, and faculty review is the current safeguard.
11. **Recognition is probabilistic.** Thresholds must be chosen by measuring false acceptance and false rejection on a
    separate test set. No accuracy figure may be claimed until it has been measured.
12. **Bias and performance differences are unknown.** Performance may vary with skin tone, age, lighting, glasses, pose,
    and camera placement. A small local prototype cannot establish fairness across a population.
13. **Retention and consent are implemented but must be operated.** Consent records, withdrawal with deletion, and a
    retention purge exist (Phase 4). The purge runs only when an operator runs `python -m app.cli purge-biometrics`. Nothing
    schedules it. The retention period (default 365 days) is a setting, not an approved institutional policy.

## Environment limitations

14. The development sandbox has no webcam, no classroom camera, and no GPU. Camera and live-recognition validation must be
    done locally by the team with consent.

## Security limitations of the Phase 1 foundation

15. **Request-size limit is partial.** The middleware rejects requests whose `Content-Length` header exceeds the limit for
    that route. Enrolment uploads (20 images at 3 MB) and video uploads (`MAX_VIDEO_UPLOAD_BYTES`, 100 MB) have their own
    limits, and each file is read in capped chunks. A chunked request without `Content-Length` to other endpoints is still
    not limited.
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
21. **Attendance rules are configurable, not official.** The recognition rules (match threshold, margin, 5 observations
    over 2.0 s, 0.4 s minimum gap, roster-only) are settings in `backend/app/core/config.py`. Attendance-percentage and
    late-arrival rules are not yet implemented (Phase 5). None of these values are college regulations, and the
    institution must confirm them before use.
22. **Session cookie `Secure` flag depends on the environment.** It is set only when `APP_ENV=production`. Local
    development uses plain HTTP. Production must sit behind HTTPS.
23. **Roll number is the student code.** The PRD speaks of roll numbers; the prototype stores one `student_code` per
    student and has no separate roll-number field.
24. **Student contact email is hidden from students themselves** in `/students/me`, returning `null`. This is a deliberate
    choice to keep the response minimal; a profile-editing screen is not implemented.
25. **PostgreSQL in the sandbox came from the `pgserver` PyPI package.** It was used only to verify the migrations and
    tests. It is not a project dependency. Local development instructions still use a standard PostgreSQL install.

## Phase 3 limitations (timetable and sessions)

26. **Timetable entries are managed through the API only.** No timetable screen exists yet. Holidays and one-off
    schedule changes are not modelled. A cancelled class must be handled by cancelling its session.
27. **Times are naive datetimes treated as UTC when the API receives them without an offset.** Clients should send an
    offset. The institutional timezone (`Asia/Kolkata`) is used for period resolution.

## Phase 4 limitations (enrolment and recognition)

28. **No measured accuracy.** No false-accept, false-reject, or speed figure exists for this project. Thresholds
    (0.363 cosine, 0.05 margin) are defaults from OpenCV and are **not calibrated** on any local data. Do not describe the
    system as accurate. Measure on a separate, consented test set first (`face-recognition.md`, section 8).
29. **Camera path not tested on hardware.** The sandbox has no webcam or classroom camera. The live camera run has never
    read from a real device. The video-file run uses the same code path, and it was tested with synthetic videos.
30. **Test faces are synthetic.** The automated tests use generated images with marker pixels. They test the logic, not
    face recognition. The real-model test is a smoke test on upstream sample photos (no accuracy claim).
31. **No liveness or anti-spoofing** (also item 10). A photograph or a screen showing a student could be accepted.
32. **Single-process job state.** Camera and video runs are threads inside the API process, and their state is held in
    memory. A restart stops the runs. Multiple worker processes would not see each other's jobs.
33. **Recognition runs cannot be resumed.** A stopped or crashed run keeps the rows already written. Re-running is safe
    (no duplicates), but unfinished faces are not re-checked from where they stopped.
34. **Look-alike students.** Two enrolled students with similar appearance may give `uncertain` results, which are never
    counted. A genuinely present student can then be missed. Faculty corrections arrive in Phase 5.
35. **Enrolment photos are stored only as embeddings, and the embeddings are personal data.** Keep the database on
    controlled storage and do not copy it into shared folders. The institution must decide who may enrol students.
36. **Model replacement needs re-enrolment.** Embeddings from another model are ignored until the student is enrolled again,
    so a model change silently reduces matches until re-enrolment is done. The status endpoint shows the model name.
37. **Uploaded videos are processed on the server with OpenCV.** Malformed files are rejected only by their first bytes.
    OpenCV's decoder is not sandboxed. Run the server with least privilege, and accept videos only from trusted staff.
38. **Frontend screens for consent, enrolment, and recognition are not built.** The endpoints are tested through the API
    only. Administrators use the API documentation (`/api/docs`, development only) until the screens are added.

