FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -e ".[dev]"

# demo-mode store (writable data dir for the approval console)
RUN mkdir -p /data/cah && chmod 777 /data/cah

ENV HARNESS_DEMO=1
ENV CAH_STORE_DIR=/data/cah
ENV PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["uvicorn", "cah.web.app:app", "--host", "0.0.0.0", "--port", "7860"]
