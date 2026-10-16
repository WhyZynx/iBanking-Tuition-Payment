FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/tuition_service/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend

EXPOSE 8002

CMD ["uvicorn", "backend.tuition_service.main:app", "--host", "0.0.0.0", "--port", "8002"]