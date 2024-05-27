FROM python:slim

WORKDIR /client

COPY requirements.txt .

RUN pip3 install -r requirements.txt

EXPOSE 5000

COPY . .

CMD [ "python3" , "main.py"]

