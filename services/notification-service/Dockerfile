FROM python:3.12-slim
WORKDIR /app
COPY services/notification-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/notification-service/app/ ./app/
COPY services/notification-service/alembic/ ./alembic/
COPY services/notification-service/alembic.ini ./alembic.ini
COPY shared/ /shared/
EXPOSE 8007
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
