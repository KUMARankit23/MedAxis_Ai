FROM python:3.12-slim
WORKDIR /app
COPY services/reporting-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/reporting-service/app/ ./app/
COPY shared/ /shared/
EXPOSE 8005
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
