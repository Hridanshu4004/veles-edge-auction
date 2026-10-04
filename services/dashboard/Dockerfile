FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx
COPY services/dashboard/main.py /app/main.py
COPY services/dashboard/static /app/static
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
