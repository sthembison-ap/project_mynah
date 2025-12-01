# Simple CPU image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Node.js, core build tools, git, and crucially, PostgreSQL development libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Dependencies for NodeSource
        curl gnupg \
        # Dependencies for Python packages and pgvector
        build-essential git \
        # Crucial for pgvector to find the necessary headers:
        postgresql-client libpq-dev && \
    \
    # 1. Download and de-armor the Nodesource GPG key
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    \
    # 2. Add the Node.js 20 LTS repository
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    \
    # 3. Update apt and install nodejs (which includes npm)
    apt-get update && \
    apt-get install -y nodejs && \
    \
    # 4. Clean up to minimize image size
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]