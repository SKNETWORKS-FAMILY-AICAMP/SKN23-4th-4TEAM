FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY services/fastapi_ai/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /tmp/requirements.txt

COPY services /app/services

EXPOSE 8001
CMD ["uvicorn", "services.fastapi_ai.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
