FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git ffmpeg curl unzip && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://deno.land/install.sh | CI=1 DENO_INSTALL=/usr/local sh && \
    deno --version

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python3", "-m", "AnnieXMedia"]
