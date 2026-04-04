FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY services/ai-insights-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/ai-insights-service/ .
EXPOSE 8006
CMD ["python", "app.py"]
