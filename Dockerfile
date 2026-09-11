FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    FRANKENFLY_DATA_DIR=/data FRANKENFLY_STATE_DIR=/state
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 frankenfly \
    && useradd --uid 10001 --gid frankenfly --no-create-home frankenfly \
    && mkdir /data /state \
    && chown frankenfly:frankenfly /data /state
COPY frankenfly ./frankenfly
COPY dist ./dist
COPY LICENSE NOTICE ./
USER frankenfly
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "frankenfly.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
