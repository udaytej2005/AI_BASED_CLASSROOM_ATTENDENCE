#!/usr/bin/env bash
# Download and verify the two face models used by Phase 4 (YuNet detector and SFace recogniser).
#
# Provenance (checked when this script was written):
#   upstream repo : https://github.com/opencv/opencv_zoo
#   pinned commit : 47534e27c9851bb1128ccc0102f1145e27f23f98 (2026-05-28)
#   detector      : models/face_detection_yunet/face_detection_yunet_2023mar.onnx
#                   Git LFS sha256 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4, 232589 bytes
#                   licence: MIT (models/face_detection_yunet/LICENSE)
#   recogniser    : models/face_recognition_sface/face_recognition_sface_2021dec.onnx
#                   Git LFS sha256 0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79, 38696353 bytes
#                   licence: Apache-2.0 (models/face_recognition_sface/LICENSE)
#
# The SFace README does not state its training data. Read docs/face-recognition.md before any real use.
#
# Usage (from the repository root):
#   scripts/fetch_face_models.sh                 # downloads about 1.1 GB (the whole opencv_zoo archive) once
#   FACE_ZOO_TARBALL=/path/to.tar.gz scripts/fetch_face_models.sh   # use an archive you already have
set -euo pipefail

COMMIT="47534e27c9851bb1128ccc0102f1145e27f23f98"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/models"
PREFIX="opencv_zoo-main"  # top folder name inside the archive for this commit
DETECTOR="face_detection_yunet_2023mar.onnx"
DETECTOR_SHA="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
RECOGNIZER="face_recognition_sface_2021dec.onnx"
RECOGNIZER_SHA="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ARCHIVE="${FACE_ZOO_TARBALL:-}"
if [[ -z "$ARCHIVE" ]]; then
  ARCHIVE="$WORK/opencv_zoo.tar.gz"
  echo "Downloading opencv_zoo at $COMMIT (about 1.1 GB)..."
  curl -fL --retry 3 -o "$ARCHIVE" "https://codeload.github.com/opencv/opencv_zoo/tar.gz/$COMMIT"
fi

tar -xzf "$ARCHIVE" -C "$WORK" \
  "$PREFIX/models/face_detection_yunet/$DETECTOR" \
  "$PREFIX/models/face_detection_yunet/LICENSE" \
  "$PREFIX/models/face_recognition_sface/$RECOGNIZER" \
  "$PREFIX/models/face_recognition_sface/LICENSE"

verify() {
  local file="$1" expected="$2" actual
  actual="$(sha256sum "$file" | cut -d' ' -f1)"
  if [[ "$actual" != "$expected" ]]; then
    echo "SHA-256 mismatch for $(basename "$file"): expected $expected, got $actual" >&2
    exit 1
  fi
}

verify "$WORK/$PREFIX/models/face_detection_yunet/$DETECTOR" "$DETECTOR_SHA"
verify "$WORK/$PREFIX/models/face_recognition_sface/$RECOGNIZER" "$RECOGNIZER_SHA"

mkdir -p "$DEST/LICENSES"
install -m 0644 "$WORK/$PREFIX/models/face_detection_yunet/$DETECTOR" "$DEST/$DETECTOR"
install -m 0644 "$WORK/$PREFIX/models/face_recognition_sface/$RECOGNIZER" "$DEST/$RECOGNIZER"
install -m 0644 "$WORK/$PREFIX/models/face_detection_yunet/LICENSE" "$DEST/LICENSES/face_detection_yunet.LICENSE.txt"
install -m 0644 "$WORK/$PREFIX/models/face_recognition_sface/LICENSE" "$DEST/LICENSES/face_recognition_sface.LICENSE.txt"

echo "Installed and verified:"
echo "  $DEST/$DETECTOR"
echo "  $DEST/$RECOGNIZER"
echo "Licence texts are in $DEST/LICENSES/."
