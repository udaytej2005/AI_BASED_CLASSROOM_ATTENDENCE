# Face enrolment and recognition (Phase 4)

> **Status:** Implemented and tested with synthetic data and the real model files (smoke test only).
> **Not validated** on real students, real classroom cameras, or any measured accuracy. Read section 8 before use.

This document describes how a student is enrolled, how a live camera or a recorded video becomes attendance, what is
stored, and what must be done before the system is used with real people.

## 1. Principles

- **Consent first.** A student's face cannot be enrolled until consent has been recorded. Consent can be withdrawn,
  and withdrawal deletes all embeddings in the same transaction.
- **No images are stored.** Uploaded photos and video frames are decoded in memory, or read from a temporary file
  that is deleted when the job ends. Only embeddings (128 numbers per photo) are stored.
- **Embeddings never leave the server.** No API returns a vector, a frame, or an image. Responses contain counts,
  model names, dates and reasons.
- **Uncertain is not present.** A face is counted only when it matches one student clearly, passes the quality gates,
  and that match is confirmed over time (temporal verification).
- **Attributes stay local.** Camera addresses and stream URLs are read from the server environment and are never stored
  in the database or returned by the API.

## 2. Pipeline

```
frame -> detect faces (YuNet) -> track faces across frames (IoU tracker)
      -> quality gates (size, detector score, sharpness, brightness, tilt)
      -> embed (SFace, 128-d) -> match against enrolled students (cosine, margin)
      -> recognised_candidate | unknown | uncertain | low_quality | error
      -> temporal verification (N observations, spread over T seconds, at least G apart)
      -> attendance row: present (source camera or video, best score, observation count)
```

Module map:

| Stage | File |
|---|---|
| Model adapter (replaceable) | `backend/app/vision/backend.py` |
| Quality gates | `backend/app/vision/quality.py` |
| Matching | `backend/app/vision/matcher.py` |
| Tracking | `backend/app/vision/tracker.py` |
| Per-frame pipeline | `backend/app/vision/pipeline.py` |
| Temporal verification | `backend/app/vision/verification.py` |
| Enrolment, consent, purge | `backend/app/services/enrollment.py` |
| Recognition to attendance | `backend/app/services/recognition.py` |
| Background camera / video jobs | `backend/app/services/live_runner.py` |

## 3. Models

| Role | File | Licence (upstream folder) | Source |
|---|---|---|---|
| Detector | `models/face_detection_yunet_2023mar.onnx` | MIT | OpenCV Zoo, commit `47534e27…`, LFS sha256 `8f2383e4…` |
| Recogniser | `models/face_recognition_sface_2021dec.onnx` | Apache-2.0 | OpenCV Zoo, commit `47534e27…`, LFS sha256 `0ba9fbfa…` |

Install them with the pinned, verified download script (run from the repository root):

```bash
scripts/fetch_face_models.sh
# or, if you already have the OpenCV Zoo archive:
FACE_ZOO_TARBALL=/path/to/opencv_zoo.tar.gz scripts/fetch_face_models.sh
```

The script downloads about 1.1 GB (the whole archive for that commit), checks the SHA-256 of both weight files against
the values above, and installs them under `models/` (git-ignored). Licence texts go to `models/LICENSES/`.

Model licence and data notes are in ADR-009 (`architecture-decisions.md`). In short:

- The **weight licences** above were read from the upstream folders.
- The **YuNet** README cites the WIDER FACE dataset for training. This project does not verify that dataset's terms.
- The **SFace** README does not state its training data. Its data terms are **unverified**.
- The adapter in `vision/backend.py` keeps the model swappable. Changing the model needs new enrolments, because
  embeddings from one model cannot be compared with another. The stored `model_name` and `model_version` protect
  against mixing them: embeddings from another model are ignored until the student is re-enrolled.

Without the model files the API returns HTTP 503 for enrolment and recognition, and the status message names the missing
file only (no server paths).

## 4. Enrolment

1. An administrator records consent: `POST /api/v1/students/{id}/consent` with `{"confirmed": true, "reference": "FORM-12"}`.
   The reference is a short code for the paper or digital form that the institution keeps. The form itself is not stored.
2. The administrator uploads 5 to 20 photos: `POST /api/v1/students/{id}/enrollment` (multipart field `images`).
   - JPEG or PNG only, at most 3 MB and 4000 px per side each.
   - Each photo must contain **exactly one** face that passes every gate:
     - face at least **80 px** (the shorter side of the box),
     - detector confidence at least **0.85**,
     - sharpness (Laplacian variance) at least **60**,
     - mean brightness between **50 and 215**,
     - head roll no more than **0.35** (eye-height difference over eye distance).
   - At least **5** photos must pass. Otherwise **nothing is stored** and the response lists the reasons per photo.
   - Re-enrolment replaces the previous embeddings in one transaction.
3. `GET /api/v1/students/{id}/enrollment` shows consent state, the number of stored embeddings, the model, and dates.
   Administrators, principals and faculty can read it.

Every gate threshold is a setting (`QUALITY_*`, `ENROLLMENT_*`). They are conservative starting values chosen for this
prototype, not validated values.

## 5. Live recognition and video

- **Camera:** `POST /api/v1/sessions/{id}/recognition/camera` starts a background run on the camera assigned to the
  session. The camera's `stream_reference` must be a device index (for example `0`) or the name of a server
  environment variable whose value is the stream address (for example `CAM_R101_URL`). Stream addresses with
  credentials belong in the environment, never in the database.
- **Video file:** `POST /api/v1/sessions/{id}/recognition/video` (multipart field `video`) accepts an MP4, MOV, AVI or
  MKV file up to 100 MB. The file type is checked from its first bytes. The file is written to the system temporary
  directory with owner-only permissions, processed, and deleted when the job ends.
- **Jobs:** `GET .../recognition/jobs/{job_id}` reports state (`running`, `completed`, `stopped`, `failed`), frame and
  recognition counts, and the student ids newly marked present. `POST .../jobs/{job_id}/stop` asks a run to stop.
- **Results:** `GET /api/v1/sessions/{id}/recognized` lists students marked present, with source, best score, and
  observation count.
- Only one active run per session is allowed. Only the assigned faculty member or an administrator can start, upload
  to, or stop a run. Runs are refused for sessions that are not open.

Runs are background threads inside the API process. **Run the server as a single process** (the default). Job state is
in memory and is lost on restart. Multi-worker deployment needs a job queue; that is out of scope.

### Attendance rules used by recognition

- Only students on the **session's class roster** can be marked present. A match to anyone else is discarded.
- A student is marked present after **5 accepted observations**, spread over **at least 2.0 seconds**, with each
  observation **at least 0.4 seconds** after the previous one (defaults; all configurable). Several tracks of one
  person at one moment count once.
- Each student gets **at most one** present row per session, enforced by a unique database constraint.
- Recognition runs on every 3rd frame and re-checks a tracked face every 10 processed frames (defaults).
- These are **configurable prototype rules**. They are not college regulations. The institution must confirm them.

## 6. Consent withdrawal, deletion and retention

| Action | Who | Effect |
|---|---|---|
| `DELETE /students/{id}/consent` | Administrator | Marks consent withdrawn and deletes all embeddings. The consent row is kept for the audit trail. |
| `DELETE /students/{id}/enrollment` | Administrator | Deletes embeddings but keeps consent (for example, before a fresh enrolment). |
| `python -m app.cli purge-biometrics [--retention-days N]` | Operator with server access | Deletes embeddings older than the retention period (default **365 days**, setting `BIOMETRIC_RETENTION_DAYS`). Writes a count-only audit record. |

Run `purge-biometrics` on a schedule (for example, a daily cron job) in any deployment. Nothing runs it automatically yet.

Audit records hold counts and identifiers only. The audit writer refuses any detail key that contains `embedding`,
`image`, `password`, `token` or `secret`.

## 7. Command reference

```bash
cd backend && . .venv/bin/activate
python -m app.cli purge-biometrics
pytest tests/test_vision.py tests/test_enrollment.py tests/test_recognition.py   # synthetic, deterministic
pytest tests/test_real_models.py                                                 # needs models/ (skips otherwise)
FACE_SAMPLE_IMAGE=/path/to/local/photo.jpg pytest tests/test_real_models.py     # optional local detection check
```

## 8. Limits and what has NOT been done

- **No measured accuracy.** No false-accept rate, false-reject rate, or speed figure has been measured on this project's
  data. The system must not be described as accurate until a separate, consented test set has been used. The
  enrolment and test sets must be separate.
- **Tests use synthetic faces.** The unit and API tests use generated images with markers (`backend/tests/fakes.py`). They
  test the logic (gates, matching, tracking, verification, permissions, deletion) and not face recognition itself.
- **Real-model check is a smoke test.** `test_real_models.py` loads the real models, detects faces in the upstream sample
  photos, and checks that a 128-dimension embedding is returned. That is all it claims.
- **No webcam was tested.** The development sandbox has no camera. The camera path has not been run on a real device.
  The video-file path uses the same pipeline.
- **No liveness detection.** A printed photo or a screen can be presented to the camera. Faculty review remains the
  safeguard (see `known-limitations.md`).
- **Bias and performance differences are unknown.** They must be measured on a consented, representative set before any
  claim is made.
- **Look-alike and twin students** can produce `uncertain` results. This is intended. An uncertain face is never counted
  as present.
- **Model-licence review is partial.** See section 3 and ADR-009.

## 9. Local setup checklist (before real data)

1. Obtain written consent from each student, and store the form outside this repository.
2. Run `scripts/fetch_face_models.sh` on the faculty computer, not in the repository.
3. Set `APP_ENV=production`, a real `SECRET_KEY`, and a real database password (see `installation-and-troubleshooting.md`).
4. Measure accuracy on a separate, consented set (not the enrolment photos). Record the results in
   `implementation-status.md` only as measured values, with the sample sizes and conditions.
5. Schedule `purge-biometrics`. Set `BIOMETRIC_RETENTION_DAYS` to the period the institution approves.
