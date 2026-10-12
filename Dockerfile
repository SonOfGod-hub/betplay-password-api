FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y libcurl4-openssl-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "betplay_password_api:app", "--host", "0.0.0.0", "--port", "8001"]
