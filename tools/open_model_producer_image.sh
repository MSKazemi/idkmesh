#!/usr/bin/env bash
# Build the candidate-producer image used by tools/open_model_benchmark_probe.py.
#
# Network is used HERE, on the host, to fetch the pinned open-weight snapshot
# and the base image. The probe itself then runs the image with `--network
# none`, so the snapshot has to be baked in first.
#
#   ./tools/open_model_producer_image.sh [image-tag]
#
# Weights: Qwen/Qwen2.5-Coder-0.5B-Instruct at the revision pinned in
# tools/open_model_benchmark_probe.py. Open weights, zero paid API spend.
set -euo pipefail

IMAGE="${1:-idkmesh-open-model-producer:task001}"
MODEL_REPO="Qwen/Qwen2.5-Coder-0.5B-Instruct"
MODEL_REVISION="bbf27711794f58ebd1796058f4280b53c32e19fc"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="$(mktemp -d)"
trap 'rm -rf "$CONTEXT"' EXIT

python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='${MODEL_REPO}',
    revision='${MODEL_REVISION}',
    local_dir='${CONTEXT}/model',
)
"
rm -rf "${CONTEXT}/model/.cache"
cp "${ROOT}/tools/open_model_producer.Dockerfile" "${CONTEXT}/Dockerfile"
docker build -t "${IMAGE}" "${CONTEXT}"

echo "built ${IMAGE}"
docker image inspect --format='image id: {{.Id}}' "${IMAGE}"
