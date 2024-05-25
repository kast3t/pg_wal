import os
import psycopg2
import requests
import time
from typing import Union
from psycopg2 import OperationalError
from psycopg2._psycopg import connection


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
