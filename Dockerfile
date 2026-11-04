ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data

ARG REQUIREMENTS_FILE=requirements.txt
COPY ${REQUIREMENTS_FILE} /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY telegram_rss_bot.py /app/telegram_rss_bot.py
RUN mkdir -p /app/data

CMD ["python", "/app/telegram_rss_bot.py"]
