# KubeVibe
# Stage 1 - GENERATE

import json
import os
import datetime
import urllib.request
import schemas as sch
from log import log

def generate(outputfolder, model, txt, context=None, llmUrl = "localhost:11435"):
    
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

    data["format"] = sch.artifacts_schema()

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

def extractanswer(answerserial):
    if answerserial:
        answer = json.loads(answerserial)
        responseserial = answer["response"]
        try:
            response = json.loads(responseserial)
        except:
            response = None
    else:
        response = None
    
    return response

if __name__ == "__main__":
    txt = "develop a credit card checker service"
    context = """You are an AI system that generates deployable Kubernetes service artifacts.

Your objective:
Deploy a working service inside an existing Kubernetes cluster, exposing port 80 through a Kubernetes Service.

You must return a JSON object with the following keys:
- yamlfilecontent (required): Kubernetes manifest(s) including one Deployment and one Service for Kubernetes Client Version v1.30.5
- containerfilecontent (optional): Dockerfile text in docker version 28.1.1
- pythonfilecontent (optional): Python Flask service code.
- requirementscontent (optional): the content of requirements.txt if the service needs dependencies.

Rules:
- Follow the Task specification exactly. Do not invent endpoints, variables, or artifacts that are not defined there.
- Be deterministic: no explanations, no markdown, no comments, no placeholder text.
- If the Python app requires dependencies (e.g., Flask, requests, etc.), also produce a 'requirementscontent' field containing the full text of a requirements.txt file.
- If any field from the Task is missing, apply safe defaults.

Safe defaults:
- Image: satt70/myapp:latest
- App file: myapp.py
- Language: Python 3.11
- Docker base image: python:3.11-slim
- Dockerfile name: Dockerfile
- Service type: ClusterIP
- Service port: 80, 443, or 5000
- Target port: 80, 443 or 5000
- Resources: requests cpu=100m/memory=128Mi; limits cpu=200m/memory=256Mi
"""
    context2 = """You are an AI system that generates deployable Kubernetes service artifacts.

Your objective:
Deploy a working service inside an existing Kubernetes cluster, exposing port 80 through a Kubernetes Service.

You must return a JSON object with the following keys:
- yamlfilecontent (required): Kubernetes manifest(s) including one Deployment and one Service for Kubernetes Client Version v1.30.5
- containerfilecontent (optional): Dockerfile text in docker version 28.1.1
- pythonfilecontent (optional): Python Flask service code.
- requirementscontent (optional): the content of requirements.txt if the service needs dependencies.

Rules:
- Follow the Task specification exactly. Do not invent endpoints, variables, or artifacts that are not defined there.
- Be deterministic: no explanations, no markdown, no comments, no placeholder text.
- If the Python app requires dependencies (e.g., Flask, requests, etc.), also produce a 'requirementscontent' field containing the full text of a requirements.txt file.
- If any field from the Task is missing, apply safe defaults.

Safe defaults:
- Image: satt70/myapp:latest
- App file: myapp.py
- Language: Python 3.11
- Docker base image: python:3.11-slim
- Dockerfile name: Dockerfile
- Service type: ClusterIP
- Service port: 80, 443, or 5000
- Target port: 80, 443 or 5000
- Resources: requests cpu=100m/memory=128Mi; limits cpu=200m/memory=256Mi

Consistency requirements:
- Deployment container image == containerfile image_name (if provided)
- Container EXPOSE/served port == Service targetPort
- Environment variables from the Task appear both in the Python app and in the Deployment
- All HTTP endpoints listed in the Task exist in the Flask app

Artifact requirements:
- pythonfilecontent: minimal app implementing the listed endpoints
- containerfilecontent: Dockerfile copying the app and requirements.txt, installing dependencies, exposing port, and running the app
- requirementscontent: text listing all Python dependencies needed by the app
- yamlfilecontent: Deployment + Service consistent with image, ports, and resources

Output format:
Return exactly one JSON object with the keys above.
No extra text, comments, or markdown."""
    model = "deepseek-r1:1.5b"
    outputfolder = "test"

    if not os.path.isdir(outputfolder):
        os.makedirs(outputfolder)

    print("generating...")

    ans = extractanswer(generate(outputfolder,model,txt,context))
    if ans:
        print("succesfully generated")
        for key in ans:
            print(key)
            print(ans[key])
    else:
        print("error ")