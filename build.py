# KubeVibe
# Stage 2 - Build
import os
import subprocess
import yaml
import datetime
from log import log, inlog

def smartyamldump(d):
    if type(d) == str or type(d) == dict or d is None:
        return yaml.dump(d)
    elif type(d) == list:
        return yaml.dump_all(d)
    else:
        raise Exception("YAML format unknown")

def preprocess(outputfolder, cf, pf, rqs, rawlogfile, imageRep = "satt70"):
    pycode = os.path.join(outputfolder, "myapp.py")
    containerfile = os.path.join(outputfolder, "Dockerfile")
    requirements = os.path.join(outputfolder, "requirements.txt")

    summ = ""
    datet = datetime.datetime.now()

    f = open(pycode, "w")
    f.write(pf)
    f.close()

    f = open(containerfile, "w")
    f.write(cf)
    f.close()

    f = open(requirements, "w")
    f.write(rqs)
    f.close()

    # Fixup: increase chances by adding empty requirements
    # Update: it still seems to be required to mention it on the prompt 
    #f = open(os.path.join(outputfolder, "requirements.txt"), "w")
    #f.close()

    cmds = ["docker build -t myapp .",
            f"docker tag myapp:latest {imageRep}/myapp:latest",
            f"docker push {imageRep}/myapp:latest"]

    origdir = os.getcwd()
    os.chdir(outputfolder)

    preret = True
    for cmd in cmds:
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #log(rawlogfile, p.stdout.decode(), "build:*")
        summ += inlog(p.stdout.decode(), "connect:curl")
        if p.returncode != 0:
            preret = False
            break
    
    os.chdir(origdir)

    log(rawlogfile, summ, "phase", datet)

    return preret, summ

if __name__ == "__main__":

    codefile = "from flask import Flask, request\n\napp = Flask(__name__)\n\n@app.route('/check_credit_card', methods=['POST'])\ndef check_credit_card():\n    card_number = request.json.get('card_number')\n    # Logic to check credit card validity would go here\n    return {'valid': True}\n\nif __name__ == '__main__':\n    app.run(host='0.0.0.0', port=5000)" 
    containerfile = "FROM python:3.11-slim\nCOPY myapp.py /myapp.py\nCOPY requirements.txt /requirements.txt\nRUN pip install --no-cache-dir -r /requirements.txt\nEXPOSE 5000\nCMD [\"python\", \"/myapp.py\"]"
    requirements = "Flask==2.3.2"
    manifest = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: credit-card-checker-deployment\nspec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: credit-card-checker\n  template:\n    metadata:\n      labels:\n        app: credit-card-checker\n    spec:\n      containers:\n      - name: credit-card-checker-container\n        image: satt70/myapp:latest\n        ports:\n        - containerPort: 5000\n        resources:\n          requests:\n            cpu: 100m\n            memory: 128Mi\n          limits:\n            cpu: 200m\n            memory: 256Mi\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: credit-card-checker-service\nspec:\n  type: ClusterIP\n  selector:\n    app: credit-card-checker\n  ports:\n  - protocol: TCP\n    port: 80\n    targetPort: 5000"

    """
    print(containerfile)
    print()
    print(codefile)
    print()
    print(requirements)
    print()
    print(manifest)
    """

    success = True
    example = {
        "codefile": codefile,
        "containerfile": containerfile,
        "manifest": manifest,
        "requirements": requirements
    }

    print("building...")
    try:
        d = yaml.safe_load_all(example["manifest"])
        d = list(d)
    except:
        print("error")
        success = False
    
    cf = None
    if "containerfile" in example:
        cf = example["containerfile"]
    
    pf = None
    if "codefile" in example:
        pf = example["codefile"]
    
    rqs = None
    if "requirements" in example:
        rqs = example["requirements"]
    
    outputfolder = "test"
    rawlogfile = os.path.join(outputfolder, "kubevibe.rawlog")

    if cf and pf:
        ret, logs = preprocess(outputfolder, cf, pf, rqs, os.path.abspath(rawlogfile))
        print(logs)
        if not ret:
            print("build failed")
            success = False
    
    vibefile = os.path.join(outputfolder, "vibe.yaml")

    f = open(vibefile, "w")
    f.write(smartyamldump(d))
    f.close()

    if success:
        print("completed")
    else:
        print("failed")