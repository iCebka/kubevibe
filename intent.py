import json
import urllib.request
import time 
import sys
import os
import subprocess
from json_to_verb import dict_to_text
from ctl import *
from log import *
import schemas2 as sch
import prompts as pts

llmUrl = "localhost:11434"

# Receives a curated intent to charge few-shot prompting through examples

def deployment_to_text(bankpath, deployment_name, pythonfile="myapp.py", containerfile="Dockerfile", yamlfile="vibe.yaml"):
    origdir = os.getcwd()
    #print(origdir)
    os.chdir(bankpath)

    shot_string = f"Deployment: {deployment_name}\n" # String to construct by iteration
    pythonfile = pythonfile
    containerfile = containerfile
    yamlfile = yamlfile

    preret1 = True
    p1 = subprocess.run(f"cat {deployment_name}/{pythonfile}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p1.returncode != 0:
        preret1 = False
    pythonfilecontent = p1.stdout.decode()

    preret2 = True
    p2 = subprocess.run(f"cat {deployment_name}/{containerfile}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p2.returncode != 0:
        preret2 = False
    containerfilecontent = p2.stdout.decode()

    preret3 = True
    p3 = subprocess.run(f"cat {deployment_name}/{yamlfile}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p3.returncode != 0:
        preret3 = False
    yamlfilecontent = p3.stdout.decode()

    if (preret1 and preret2 and preret3):        
        shot_string = shot_string + f"{pythonfile}:\n{pythonfilecontent}\n\n{containerfile}:\n{containerfilecontent}\n\n{yamlfile}:\n{yamlfilecontent}\n"
    else:
        shot_string = "" # Pending: include a proper exception validation
    
    return shot_string

def charge_few_shot(rawlogfile, intent, n=2):

    # Here we should include some logic to extract the type of service the user requests
    # to search for the best examples according to it 

    # Ideally: we should provide an AI method to determine based on the intent the type of service 
    # the user requests, and based on that we should be able to separate a set of reference deployments for it
    # currently we will just use the predefined path from the results of the previous experiment and the already known names

    origdir = os.getcwd()
    bankpath = "results/qwen3:14b"
    deployments = ["1"]
    
    log(rawlogfile, f"Few-shot charging with {deployments} from {bankpath}", "intent-extraction")

    charged_intent = f"{intent}\nHere there are some examples of correct deployment files for reference:\n"

    for deploy in deployments:
        deploystring = deployment_to_text(bankpath, deploy)
        #print(deploystring)
        charged_intent = charged_intent + deploystring
    
    os.chdir(origdir)
    log(rawlogfile, f"Few-shot charged with {deployments} from {bankpath}", "intent-extraction")

    return charged_intent, True

def curate(rawlogfile, coreintent, method, model):

    intent = coreintent["request"]
    if method in ("curated-llm-zero-shot", "curated-llm-few-shot"):
        gen_context = pts.build_generation_context(coreintent, preset="kubernetes_service_plain")
    else:
        gen_context = pts.build_generation_context(coreintent, preset="kubernetes_service_structured")

    last_try = coreintent["last-try"]
    last_iteration = last_try["iteration"]

    if last_iteration < 0:
        prefix = f"Context: {gen_context}\nTask: {intent}"
    else:
        last = coreintent["last-try"]
        last_answer_temp = last["answer"]
        last_answer = {k: v for k, v in last_answer_temp.items() if k != "improvement_plan"}
        last_grade = last["grade"]

        last_score = last_grade["score"]
        last_score_explanation = last_grade["explanation"]
        last_suggestion = last_grade["suggested_action"]
        last_rationale = ""

        if "retry" in last_rationale:
            last_rationale = last_grade["retry_rationale"]

        grade_str = f"Previous score: {last_score}\nReason: {last_score_explanation}\n"

        prefix = (
            f"Context: {gen_context}\nTask: {intent}\n"
            f"Previous answer:\n{json.dumps(last_answer, indent=2)}\n"
            f"{grade_str}\n"
        )
    txt = prefix
    data = {
        "model": model,
        "prompt": txt,
        "stream": False,
        "think": False
    }

    if method == "none":
        return intent, True
    elif method == "curated-llm-zero-shot":
        pass
    elif method == "curated-llm-few-shot":
        pass
    elif method == "only-json-as-format":
        data["format"] = "json"
    elif method == "json-with-required":
        schema = sch.service_schema()
        data["format"] = schema
        if last_iteration >= 0:
            data["format"]["properties"]["improvement_plan"] = sch.improvement_schema()
            data["format"]["required"].append("explanation")
            data["format"]["required"].append("improvement_plan")
    else:
        print("Method not recognized")
        return None, True

    dataserial = json.dumps(data)
    databinary = dataserial.encode()

    log(rawlogfile, f"Request for curating:\n{json.dumps(data, indent=4)}", "control")

    try:
        f = urllib.request.urlopen(f"http://{llmUrl}/api/generate", databinary, timeout=90)
        answerserial = f.read().decode()
    except:
        answerserial = None
    
    if not answerserial:
        return None, False
    
    outer = json.loads(answerserial)
    curatedintent = outer.get("response", "")

    return curatedintent, True

def judge(rawlogfile, coreintent, method, model, hands_free=True):
    success = True
    valid = 0
    inputdelay = 0

    if method=="none":
        grade = {
            "score": 5,
            "explanation": "not validated",
            "suggested_action": "approve"
        }
    elif method == "llm-as-a-judge":
        val_context = pts.build_validation_context(coreintent, preset="kubernetes_service_plain")
        answer = coreintent["answer"]
        txt = (
            f"Context: {val_context}\n"
            f"The assigned task was: {coreintent['request']}\n"
            f"The answer to evaluate is: "
            f"{json.dumps(answer, indent=4) if isinstance(answer, (dict, list)) else str(answer)}"
        )


        data = {
            "model": model,
            "prompt": txt,
            "stream": False,
            "think": False
        }
        
        schema = sch.validation_schema_strict()
        if not hands_free:
            schema["properties"]["suggested_action"]["enum"] = [
                "approve",
                "ask",
                "retry"
            ]
        data["format"] = schema
        dataserial = json.dumps(data)
        databinary = dataserial.encode()

        log(rawlogfile, f"Request for judge\n{json.dumps(data, indent=4)}", "control")

        try:
            f = urllib.request.urlopen(f"http://{llmUrl}/api/generate", databinary, timeout=90)
            answerserial = f.read().decode()
        except:
            answerserial = None
        
        if not answerserial:
            return None, False

        outer = json.loads(answerserial)
        grade = outer.get("response", "")

        grade = json.loads(grade)

    else:
        print("Method not recognized")
        grade = {
            "score": 5,
            "explanation": "not validated",
            "suggested_action": "approve"
        }
    
    score = grade["score"]
    action = grade["suggested_action"]

    if score == 5 and action == "approve":
        valid = 1
    elif action == "ask":
        question = grade["clarification_question"]
        print(colorise("green", f"\nClarification question: {question}"))
        t0 = time.time()
        aclaration = input(colorise("green", "> "))
        t1 = time.time()
        grade["clarification_answer"] = aclaration
        inputdelay = t1-t0

        sys.stdout.write("\033[F")
        sys.stdout.write("\033[K")
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[K")
        sys.stdout.write("\033[F")
        sys.stdout.flush()
        sys.stdout.write("\r" + colorise("yellow","(prompt)(curate)(validate)"))
    
    return grade, valid, success, inputdelay


def get_intent(prompt, model, intentmethod, outputfolder, rawlogfile):
    #outputfolder = f"intent-test/{model}/{datetime.datetime.now().strftime("%d-%m-%Y_%H_%M_%S")}_output"
    #if not os.path.isdir(outputfolder):
    #    os.makedirs(outputfolder)
    
    #rawlogfile = os.path.join(outputfolder, "kubevibe.rawlog")
    #f = open(rawlogfile, "w")
    #f.close()

    t0 = time.time()
    log(rawlogfile, f"Intent extraction using {intentmethod}", "intent-extraction")
    printcol("yellow", "(curate)", end="\n", flush=True)

    coreintent = {
        "iteration": 0,
        "request": prompt,
        "answer": -1,
        "grade": {
            "score": -1,
            "explanation": "-1"
        },
        "valid": 0,
        "last-try": {
            "iteration": -2,
            "answer": "-2",
            "grade": {
                "score": -2,
                "explanation": "-2"
            }
        }
    }

    if intentmethod != "none":
        rawintent, intent_success = curate(rawlogfile, coreintent, intentmethod, model)
    else:
        rawintent = coreintent["request"]
        curatedintent = rawintent
        intent_success = True
    
    if intentmethod == "curated-llm-zero-shot":
        curatedintent = rawintent
    elif intentmethod == "curated-llm-few-shot":
        curatedintent = charge_few_shot(rawlogfile, rawintent, n=1)
    elif intentmethod in ("only-json-as-format", "json-with-required"):
        if intentmethod == "json-with-required":
            curatedintent = pts.normalize_kubevibe_intent(json.loads(rawintent))
        curatedintent = dict_to_text(curatedintent)

    tf = time.time()
    tm = tf - t0
    return tm, curatedintent, intent_success

if __name__ == "__main__":

    model = "qwen2.5:32b"
    envmodel = os.getenv("MODEL")
    if envmodel:
        model = envmodel
    
    intentmethod = "none"
    envintentmethod = os.getenv("INTENT_METHOD")
    if envintentmethod:
        intentmethod = envintentmethod
    
    if len(sys.argv) == 1:
        print("Rapid service prototyping for Kubernetes. Prompt: ")
        prompt = input()
    else:
        prompt = " ".join(sys.argv[1:])
        print("Rapid service prototyping for Kubernetes")

    tm, curatedintent, intent_success = get_intent(prompt, model, intentmethod, "", "")
    if intent_success:
        print(f"success in {tm} secs")
        print(curatedintent)
    else:
        print(f"failed in {tm} secs")

"""
if __name__ == "__main__":
    model = "qwen2.5:32b"
    envmodel = os.getenv("MODEL")
    if envmodel:
        model = envmodel
    
    intentmethod = "none"
    envintentmethod = os.getenv("INTENT_METHOD")
    if envintentmethod:
        intentmethod = envintentmethod

    outputfolder = f"intent-test/{model}/{datetime.datetime.now().strftime("%d-%m-%Y_%H_%M_%S")}_output" # we should include the date here to make experiments easier
    if not os.path.isdir(outputfolder):
        os.makedirs(outputfolder)
    
    rawlogfile = os.path.join(outputfolder, "kubevibe.rawlog")
    f = open(rawlogfile, "w")
    f.close()
    
    printcol("yellow", "[[[Test on intents]]]")

    if len(sys.argv) == 1:
        print("Rapid service prototyping for Kubernetes. Prompt: ")
        prompt = input()
    else:
        prompt = " ".join(sys.argv[1:])
        print("Rapid service prototyping for Kubernetes. Proceding with prompt: ", colorise("violet", prompt))

    t0 = time.time()
    log(rawlogfile, f"Intent extraction using {intentmethod}", "intent-extraction")
    printcol("yellow", "(curate)", end="", flush=True)
    

    coreintent = {
        "iteration": 0,
        "request": prompt,
        "answer": -1,
        "grade": {
            "score": -1,
            "explanation": "-1"
        },
        "valid": 0,
        "last-try": {
            "iteration": -2,
            "answer": "-2",
            "grade": {
                "score": -2,
                "explanation": "-2"
            }
        }
    }

    if intentmethod != "none":
        rawintent, intent_success = curate(rawlogfile, coreintent, intentmethod, model)

    else:
        rawintent, intent_success = coreintent["request"]

    curatedintent = rawintent

    if intentmethod == "curated-llm-few-shot":
        curatedintent = charge_few_shot(rawlogfile, curatedintent, n=1)
    elif intentmethod in ("only-json-as-format", "json-with-required"):
        if intentmethod == "json-with-required":
            curatedintent = pts.normalize_kubevibe_intent(json.loads(rawintent))
        #print("aqui", type(curatedintent))
        curatedintent = dict_to_text(json.loads(curatedintent))
        #print("aqui")

    tf = time.time()

    if intent_success: 
        vibed_str = f"Intent-Extracted in {int(tf-t0)} seconds.\n{curatedintent}"
    else:
        vibed_str = f"Failed in {int(tf-t0)} seconds."
    log(rawlogfile, vibed_str, "control")
    print(vibed_str)
"""

"""
if __name__ == "__main__":

    envtimeout = os.getenv("TIMEOUT")
    envtries = os.getenv("N")

    hands_free = True
    envhandsfree = os.getenv("HANDS_FREE")
    if envhandsfree:
        hands_free = bool(int(envhandsfree))
    
    model = "qwen2.5:32b"
    envmodel = os.getenv("MODEL")
    if envmodel:
        model = envmodel
    
    intentmethod = "none"
    envintentmethod = os.getenv("INTENT_METHOD")
    if envintentmethod:
        intentmethod = envintentmethod
    
    validationmethod = "none"
    envalidationmethod = os.getenv("IVAL_METHOD")

    if envalidationmethod:
        validationmethod = envalidationmethod
    
    it = 0
    it_int = 0
    broken = False
    intent_success = False
    validation_success = False
    valid_intent = False
    end_intent = False
    kube_success = False
    delay = 0

    outputfolder = f"intent-test/{model}/{datetime.datetime.now().strftime("%d-%m-%Y_%H_%M_%S")}_output" # we should include the date here to make experiments easier
    if not os.path.isdir(outputfolder):
        os.makedirs(outputfolder)
    
    rawlogfile = os.path.join(outputfolder, "kubevibe.rawlog")
    f = open(rawlogfile, "w")
    f.close()
    
    printcol("yellow", "[[[Test on intents]]]")

    if len(sys.argv) == 1:
        print("Rapid service prototyping for Kubernetes. Prompt: ")
        prompt = input()
    else:
        prompt = " ".join(sys.argv[1:])
        print("Rapid service prototyping for Kubernetes. Proceding with prompt: ", colorise("violet", prompt))
    
    timeout_string = f"\nTimeout: {colorise("violet", envtimeout)}" if envtimeout else ""
    tries_string = f"\nAttempts: {colorise("violet", envtries)}" if envtries else ""
    summ_text = (
        "Parameters summary:"
        f"\nUsing model for artifact generation: {colorise("violet", model)}"
        f"\nIntent extraction method: {colorise("violet", intentmethod)}"
        f"\nIntent validation method: {colorise("violet", validationmethod)}"
        f"\nFree hands: {colorise("violet", str(hands_free))}"
    )

    if len(timeout_string) > 2:
        summ_text += timeout_string
    if len(tries_string) > 2:
        summ_text += tries_string

    print(summ_text)
    log(rawlogfile, f"{(
        "Parameters summary:"
        f"\nUsing model for artifact generation: {model}"
        f"]nIntent extraction method: {intentmethod}"
        f"\nIntent validation method: {validationmethod}"
        f"\nFree hands: {str(hands_free)}"
    )}", "control")
    log(rawlogfile, f"Received intent: {prompt}", "intent-extraction")

    coreintent = {}
    coreintent["iteration"] = 0
    coreintent["request"] = prompt
    coreintent["answer"] = "-1"
    coreintent["grade"] = {
        "score": -1,
        "explanation": "-1"
    }
    coreintent["valid"] = 0
    coreintent["last-try"] = {
        "iteration": -2,
        "answer": "-2",
        "grade": {
            "score": -2,
            "explanation": "-2"
        }
    }

    resultdata = {
        "endpoint": "22",
        "chart": "kamerbeek"
    }

    t0 = time.time()
    while True:
        if not end_intent:
            print(colorise("yellow", "Intent Extraction Loop"))
            while True:
                printcol("yellow", "(prompt)", end="", flush=True)
                log(rawlogfile, f"Intent extraction lap {it_int}", "intent-extraction")
                log(rawlogfile, f"Core intent status [{it_int}]:\n{json.dumps(coreintent, indent=4)}", "core-intent")
                log(rawlogfile, f"Intent extraction using {intentmethod}", "intent-extraction")
                coreintent["iteration"] = it_int

                prev_it = it_int-1
                prev_answer = coreintent["answer"]
                prev_grade = coreintent["grade"]
                prev_valid = coreintent["valid"]
                
                coreintent["last-try"]["iteration"] = prev_it
                coreintent["last-try"]["answer"] = prev_answer
                coreintent["last-try"]["grade"] = prev_grade
                coreintent["last-try"]["valid"] = prev_valid

                if intentmethod != "none":
                    printcol("yellow", "(curate)", end="", flush=True)
                    rawintent, intent_success = curate(rawlogfile, coreintent, intentmethod, model)
                else:
                    rawintent, intent_success = coreintent["request"], True
                
                if intent_success:
                    if intentmethod not in ("none", "curated-llm-zero-shot", "curated-llm-few-shot"):
                        intent = json.loads(rawintent)
                        intent = pts.normalize_kubevibe_intent(intent)
                        log(rawlogfile, f"Curated intent with success: \n{json.dumps(intent, indent=4)}", "intent-extraction")
                    else:
                        intent = rawintent
                        log(rawlogfile, f"Curated intent with success: \n{intent}", "intent-extraction")
                    coreintent["answer"] = intent
                    #print(intent)

                    log(rawlogfile, f"Beginning validation using {validationmethod}", "intent-validation")
                    printcol("yellow", "(validate)", end="", flush=True)
                    grade_intent, valid_intent, validation_success, inputdelay = judge(rawlogfile, coreintent, validationmethod, model, hands_free)
                    delay += inputdelay

                    if validation_success:
                        coreintent["grade"] = grade_intent
                        coreintent["valid"] = valid_intent
                        log(rawlogfile, f"Successfully intent validation with status {valid_intent}. \nResult:{json.dumps(grade_intent, indent=4)}", "intent-validation")
                        if validation_success:
                            coreintent["grade"] = grade_intent
                            coreintent["valid"] = valid_intent
                            log(rawlogfile, f"Successfully intent validation with status {valid_intent}. \nResult: {json.dumps(grade_intent, indent=4)}", "intent-validation")
                            if valid_intent == 1:
                                end_intent = True
                                printcol("green", "✔", end="\n", flush=True)
                                if intentmethod not in ("none", "curated-llm-zero-shot", "curated-llm-few-shot"):
                                    intent = pts.render_kubevibe_intent_to_prompt(intent) 
                                elif intentmethod == "curated-llm-few-shot":
                                    intent = charge_few_shot(rawlogfile, intent, n=2)
                                    coreintent["answer"] = intent
                                print(colorise("yellow", "Service Prototyping Loop"))
                                break
                            printcol("red", "✘", end="\n", flush=True)
                        else:
                            broken = True
                        it_int += 1
            printcol("yellow", "(generate)", end="", flush=True)
            context = ""
            print()
            it += 1
            break

            if kube_success:
                break

            if envtimeout and ((time.time() - t0) - delay) > int(envtimeout):
                broken = True
                break

            if envtries and (it > int(envtries)):
                broken = True
                break
    tf = time.time()

    log(rawlogfile, f"Core intent status:\n{json.dumps(coreintent, indent=4)}", "core-intent")
    if broken:
        broken_str = f"Timeout without success after {int(tf-t0)-delay} seconds and {it_int - 1} tries"
        print(broken_str)
        log(rawlogfile, broken_str, "control")
        exit(1)
    else:
        vibed_str = f"Intent-Extracted in {int(tf-t0)-delay} seconds."
        log(rawlogfile, vibed_str, "control")
        print(coreintent["answer"])
        print("Intent-Extracted in ", int(tf-t0), "seconds.")
        #print("Enjoy your service at", colorise("violet", resultdata["endpoint"]), "or deploy from chart", colorise("violet", resultdata["chart"]))
"""