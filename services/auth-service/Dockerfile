FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared/ ./shared/

# Copy service files
COPY services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/auth-service/ .

EXPOSE 8001
CMD ["python", "app.py"]
