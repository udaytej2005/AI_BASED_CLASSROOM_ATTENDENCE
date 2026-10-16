# Architecture decisions

Each decision has a status: **Accepted**, **Provisional** (to be revisited when evidence arrives), or **Deferred**.

## ADR-001: Python + FastAPI backend with SQLAlchemy and Alembic

- **Status:** Accepted
- **Context:** The face-recognition code is Python (OpenCV, pretrained models). The API must validate data, document itself,
  and be easy to test.
- **Decision:** FastAPI for the HTTP API (automatic OpenAPI docs, Pydantic validation), SQLAlchemy 2.x for database access,
  Alembic for migrations, pytest for tests.
- **Reasons:** One language for the API and the computer-vision code, typed request models, mature migration tooling, and
  a well-known stack for a student to explain in a viva.

## ADR-002: PostgreSQL as the intended database, with SQLite only for tests and as a documented fallback

- **Status:** Accepted
- **Context:** The PRD names PostgreSQL. Concurrent writes from the camera worker, the API, and dashboards are a realistic
  requirement, and PostgreSQL enforces constraints and types more strictly than SQLite.
- **Decision:** Configuration targets PostgreSQL (`postgresql+psycopg://...`). Automated tests run on SQLite for speed and
  isolation. The full test suite also runs against PostgreSQL 16.2 (sandbox, via `TEST_DATABASE_URL`). The repository keeps
  the database code portable by avoiding vendor-specific SQL.
- **Consequence:** Docker Compose is the easiest PostgreSQL path, but Docker is not available in the sandbox. Docker Compose
  is therefore **not yet provided** and will be added only when it can be tested.

## ADR-003: React + TypeScript + Vite frontend with Tailwind CSS v4, React Router, and a dev-server proxy

- **Status:** Accepted
- **Context:** The PRD recommends React and Vite. The UI needs routing, role-specific navigation, and tables/charts later.
- **Decision:** React 18.3, TypeScript (strict), Vite 6, Tailwind CSS 4.1.11 (`@tailwindcss/vite`), React Router 6, Vitest and
  Testing Library for tests, ESLint 9 for linting. The browser calls only relative `/api/v1/...` URLs. Vite proxies them to
  FastAPI, so no backend address is embedded in browser code.
- **Consequence:** Tailwind 4.0.0 with `@tailwindcss/vite` 4.0.0 produced a build error in this environment (mismatched
  nested `tailwindcss` version). Both are now pinned to 4.1.11 exactly.

## ADR-004: Face-recognition model selection and licence (Phase 4 decision; research so far)

- **Status:** Deferred to Phase 4, with a documented constraint.
- **Findings:**
  - The InsightFace **library** is MIT-licensed.
  - The popular InsightFace **pretrained packs** (`buffalo_l`, `buffalo_s`, `antelopev2`) are released for **non-commercial research
    use only**, according to the InsightFace product page ([insightface.ai](https://www.insightface.ai/)) and third-party
    documentation that repeats the same restriction (for example [LocalAI](https://localai.io/docs/features/face-recognition/index.html)).
    Those pages were read on 2026-10-16 and must be re-checked against the official model page before use.
  - LocalAI's documentation also lists a YuNet + SFace option (OpenCV Zoo) as Apache 2.0. This still needs to be verified
    against the upstream model cards before it is relied on.
- **Implication for this project:** It is an academic prototype, so non-commercial research use may be acceptable. The
  licence must still be stated in the thesis, and the code must keep the recognition engine behind a replaceable adapter
  so the model can be swapped without rewriting the attendance logic.
- **Decision for Phase 4:** Implement a `FaceRecognizer` adapter interface first. Benchmark at least one licence-clear
  option (OpenCV YuNet detector + SFace embedding) and one InsightFace option. Choose by measured accuracy and latency on
  the separated test set, not by reputation. Record the chosen model's weight licence in this file and in
  `docs/privacy-security-and-limitations.md` (to be written).

## ADR-005: Authentication approach

- **Status:** Provisional (to be implemented in Phase 2)
- **Plan:** Passwords hashed with a maintained algorithm (Argon2id via `argon2-cffi` or bcrypt). Session tokens in
  HTTP-only cookies or bearer tokens with short expiry, signed with `SECRET_KEY`. Role checks enforced in FastAPI
  dependencies, never only in the frontend.

## ADR-006: Attendance calculation and timezone

- **Status:** Accepted (rules to be implemented in Phase 3/5)
- **Decision:** All timestamps are stored in UTC. Timetable times are local times in the configured `TIMEZONE`
  (default `Asia/Kolkata`, IANA name). Attendance percentage uses a documented denominator. The exact rules are in
  `docs/timetable-and-attendance-rules.md` (to be written in Phase 3).

## ADR-007: Local-only biometric data

- **Status:** Accepted
- **Decision:** Enrollment photos, embeddings, and exports are never committed. They live under the git-ignored `data/`
  folder or in the database, and `.gitignore` blocks common biometric file types (`*.npy`, `*.npz`, `*.pkl`, `*.onnx`).
  Retention and deletion policies are required before real enrollment (Phase 4 and later).

## ADR-008: Frontend shows unavailable pages as disabled, never as dead links

- **Status:** Accepted
- **Decision:** Navigation items for unbuilt features are rendered as disabled "Planned" labels. This keeps the planned
  information architecture visible without implying working features.

## ADR-009: Phase 4 model choice (follow-up to ADR-004)

- **Status:** Accepted for the prototype. Accuracy not yet measured.
- **Decision:** Use OpenCV YuNet (`face_detection_yunet_2023mar.onnx`) for detection and OpenCV SFace
  (`face_recognition_sface_2021dec.onnx`) for 128-dimension embeddings, behind the `FaceDetector` and `FaceEmbedder`
  protocols in `backend/app/vision/backend.py`.
- **Weight licences (read from the upstream model folders at pinned commit `47534e27…`):**
  - YuNet: MIT (`models/LICENSES/face_detection_yunet.LICENSE.txt`). Its README cites WIDER FACE for training. That
    data is distributed for research use, and its terms are not re-checked here. Institutional sign-off is needed.
  - SFace: Apache-2.0 (`models/LICENSES/face_recognition_sface.LICENSE.txt`). The README does not state the training
    data, so its data terms remain **unverified**. This must be disclosed in the thesis and checked before any use
    beyond the prototype.
- **Why not InsightFace:** ADR-004 records that the popular InsightFace pretrained packs are documented for
  non-commercial research use. They were not downloaded or benchmarked, so this project does not depend on them.
- **Not done (ADR-004 asked for it):** A measured comparison on a separated, consented test set. No accuracy,
  false-accept or false-reject figure is claimed. The SFace README reports 0.9940 accuracy on its own benchmark
  (publisher-reported, not reproduced here).
- **Threshold:** Cosine 0.363 is the default from OpenCV's demo. It must be calibrated on the institution's own test set.
