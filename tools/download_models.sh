#!/bin/bash
# Downloads the vision models used by the Autopilot tab into models/.
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)/models"
mkdir -p "$DIR"
cd "$DIR"
curl -fL -O https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task
curl -fL -O https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -fL -O https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
ls -l "$DIR"
