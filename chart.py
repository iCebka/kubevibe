# KubeVibe
# Stage 6 - Chart

import os
import shutil
import subprocess
from log import log
import yaml

def smartyamldump(d):
    if type(d) == str or type(d) == dict or d is None:
        return yaml.dump(d)
    elif type(d) == list:
        return yaml.dump_all(d)
    else:
        raise Exception("YAML format unknown")
    
def postprocess(outputfolder, intent, rawlogfile):
    d = {
        "apiVersion": "v2",
        "name": "genchart",
        "description": "Generated chart for intent: " + intent,
        "type": "application",
        "version": "0.1.0",
        "appVersion": "1.16.0"
    }

    chartdir = os.path.join(outputfolder, "genchart")
    templatedir = os.path.join(chartdir, "templates")
    os.makedirs(templatedir, exist_ok = True)
    shutil.copy(os.path.join(outputfolder, "vibe.yaml"), templatedir)
    f = open(os.path.join(chartdir, "values.yaml"), "w")
    f.close()
    f = open(os.path.join(chartdir, "Chart.yaml"), "w")
    f.write(smartyamldump(d))
    f.close()

    abs_log = os.path.abspath(rawlogfile)

    origdir = os.getcwd()
    os.chdir(chartdir)

    cmds = [
        "helm lint",
        "helm package .",
        "mv genchart-0.1.0.tgz ../.."
    ]

    preret = True
    for cmd in cmds:
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log(abs_log, p.stdout.decode(), "postprocess:*")
        if p.returncode != 0:
            preret = False
            break
    
    os.chdir(origdir)
    chart = "genchart-0.1.0.tgz"
    return preret, chart

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

    outputfolder = D["outputfolder"]
    logfile = D["logfile"]
    rawlogfile = os.path.join(outputfolder, logfile)

    print("generating chart...")

    success, chart = postprocess(outputfolder, "test", rawlogfile)

    if success:
        print("success in ", chart)
    else:
        print("failed")