"""Computer-vision pipeline: detection, quality gates, embedding, matching, tracking and temporal
verification.

Each stage is small and testable on its own. Face models are reached only through the adapters in
``backend.py``,
so the detector or recogniser can be replaced without changing the attendance logic.
"""
