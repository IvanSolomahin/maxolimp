FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Add the regional trust roots without replacing Debian's public CA bundle.
COPY certs/*.crt /usr/local/share/ca-certificates/russian_trusted/
RUN update-ca-certificates

COPY task_find_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY task_find_service/app ./app
COPY task_find_service/import_etl.py ./import_etl.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
