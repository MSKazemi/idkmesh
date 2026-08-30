# Candidate-producer image for tools/open_model_benchmark_probe.py.
#
# The probe runs this image with `--network none`, so the pinned open-weight
# snapshot must already be inside it. Build with a context that contains the
# snapshot in ./model; tools/open_model_producer_image.sh does that for you.
#
# This image is a candidate PRODUCER only. It never receives repository
# credentials, the source checkout, or the EvaluatorPlan.
FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

ENV PIP_NO_CACHE_DIR=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false

# CPU-only wheels; the probe pins no GPU requirement and asserts no GPU access.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install --no-cache-dir transformers accelerate

COPY model /model
RUN chmod -R a+rX /model
