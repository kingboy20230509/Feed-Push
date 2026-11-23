FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN mkdir /data && chown 10001:10001 /data
COPY stock.py service.py ./
USER 10001:10001
EXPOSE 8787
ENTRYPOINT ["python", "service.py"]
