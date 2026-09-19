FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1
ENV PORT=3000
RUN mkdir -p /app/data && chmod 777 /app/data
EXPOSE 3000

CMD ["python", "main.py"]
