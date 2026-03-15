FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

WORKDIR $APP_HOME

# Install system deps (sqlite3 for DB inspection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Default: run the interactive chat agent
CMD ["python", "chat.py"]
