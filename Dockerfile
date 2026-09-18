# SWETrack API image. Serves the full API (see README.md) plus a read-only
# dashboard UI at GET /.
#
# The image installs the sentence-transformers/torch libraries (a declared
# runtime dependency for the embedding ranker) but does NOT pre-download the
# all-MiniLM-L6-v2 model weights at build time. Weights are fetched from
# Hugging Face lazily, on the first embedding request, and cached inside the
# container at /root/.cache/huggingface. That cache is lost when the
# container is removed; mount a volume to persist/reuse it across runs:
#
#   docker run --rm -p 8000:8000 \
#     -v swetrack-hf-cache:/root/.cache/huggingface \
#     swetrack:milestone-1
#
# TF-IDF requests and GET /health never trigger a download.

FROM python:3.11-slim

WORKDIR /app

# The installed package resolves data/config paths via SWETRACK_ROOT_DIR
# (see src/swetrack/infrastructure/paths.py) since a non-editable pip
# install puts it under site-packages, with no pyproject.toml above it to
# auto-detect the root from.
ENV SWETRACK_ROOT_DIR=/app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY data ./data

# Install the CPU-only torch build first: the default PyPI wheel pulls in
# the CUDA runtime (cudnn, cublas, cusolver, ...) at 500MB+ per package,
# which is both wasted (this image never has GPU access) and prone to
# timing out mid-download. The CPU wheel is a fraction of the size.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "swetrack.api:app", "--host", "0.0.0.0", "--port", "8000"]
