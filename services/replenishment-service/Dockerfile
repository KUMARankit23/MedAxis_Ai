FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY services/replenishment-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/replenishment-service/ .
EXPOSE 8004
CMD ["python", "app.py"]
