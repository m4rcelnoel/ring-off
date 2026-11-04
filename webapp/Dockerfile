# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# Hand the same version to the backend stage, so both report one number.
RUN node -p "require('./package.json').version" > /version.txt

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
COPY --from=frontend /version.txt ./version.txt
COPY --from=frontend /frontend/dist ./static
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
