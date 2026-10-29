FROM python:3.12-slim
WORKDIR /app
COPY services/trading-worker/main.py ./main.py
CMD ["python","main.py"]
