FROM ubuntu:22.04

USER root

RUN apt-get update && \
    apt-get install -y apt-utils && \
    env DEBIAN_FRONTEND="noninteractive" apt-get -y install tzdata && \
    ln -fs /usr/share/zoneinfo/Europe/Brussels /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    rm -rf /var/cache/apt && \
    apt-get clean

RUN apt-get update && \
    apt-get install -y python3-pip python3-dev pypy3 pypy3-dev sagemath && \
    rm -rf /var/cache/apt && \
    apt-get clean

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/cache/apt && \
    apt-get clean

# RUN apt install -y netcat net-tools

RUN useradd -ms /bin/bash user
USER user
WORKDIR /home/user/

ENV PATH="${PATH}:/home/user/.local/bin"

# jupyter lab will be install in main python
# other interpreters only need to install ipykernel
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -U pycryptodome binteger jupyterlab ipykernel

RUN pypy3 -m pip install --no-cache-dir -U pip
RUN pypy3 -m pip install --no-cache-dir -U pycryptodome binteger ipykernel jupyter_client
RUN pypy3 -m ipykernel install --prefix=/home/user/.local/ --name 'pypy3'

RUN sage -pip install --no-cache-dir -U pip
RUN sage -pip install --no-cache-dir -U pycryptodome binteger ipykernel

ENV PYTHONPATH="${PYTHONPATH}:/home/user/ches2022wbc/"

CMD jupyter lab --no-browser --port=9999 --ip=127.0.0.1