import subprocess
import time
from agent import Agent
from flask import Flask, jsonify

# ООП сделало больно и покинуло чат, чат, чат, чат...

app = Flask(__name__)


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
            time.sleep(1)
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
