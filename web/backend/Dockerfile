FROM python:3.11-slim
WORKDIR /app
COPY web/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY web/backend /app/web/backend
# Mount mechanisms to be importable
COPY mechanisms /app/mechanisms
COPY common /app/common
ENV PYTHONPATH=/app
CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
