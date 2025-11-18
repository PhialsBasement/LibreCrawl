FROM python:3.12

COPY . .

RUN pip install -r requirements.txt

RUN playwright install chromium

ENV LIBRE_CRAWL_DATA_PATH=/data

VOLUME [ "/data" ]

CMD ["python", "main.py", "-l"]
