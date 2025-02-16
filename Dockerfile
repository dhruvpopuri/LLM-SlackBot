FROM --platform=linux/x86_64 python:3.8.10

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/home/app/web

RUN useradd --user-group --create-home --no-log-init --shell /bin/bash app

ENV HOMEDIR=/home/app/web

WORKDIR $HOMEDIR

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --default-timeout=500 -r requirements.txt
RUN apt-get update && apt-get install -y netcat

COPY . .

RUN chown -R app:app $HOMEDIR
RUN chmod +x /home/app/web/entrypoint.sh

USER app:app

EXPOSE 8000

ENTRYPOINT ["/home/app/web/entrypoint.sh"]
