FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY services/billing-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/billing-service/ .
EXPOSE 8003
CMD ["python", "app.py"]
