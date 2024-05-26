import random
import subprocess
import time
from agent import Agent
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2._psycopg import connection


load_dotenv("docker/writer.env")

good = 0
bad = 0


def create_table(tableName: str) -> None:
    c = agent.conn2master.cursor()
    c.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(tableName)))
    c.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {}(id integer PRIMARY KEY)").format(sql.Identifier(tableName)))

    agent.conn2master.commit()
    c.close()


def writeNumber(conn: connection, number: int, tableName: str) -> bool:
    global good, bad
    try:
        c = conn.cursor()
        c.execute(sql.SQL("INSERT INTO {} (id) VALUES (%s)").format(sql.Identifier(tableName)), (number, ))
        conn.commit()
        c.close()
        good += 1
        return True
    except Exception as err:
        print("Error while inserting number {}: {}".format(number, err))
        conn.rollback()
        bad += 1
        return False


def testSlaveDown() -> None:
    print("Run test, where Slave dies (осуждаю!)...")

    # Создаём таблицу, если её не существует
    create_table("test_slave_down")

    for i in range(10000):
        if i == 5000:
            if subprocess.run(["docker", "compose", "stop", "pg-slave"]).returncode == 0:
                print("Slave was successfully killed")

        if writeNumber(agent.conn2master, i, "test_slave_down"):
            print("Successfully wrote number {} in database!".format(i))
        time.sleep(random.choice([0.1, 0.2, 0.3, 0.4, 0.5]))

    print("Test, where Slave dies, is done. Good: {}. Bad: {}".format(good, bad))
    if subprocess.run(["docker", "compose", "start", "pg-slave"]).returncode == 0:
        print("Slave was successfully resurrected")


def testMasterDown() -> None:
    print("Run test, where Master dies...")
    conn = agent.conn2master

    # Создаём таблицу, если её не существует
    create_table("test_master_down")

    for i in range(1000000):
        if i == 500000:
            if subprocess.run(["docker", "compose", "stop", "pg-master"]).returncode == 0:
                print("Master was successfully killed")
            conn = agent.conn2slave

        if writeNumber(conn, i, "test_master_down"):
            print("Successfully wrote number {} in database!".format(i))
        time.sleep(random.choice([0.1, 0.2, 0.3, 0.4, 0.5]))

    print("Test, where Master dies, is done. Good: {}. Bad: {}".format(good, bad))
    if subprocess.run(["docker", "compose", "start", "pg-master"]).returncode == 0:
        print("Master was successfully resurrected")


if __name__ == '__main__':
    agent = Agent()

    testSlaveDown()

    good = 0
    bad = 0

    time.sleep(5)  # Ждём, пока БД Slave окончательно поднимется
    agent.initConnections()
    testMasterDown()
