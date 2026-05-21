FROM python:3.12-slim
WORKDIR /app
COPY services/replenishment-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/replenishment-service/app/ ./app/
COPY services/replenishment-service/alembic/ ./alembic/
COPY services/replenishment-service/alembic.ini ./alembic.ini
COPY shared/ /shared/
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
