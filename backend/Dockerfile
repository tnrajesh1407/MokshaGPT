FROM python:3.11-slim

WORKDIR /app

# Install build tools needed for vectorbt/numba/llvmlite and other compiled deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
# Force UTF-8 output so em dashes and other Unicode in logs render correctly
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
