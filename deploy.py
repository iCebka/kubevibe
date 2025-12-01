# KubeVibe 
# Stage 4 - Deploy

import subprocess
import os
from log import log

def deploy(deployfile, rawlogfile):
    ns = "vibe-test-deploy"
    ok = True

    p = subprocess.run(f"kubectl create namespace {ns}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log(rawlogfile, p.stdout.decode(), "deploy:namespace")
    if p.returncode != 0:
        ok = False
    p = subprocess.run(f"kubectl -n {ns} create -f {deployfile}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log(rawlogfile, p.stdout.decode(), "deploy:create")
    if p.returncode != 0:
        ok = False
    p = subprocess.run(f"kubectl delete namespace {ns}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log(rawlogfile, p.stdout.decode(), "deploy:delete")
    if p.returncode != 0:
        ok = False

    return ok

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
        "logfile": "kubevibe.rawlog"
    }
    
    print("deploying...")

    vfile = os.path.join(D["outputfolder"], D["node"]["manifest"]["file"])
    rawlogfile = os.path.join(D["outputfolder"], D["logfile"])

    success = deploy(vfile, rawlogfile)

    if success:
        print("success")
    else:
        print("failed")