import os
import json
import time
import urllib.request
import re
import time
from ctl import *
from log import log
import datetime
import schemas as sch

PHASE_RE = re.compile(r"^--Log:\s+(.*?)\s+--phase--\s*$")
CTX_RE = re.compile(r"^--Log:\s+(.*?)\s+--([^-]+)--\s*$")
DASH_LINE = re.compile(r"⁻-Log:")

def finderror(outputfolder, model, txt, context=None, llmUrl = "localhost:11435"):
    
    rawlogfile = os.path.join(outputfolder, "kubevibe.rawlog")

    if context:
        txt = f"Context: {context}\nTask: {txt}"
    else:
        txt = f"Task: {txt}"

    data = {
        "model": model,
        "prompt": txt,
        "stream": False,
        "think": False
    }

    data["format"] = sch.fix_schema()

    dataserial = json.dumps(data)
    databinary = dataserial.encode()
    log(rawlogfile, f"Request for generate:\n{json.dumps(data, indent=3)}", "control")

    try:
        f = urllib.request.urlopen(f"http://{llmUrl}/api/generate", databinary, timeout=300)
        answerserial = f.read().decode()
    except:
        answerserial = None
    
    f = open(os.path.join(outputfolder, "kubevibe.rawlog"), "a")
    print(f"--Log: {datetime.datetime.now()} --artifact-generation-- Raw request", file=f)
    print(txt, file=f)
    print(f"--Log: {datetime.datetime.now()} --artifact-generation-- Raw response", file=f)
    print(answerserial, file=f)
    f.close()

    return answerserial

def diff_json_strings(json1: dict, json2: dict) -> dict:
    """
    Compara dos JSONs (diccionarios) con campos tipo "string": "string"
    y devuelve un diccionario con las diferencias entre valores de claves coincidentes.

    Ejemplo:
    >>> diff_json_strings({"a": "1", "b": "2"}, {"a": "1", "b": "3"})
    {'b': {'json1': '2', 'json2': '3'}}
    """
    diffs = {}
    for key in json1:
        if key in json2 and isinstance(json1[key], str) and isinstance(json2[key], str):
            if json1[key] != json2[key]:
                diffs[key] = {"json1": json1[key], "json2": json2[key]}
    return diffs


def generateFixed(D):
    model = D["model"]
    outputfolder = D["outputfolder"]
    ok = True
    stage = D["node"]["stage"]
    print(f"Error during {stage} with")

    core = {
        "code" : D["node"]["code"]["content"],
        "container" : D["node"]["container"]["content"],
        "manifest": D["node"]["manifest"]["content"],
        "requirements": D["node"]["requirements"]["content"],
        "logs" : D["node"]["logs"]
    }

    txt = f"""You are a senior software engineer helping fix a failing deploymnent pipeline.
Work step-by-step internally, but output only valid JSON matching the given schema.

- Requested service:
{D["intent"]}

- Current pipeline stage: {stage}
- Environment is known-good; only code artifacts may be changed
- Make minimal changes that directly address the failure
- If no errors found, do not change nothing

Artifacts:
myapp.py:
{core['code']}
--
Dockerfile:
{core['container']}
--
vibe.yaml:
{core['manifest']}
--
requirements.txt:
{core['requirements']}

- Identify the single primary root cause tied to {stage}.
- Edit only artifacts with the improved solution
- If other artifact is not required to be fixed, dont write anything on their JSON slot
"""
    #print(txt)

    fixed = {
        "code": core["code"],
        "container": core["container"],
        "manifest": core["manifest"],
        "requirements": core["requirements"]
    }
    diffs = {}
        #time.sleep(1)
        #print("+")
    an = finderror(outputfolder, model, txt, None, "localhost:11434")
    
    if an:
        ans = json.loads(json.loads(an)["response"])
        newContainerfile = ans["Dockerfile"]
        newYamlfile = ans["vibe.yaml"]
        newCodefile = ans["myapp.py"]
        newRequirements = ans["requirements.txt"]
        maxNullSize = 50
        if len(newContainerfile) > maxNullSize:
            fixed["container"] = newContainerfile
        if len(newYamlfile) > maxNullSize:
            fixed["manifest"] = newYamlfile
        if len(newCodefile) > maxNullSize:
            fixed["code"] = newCodefile
        if len(newRequirements) > maxNullSize:
            fixed["requirements"] = newRequirements
    
        diffs = diff_json_strings(core, fixed)
        #print(diffs)
    else:
        ok = True #False. We let this like this to allow direct retry
    
    #if len(diffs) == 0:
    #    ok = False
    
    return diffs, ok


def fix(D, test=False):
    
    success = 0
    
    if test:
        an = {
            "response": "revision"
        }
        ans = an["response"]
        fixes = ans
        success = 1
    else:
        fixes, ok = generateFixed(D)
        if ok:
            success = 1
            for key in fixes:
                D["node"][key]["content"] = fixes[key]["json2"]
        
    D["rev"] += 1

    print(colorise("green",str(json.dumps(fixes,indent=4))))
    return fixes, success

if __name__ == "__main__":
    
    codefile = "myapp.py"
    codefilecontent = "from flask import Flask, request\n\napp = Flask(__name__)\n\n@app.route('/check_credit_card', methods=['POST'])\ndef check_credit_card():\n    card_number = request.json.get('card_number')\n    # Logic to check credit card validity would go here\n    return {'valid': True}\n\nif __name__ == '__main__':\n    app.run(host='0.0.0.0', port=5000)" 
    containerfile = "Dockerfile"
    containerfilecontent = "FROM python:3.11-slim\nCOPY myapp.py /myapp.py\nCOPY requirements.txt /requirements.txt\nRUN pip install --no-cache-dir -r /requirements.txt\nEXPSOE 5001\nCMD ['python', '/myapp.py']"
    requirements = "Flask==2.3.2"
    vibefile = "vibe.yaml"
    yamlfilecontent = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: credit-card-checker-deployment\nspec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: credit-card-checker\n  template:\n    metadata:\n      labels:\n        app: credit-card-checker\n    spec:\n      containers:\n      - name: credit-card-checker-container\n        image: satt70/myapp:latest\n        ports:\n        - containerPort: 5000\n        resources:\n          requests:\n            cpu: 100m\n            memory: 128Mi\n          limits:\n            cpu: 200m\n            memory: 256Mi\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: credit-card-checker-service\nspec:\n  type: ClusterIP\n  selector:\n    app: credit-card-checker\n  ports:\n  - protocol: TCP\n    port: 80\n    targetPort: 5000"
    #logs = "--Internal: 2025-10-24 11:27:47.427867 --connect:namespace--\nnamespace/vibe-test-service created\n--Internal: 2025-10-24 11:27:47.678758 --connect:create--\ndeployment.apps/credit-card-checker-deployment created\nservice/credit-card-checker-service created\n--Internal: 2025-10-24 11:27:47.789177 --connect:namespace--\n10.43.243.254\n--Internal: 2025-10-24 11:27:57.826814 --connect:curl--\n  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n                                 Dload  Upload   Total   Spent    Left  Speed\n100   207  100   207    0     0  38461      0 --:--:-- --:--:-- --:--:-- 41400\n<!doctype html>\n<html lang=en>\n<title>404 Not Found</title>\n<h1>Not Found</h1>\n<p>The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.</p>\n--Internal: 2025-10-24 11:28:41.888770 --connect:curl--\nnamespace 'vibe-test-service' deleted"
    logs = "--Log: 2025-10-23 17:04:36.426751 --phase--\nCONNECT\n--Log: 2025-10-23 17:04:36.605174 --connect:namespace--\nnamespace/vibe-test-service created\n\n--Log: 2025-10-23 17:04:36.872142 --connect:create--\ndeployment.apps/credit-card-checker-deployment created\nservice/credit-card-checker-service created\n\n--Log: 2025-10-23 17:04:36.996307 --connect:svc--\n10.43.35.230\n\n--Log: 2025-10-23 17:04:47.027127 --connect:curl--\n  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n                                 Dload  Upload   Total   Spent    Left  Speed\n\n  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\n  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\ncurl: (7) Failed to connect to 10.43.35.230 port 80 after 1 ms: Couldn't connect to server\n\n--Log: 2025-10-23 17:04:47.045855 --connect:curl--\n  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n                                 Dload  Upload   Total   Spent    Left  Speed\n\n  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\n  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\ncurl: (7) Failed to connect to 10.43.35.230 port 443 after 5 ms: Couldn't connect to server\n\n--Log: 2025-10-23 17:04:47.055959 --connect:curl--\n  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n                                 Dload  Upload   Total   Spent    Left  Speed\n\n  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\n  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\ncurl: (7) Failed to connect to 10.43.35.230 port 5000 after 1 ms: Couldn't connect to server\n\n--Log: 2025-10-23 17:04:58.913774 --connect:delete--\nnamespace 'vibe-test-service' deleted"

    stage = "CONNECT"
    stage_result = 0
    step = 11

    D = {
        'intent': "Develop a credit card check server",
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
            },
            "stage": stage,
            "result": stage_result,
            "step": step,
            "logs": logs
        },
        "outputfolder": "test",
        "logfile": "kubevibe.rawlog2",
        "rev": 1,
        "model": "gemma3:27b"
    }

    print("fixing...")
    
    #for i in lines:
    #    print(i)

    #print(PHASE_RE.match("--Log: 2025-10-23 16:04:16.036003 --phase--"))

    print(json.dumps(D, indent=4))

    ans, success = fix(D)
    if success == 1:
        #print(colorise("green", json.dumps(ans, indent=4)))
        print("fixed")
    else:
        print("error")

    print(json.dumps(D, indent=4))