FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY services/django_web/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /tmp/requirements.txt

COPY services /app/services
COPY data /app/data

EXPOSE 8000
CMD ["sh", "-c", "python services/django_web/manage.py migrate && python services/django_web/manage.py collectstatic --noinput && gunicorn services.django_web.config.wsgi:application --bind 0.0.0.0:8000"]
