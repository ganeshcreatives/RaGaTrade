FROM python:3.12-slim
WORKDIR /app
COPY services/ml-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/ml-service/ ./
ENV MODEL_DIR=/models
EXPOSE 8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
