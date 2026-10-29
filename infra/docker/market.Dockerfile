FROM python:3.12-slim
WORKDIR /app
COPY services/market-worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/market-worker/main.py ./main.py
CMD ["python","main.py"]
