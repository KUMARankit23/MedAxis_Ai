FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY services/notification-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/notification-service/ .
EXPOSE 8007
CMD ["python", "app.py"]
