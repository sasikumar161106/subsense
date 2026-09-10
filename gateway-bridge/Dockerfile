FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV INGEST_URL=http://ai-ml:8000/api/v1/ingest/telemetry
ENV SER_PORT=/dev/ttyUSB0
ENV SER_BAUD=115200

CMD ["python", "bridge.py", "--mock"]
