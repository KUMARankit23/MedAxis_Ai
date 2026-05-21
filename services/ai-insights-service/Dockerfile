FROM python:3.12-slim
WORKDIR /app
COPY services/ai-insights-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/ai-insights-service/app/ ./app/
COPY services/ai-insights-service/alembic/ ./alembic/
COPY services/ai-insights-service/alembic.ini ./alembic.ini
COPY shared/ /shared/
EXPOSE 8006
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
