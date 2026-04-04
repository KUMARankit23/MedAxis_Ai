FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY services/reporting-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/reporting-service/ .
EXPOSE 8005
CMD ["python", "app.py"]
