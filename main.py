import os
import psycopg2
import requests
import subprocess
import time
from flask import Flask, jsonify
from typing import Union
from psycopg2 import OperationalError
from psycopg2._psycopg import connection

# ООП сделало больно и покинуло чат, чат, чат, чат...

app = Flask(__name__)


def connectToDb(dbname: str, user: str, password: str, host: str) -> Union[connection, None]:
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=5432)
        print("Successfully connected to {}".format(host))
        return conn
    except OperationalError as err:
        print("Error while creating connection to {}: {}".format(host, err))
        return None


class Agent:
    def __init__(self):
        self.role = os.environ.get('ROLE')
        self.user = os.environ.get('POSTGRES_USER')
        self.password = os.environ.get('POSTGRES_PASSWORD')
        self.dbname = os.environ.get('POSTGRES_DB')
        self.master = os.environ.get('MASTER_HOST')
        self.slave = os.environ.get('SLAVE_HOST')
        self.arbiter = os.environ.get('ARBITER_HOST')

        self.conn2master = None
        self.conn2slave = None

        print("Run as {}".format(self.role))

        if self.role != "Arbiter":
            self.initConnections()

    def initConnections(self) -> None:
        """
        Master подключается к БД Slave, Slave к БД Master, а Arbiter к БД Master и БД Slave

        Если при инициализации агента не удаётся подключиться к какой-либо БД
        в течение 20 секунд, попытки подключения прекращаются, но затем
        продолжатся в runMaster, runSlave и runArbiter
        :return: None
        """
        print("Trying to init connections...")

        for s in range(4):
            if self.master and self.conn2master is None:
                self.conn2master = connectToDb(self.dbname, self.user, self.password, self.master)
            if self.slave and self.conn2slave is None:
                self.conn2slave = connectToDb(self.dbname, self.user, self.password, self.slave)

            if (self.master and not self.conn2master) or (self.slave and not self.conn2slave):
                time.sleep(5)
            else:
                break

    def checkConn2Master(self) -> bool:
        try:
            if self.conn2master is None:
                self.conn2master = connectToDb(self.dbname, self.user, self.password, self.master)
            c = self.conn2master.cursor()
            c.execute("SELECT 1")
            c.close()
            return True
        except Exception as err:
            print("Error while checking connection to Master, seems like it's dead: {}".format(err))
            self.conn2master = None
            return False

    def checkConn2Slave(self) -> bool:
        try:
            if self.conn2slave is None:
                self.conn2slave = connectToDb(self.dbname, self.user, self.password, self.slave)
            c = self.conn2slave.cursor()
            c.execute("SELECT 1")
            c.close()
            return True
        except Exception as err:
            print("Error while checking connection to Slave, seems like it's dead: {}".format(err))
            self.conn2slave = None
            return False

    def checkConnA2M(self) -> Union[bool, None]:
        """
        :return: True - связь АМ есть; False - связи АМ нет; None - связи с А нет
        """
        try:
            r = requests.get('http://{}:5000/check/master'.format(self.arbiter))
            status = r.json().get('Master alive')
            print("Successfully got response from Arbiter. Master alive: {}".format(status))
            return status
        except Exception as err:
            print("Error while GET-request to Arbiter, seems like it's dead: {}".format(err))
            return None

    def checkConn2Arbiter(self) -> bool:
        try:
            r = requests.get('http://{}:5000/check/arbiter'.format(self.arbiter))
            status = r.json().get('Arbiter alive')
            print("Successfully got response from Arbiter. Arbiter alive: {}".format(status))
            return status
        except Exception as err:
            print("Error while GET-request to Arbiter, seems like it's dead: {}".format(err))
            return False


def runMaster():
    while True:
        print("Check if connection to Arbiter is alive...")
        statusA = agent.checkConn2Arbiter()
        statusS = agent.checkConn2Slave()
        if not statusA and not statusS:
            print("Connections to Arbiter and Slave are dead. Blocking input connections...")
            checkSuccessInsert = subprocess.run(["iptables", "-P", "INPUT", "DROP"])
            checkSuccessSave = subprocess.run(["iptables-save", ">", "/etc/iptables/rules.v4"])
            if checkSuccessInsert.returncode == 0:
                print('Seccessfully blocked input connections')
                break
            else:
                print('Error while inserting rule')
        time.sleep(5)


def runSlave():
    while True:
        print("Check if connection between Arbiter and Master alive...")
        statusAM = agent.checkConnA2M()

        if statusAM or statusAM is None:
            time.sleep(5)
        else:
            statusM = agent.checkConn2Master()
            print("Check if Master alive: {}".format(statusM))
            if not statusM:
                print('Promoting me to Master...')
                checkSuccess = subprocess.run(["touch", "/tmp/promote_me"])
                if checkSuccess.returncode == 0:
                    print('Seccessfully promoted to Master')
                    break
                else:
                    print('Error while creating trigger file')


def runArbiter():
    @app.route('/check/master', methods=['GET'])
    def checkMaster():
        if agent.checkConn2Master():
            return jsonify({"Master alive": True})
        else:
            return jsonify({"Master alive": False})

    @app.route('/check/arbiter', methods=['GET'])
    def checkArbiter():
        return jsonify({"Arbiter alive": True})

    # Сначала нужно запустить веб-сервер, чтобы в случае, когда A пытается подключиться к M и S,
    # Arbiter сразу мог отвечать на запросы о себе и М
    app.run(debug=False, host='0.0.0.0')
    agent.initConnections()


if __name__ == '__main__':
    agent = Agent()

    if agent.role == "Master":
        runMaster()
    elif agent.role == "Slave":
        runSlave()
    else:
        runArbiter()
