"""Mechanics check for the real OpenCV models. Skipped unless the model files are installed (see scripts/).

It checks that the adapter loads the models, returns a 128-dimension embedding, and that an image is
consistent with
itself. It does NOT measure recognition accuracy. Set FACE_SAMPLE_IMAGE to a local photo to test detection on
it.
The photo is never committed to Git.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from app.vision.backend import backend_status, load_opencv_backend

pytestmark = pytest.mark.skipif(
    backend_status()["status"] != "ready",
    reason="face models not installed; run scripts/fetch_face_models.sh",
)


def test_real_backend_loads_and_reports_model_identity():
    backend = load_opencv_backend()
    assert backend.model_name
    assert backend.model_version


def test_blank_image_has_no_faces():
    import numpy as np

    backend = load_opencv_backend()
    assert backend.detector.detect(np.zeros((240, 320, 3), dtype=np.uint8)) == []


@pytest.mark.skipif(not os.environ.get("FACE_SAMPLE_IMAGE"), reason="set FACE_SAMPLE_IMAGE to a local photo")
def test_sample_photo_gives_128_dimension_embedding_consistent_with_itself():
    import cv2

    image = cv2.imread(os.environ["FACE_SAMPLE_IMAGE"])
    assert image is not None
    backend = load_opencv_backend()
    faces = backend.detector.detect(image)
    assert faces, "no face detected in the sample photo"
    first = backend.embedder.embed(image, faces[0])
    second = backend.embedder.embed(image, faces[0])
    assert first.shape == (128,)
    cosine = float(first @ second / (np.linalg.norm(first) * np.linalg.norm(second)))
    assert cosine > 0.99
