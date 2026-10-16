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
