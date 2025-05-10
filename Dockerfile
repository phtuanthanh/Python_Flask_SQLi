FROM ubuntu:22.04

RUN apt update && apt install -y python3 python3-pip netcat-openbsd
COPY . /app

WORKDIR /app

RUN pip install -r requirements.txt

RUN chmod +x /app/index.py

EXPOSE 5000

CMD ["python3", "index.py"]
