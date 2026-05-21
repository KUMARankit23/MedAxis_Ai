FROM python:3.12-slim
WORKDIR /app
COPY services/billing-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/billing-service/app/ ./app/
COPY services/billing-service/alembic/ ./alembic/
COPY services/billing-service/alembic.ini ./alembic.ini
COPY shared/ /shared/
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
