FROM ubuntu:latest
FROM python:3.7
MAINTAINER "kate_sarlamanova@hotmail.com"
RUN apt-get update -y

RUN pip install --upgrade pip

RUN mkdir /app
ADD . /app
WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt
RUN rm requirements.txt

EXPOSE 5000

CMD ["python","app.py"]
