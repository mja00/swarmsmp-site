# pull official base image
FROM python:3.10.3-slim-buster

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install system dependencies
RUN apt-get update && apt-get install -y netcat dos2unix

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

# copy project
COPY . /usr/src/app/

# chmod +x the entrypoint and dos2unix it
RUN chmod +x /usr/src/app/entrypoint.sh && dos2unix /usr/src/app/entrypoint.sh

# Do some omega jank due to quarry weirdness
RUN cp /usr/local/lib/python3.10/site-packages/quarry/data/packets/0757_1.18.csv /usr/local/lib/python3.10/site-packages/quarry/data/packets/0758_1.18.2.csv
RUN cp /usr/local/lib/python3.10/site-packages/quarry/data/data_packs/0757_1.18.nbt /usr/local/lib/python3.10/site-packages/quarry/data/data_packs/0758_1.18.2.nbt

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]