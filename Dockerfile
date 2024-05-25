FROM postgres:9.6

WORKDIR /app

COPY requirements.txt ./

RUN echo "" > /etc/apt/sources.list.d/pgdg.list
RUN echo 'deb http://archive.debian.org/debian/ stretch main contrib non-free' > /etc/apt/sources.list

RUN apt-get update
RUN apt-get install python3 -y
RUN apt-get install python3-pip -y
RUN pip3 install -r requirements.txt

RUN apt-get install iptables -y
RUN debconf-set-selections <<EOF
iptables-persistent iptables-persistent/autosave_v4 boolean true
iptables-persistent iptables-persistent/autosave_v6 boolean true
EOF
RUN apt-get install iptables-persistent -y

ENV PG_MAX_WAL_SENDERS 8
ENV PG_WAL_KEEP_SEGMENTS 8

COPY ./docker/docker-entrypoint.sh /docker-entrypoint.sh
COPY ./docker/setup-replication.sh /docker-entrypoint-initdb.d/
RUN chmod +x /docker-entrypoint.sh /docker-entrypoint-initdb.d/setup-replication.sh