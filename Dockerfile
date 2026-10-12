FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y libcurl4-openssl-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

ENV PROXY_USER=u1ebdced056e605cf-zone-custom-region-co
ENV PROXY_PASS=u1ebdced056e605cf
ENV PROXY_DNS=na.proxy.2captcha.com:2334

CMD ["uvicorn", "betplay_password_api:app", "--host", "0.0.0.0", "--port", "8001"]
