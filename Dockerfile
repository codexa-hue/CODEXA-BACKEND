# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Build frontend (VITE_API_URL is empty so it defaults to relative path /api/v1)
RUN npm run build

# Stage 2: Backend & Runner
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY backend/ .

# Copy built frontend static files from Stage 1 to the correct path relative to backend
COPY --from=frontend-builder /frontend/dist /frontend/dist

# Expose port and run
ENV PORT=8000
EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT

