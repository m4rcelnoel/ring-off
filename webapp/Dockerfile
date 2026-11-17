# ── Stage 1: Build React frontend ────────────────────────────────────────────
# The output (dist/, version.txt) is plain static files, identical for every
# architecture, so this stage runs once on the build machine's own platform.
# Emulating it for arm64 under QEMU was slow and could crash npm ci with
# "qemu: uncaught target signal 4 (Illegal instruction)", hanging the CI build.
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# Hand the same version to the backend stage, so both report one number.
RUN node -p "require('./package.json').version" > /version.txt

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.11-slim
# Unbuffered, so print() diagnostics reach `docker compose logs` as they happen
# instead of sitting in a buffer until it fills or the process exits.
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
COPY --from=frontend /version.txt ./version.txt
COPY --from=frontend /frontend/dist ./static
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
