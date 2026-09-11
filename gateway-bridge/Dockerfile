FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV INGEST_URL=http://bff-gateway:3001/api/v1/telemetry/broadcast
ENV SER_PORT=/dev/ttyUSB0
ENV SER_BAUD=115200

CMD ["python", "bridge.py", "--mock"]
