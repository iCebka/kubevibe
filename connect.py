# KubeVibe 
# Stage 5 - Connect

import subprocess
import os
import time
import datetime
from log import log, inlog

def connect(deployfile, rawlogfile):
    ns = "vibe-test-service"
    ok = True
    endpoint = None
    summ = ""
    datet = datetime.datetime.now()

    p = subprocess.run(f"kubectl create namespace {ns}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #log(rawlogfile, p.stdout.decode(), "connect:namespace")
    summ += inlog(p.stdout.decode(),"connect:namespace")
    if p.returncode != 0:
        ok = False
    p = subprocess.run(f"kubectl -n {ns} create -f {deployfile}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #log(rawlogfile, p.stdout.decode(), "connect:create")
    #summ += f"--Internal-Log: {datetime.datetime.now()} --connect:create--\n"
    #summ += p.stdout.decode()
    summ += inlog(p.stdout.decode(), "connect:create")
    if p.returncode != 0:
        ok = False

    p = subprocess.run(f"kubectl -n {ns} get svc -o json | jq -r '.items[].spec.clusterIP'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #log(rawlogfile, p.stdout.decode(), "connect:svc")
    #summ += f"--Internal-Log: {datetime.datetime.now()} --connect:namespace--\n"
    #summ += p.stdout.decode()
    summ += inlog(p.stdout.decode(), "connect:namespace")
    if p.returncode != 0:
        ok = False
    output = p.stdout.decode()
    if not output:
        ok = False
    else:
        ipaddress = output.strip()
        # FIXME Kubernetes service exposure needs around ~1-2 seconds to wait for pod readiness, fails hard before
        time.sleep(10)
        p = subprocess.run(f"curl --connect-timeout 1 http://{ipaddress}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #log(rawlogfile, p.stdout.decode(), "connect:curl")
        #summ += f"--Internal-Log: {datetime.datetime.now()} --connect:curl--\n"
        #summ += p.stdout.decode()
        summ += inlog(p.stdout.decode(), "connect:curl")
        port = None
        if p.returncode != 0:
            #time.sleep(2)
            p = subprocess.run(f"curl --connect-timeout 1 http://{ipaddress}:443", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            #log(rawlogfile, p.stdout.decode(), "connect:curl")
            #summ += f"--Internal-Log: {datetime.datetime.now()} --connect:curl--\n"
            #summ += p.stdout.decode()
            summ += inlog(p.stdout.decode(), "connect:curl")
            if p.returncode != 0:
                #time.sleep(2)
                p = subprocess.run(f"curl --connect-timeout 1 http://{ipaddress}:5000", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                #log(rawlogfile, p.stdout.decode(), "connect:curl")  
                #summ += f"--Internal-Log: {datetime.datetime.now()} --connect:curl--\n"
                #summ += p.stdout.decode()
                summ += inlog(p.stdout.decode(), "connect:curl")
                if p.returncode != 0:
                    ok = False
                else:
                    endpoint = f"http://{ipaddress}"
                    port = 5000
            else:
                endpoint = f"http://{ipaddress}" #This wont be the real endpoint after all
                port = 443
        else:
            endpoint = f"http://{ipaddress}"
            port = 80

        #if port:
        #    f = open("ports.csv", "a")
        #    print(port, file=f)
        #    f.close()

    p = subprocess.run(f"kubectl delete namespace {ns}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #log(rawlogfile, p.stdout.decode(), "connect:delete")
    #summ += f"--Internal-Log: {datetime.datetime.now()} --connect:delete--\n"
    #summ += p.stdout.decode()
    summ += inlog(p.stdout.decode(), "connect:curl")
    if p.returncode != 0:
        ok = False

    #print(summ)
    log(rawlogfile, summ, "phase", datet)
    return ok, endpoint, summ

if __name__ == "__main__":

    codefile = "myapp.py"
    codefilecontent = "from flask import Flask, request\n\napp = Flask(__name__)\n\n@app.route('/check_credit_card', methods=['POST'])\ndef check_credit_card():\n    card_number = request.json.get('card_number')\n    # Logic to check credit card validity would go here\n    return {'valid': True}\n\nif __name__ == '__main__':\n    app.run(host='0.0.0.0', port=5000)" 
    containerfile = "Dockerfile"
    containerfilecontent = "FROM python:3.11-slim\nCOPY myapp.py /myapp.py\nCOPY requirements.txt /requirements.txt\nRUN pip install --no-cache-dir -r /requirements.txt\nEXPOSE 5000\nCMD ['python', '/myapp.py']"
    requirements = "Flask==2.3.2"
    vibefile = "vibe.yaml"
    yamlfilecontent = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: credit-card-checker-deployment\nspec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: credit-card-checker\n  template:\n    metadata:\n      labels:\n        app: credit-card-checker\n    spec:\n      containers:\n      - name: credit-card-checker-container\n        image: satt70/myapp:latest\n        ports:\n        - containerPort: 5000\n        resources:\n          requests:\n            cpu: 100m\n            memory: 128Mi\n          limits:\n            cpu: 200m\n            memory: 256Mi\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: credit-card-checker-service\nspec:\n  type: ClusterIP\n  selector:\n    app: credit-card-checker\n  ports:\n  - protocol: TCP\n    port: 80\n    targetPort: 5000"

    D = {
        "node": {
            "code": {
                "file": codefile,
                "content": codefilecontent
            },
            "container": {
                "file": containerfile,
                "content": containerfilecontent
            },
            "manifest": {
                "file": vibefile,
                "content": yamlfilecontent
            },
            "requirements":{
                "file": "requirements.txt",
                "content": requirements
            }
        },
        "outputfolder": "test",
        "logfile": "test.txt"
    }

    vfile = os.path.join(D["outputfolder"], D["node"]["manifest"]["file"])
    rawlogfile = os.path.join(D["outputfolder"], D["logfile"])

    print("connecting...")

    success, endpoint, logs = connect(vfile, rawlogfile)

    if success:
        print("success in ", endpoint)
    else:
        print("failed")