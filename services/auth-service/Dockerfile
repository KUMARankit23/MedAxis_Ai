FROM python:3.12-slim
WORKDIR /app
COPY services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/auth-service/app/ ./app/
COPY services/auth-service/alembic/ ./alembic/
COPY services/auth-service/alembic.ini ./alembic.ini
COPY shared/ /shared/
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
