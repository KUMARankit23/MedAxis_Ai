FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY services/inventory-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/inventory-service/ .
EXPOSE 8002
CMD ["python", "app.py"]
