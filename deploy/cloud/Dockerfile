FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (gcc for some wheels), tzdata for correct timestamps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install -U pip && pip install -r requirements.txt

# Copy project
COPY . .

EXPOSE 8000

# Default to binding on all interfaces (overridable by env)
ENV HOST=0.0.0.0 \
    PORT=8000

CMD ["python","server.py"]

