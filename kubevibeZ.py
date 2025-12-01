import os
import sys
import time
import datetime
import urllib.request
import subprocess
import yaml
import json
import shutil
import copy
import random
import fsmStages as fsm
from log import log
from parameters import CONTEXT
from ctl import *
from generate import *
from build import *
from validate import *
from deploy import *
from connect import *
from chart import *
from fix import *
import schemas as sch
import fsmStages as stg
from intent import get_intent

llmUrl = "localhost:11434"
imageRep = "satt70"
fixfromzero = False

def handle_generate(D):
    success = 0
    intent = D["intent"]
    context = CONTEXT["generate"]
    model = D["model"]
    outputfolder = D["outputfolder"]

    t0 = time.time()

    ans = extractanswer(generate(outputfolder, model, intent, context, llmUrl))
    
    if ans:
        codefilecontent = ans["pythonfilecontent"]
        containerfilecontent = ans["containerfilecontent"]
        yamlfilecontent = ans["yamlfilecontent"]

        D["node"]["code"]["content"] = codefilecontent
        D["node"]["container"]["content"] = containerfilecontent
        D["node"]["manifest"]["content"] = yamlfilecontent

        if "requirements" in ans:
            D["node"]["requirements"]["file"] = "requirements.txt"
            D["node"]["requirements"]["content"] = ans["requirements"]

        success = 1
    else:
        D["node"]["code"]["content"] = "Error while generating"
        D["node"]["container"]["content"] = "Error while generating"
        D["node"]["manifest"]["content"] = "Error while generating"

    tf = time.time()
    tm = tf - t0

    return tm, ans, success

def handle_build(D):
    success = 1
    outputfolder = D["outputfolder"]
    logfile = D["logfile"]
    rawlogfile = os.path.join(outputfolder, logfile)

    resultdata = {}

    t0 = time.time()
    try:
        d = yaml.safe_load_all(D["node"]["manifest"]["content"])
        d = list(d)
    except:
        printcol("red", "Error", end="\n", flush=True)
        success = 0
    
    cf = None
    if "content" in D["node"]["container"]:
        cf = D["node"]["container"]["content"]
    
    pf = None
    if "content" in D["node"]["code"]:
        pf = D["node"]["code"]["content"]
    
    rqs = None
    if "content" in D["node"]["requirements"]:
        rqs = D["node"]["requirements"]["content"]

    if cf and pf:
        ret, logs = preprocess(outputfolder, cf, pf, rqs, os.path.abspath(rawlogfile))
        if ret == False:
            printcol("red", "Error", end="\n", flush=True)
            success = 0
    
    vibefile = os.path.join(outputfolder, D["node"]["manifest"]["file"])

    f = open(vibefile, "w")
    f.write(smartyamldump(d))
    f.close()

    tf = time.time()
    tm = tf - t0

    return tm, resultdata, success, logs

def handle_validate(D):
    success = 0

    t0 = time.time()
    ok = validate(D)
    tf = time.time()

    if ok:
        success = 1
    
    tm = tf-t0

    return tm, "", success

def handle_deploy(D):
    success = 0

    outputfolder = D["outputfolder"]
    logfile = D["logfile"]
    vibefile = D["node"]["manifest"]["file"]

    t0 = time.time()

    vfile = os.path.join(outputfolder, vibefile)
    rawlogfile = os.path.join(outputfolder, logfile)

    ok = deploy(vfile, rawlogfile)

    if ok:
        success = 1

    tf = time.time()

    tm = tf-t0

    return tm, "", success

def handle_connect(D):
    success = 0

    outputfolder = D["outputfolder"]
    vibefile = D["node"]["manifest"]["file"]
    logfile = D["logfile"]

    t0 = time.time()

    vfile = os.path.join(outputfolder, vibefile)
    rawlogfile = os.path.join(outputfolder, logfile)

    ok, endpoint, logs = connect(vfile, rawlogfile)

    if ok==True:
        success = 1

    tf = time.time()

    tm = tf-t0

    return tm, endpoint, success, logs

def handle_chart(D):
    success = 0

    t0 = time.time()

    intent = D["intent"]
    outputfolder = D["outputfolder"]
    logfile = D["logfile"]

    rawlogfile = os.path.join(outputfolder, logfile)
    success, chart = postprocess(outputfolder, intent, rawlogfile)

    tf = time.time()
    tm = tf-t0

    return tm, chart, success

def handle_fix(D):
    
    stage = D["node"]["stage"]

    t0 = time.time()

    #print(f"Error during {stage} with")
    ans, success = fix(D)
    #print(json.dumps(D["node"], indent=4))
    #printcol("green", "fix", end="\n", flush=True)

    tf = time.time()
    tm = tf - t0

    return tm, ans, success

HANDLERS = {
    "GENERATE": handle_generate,
    "BUILD": handle_build,
    "VALIDATE": handle_validate,
    "DEPLOY": handle_deploy,
    "CONNECT": handle_connect,
    "CHART": handle_chart,
    "FIX": handle_fix
}

def execute_stage(stage, D):

    print(colorise("green",f"{stage.lower()}"))
    rawlogfile = os.path.join(D["outputfolder"], D["logfile"])
    log(rawlogfile, stage, "phase")
    log(rawlogfile, json.dumps(D, indent=4), "D")
    #print("Current State:")
    #print(json.dumps(D, indent=4))
    #print(f"Stage to apply: {stage}")
    #print(f"y=success, n=fail, z=stop")

    opts = ["y", "n"]

    #ans = input("> ").strip().lower()
    if stage in ("BUILD", "CONNECT"):
        tm, ans, success, logs = HANDLERS.get(stage)(D)
        print(f"tm: {tm}\nans: {ans}\nsuccess: {str(success)}, ")
        D["logs"] = logs
        #print(colorise("violet", logs))
    elif stage in ("GENERATE", "VALIDATE", "DEPLOY", "CHART", "FIX"):
        tm, ans, success = HANDLERS.get(stage)(D)
        #print(f"tm: {tm}\nans: {ans}\nsuccess: {str(success)}, ")
        print(f"tm: {tm}\nsuccess: {str(success)}")
    else:
        #print(colorise("yellow", str(success)))
        ans = opts[random.randint(0,1)]
        success = 1 if ans == "y" else 0
        tm = None
    
    if ans == "z":
        state = D["node"]
        return state, 2, True
    
    D["node"]["stage"] = stage
    D["node"]["result"] = success

    state = D["node"]
    return tm, state, success

def node(codefilecontent, containerfilecontent, yamlfilecontent, stage, stage_result, step=0, requirements=None):

    node = {
        "code": {
            "file": "myapp.py",
            "content": codefilecontent
        },
        "container": {
            "file": 'Dockerfile',
            "content": containerfilecontent
        },
        "manifest": {
            "file": 'vibe.yaml',
            "content": yamlfilecontent
        },
        "requirements": {
            "file": "requirements.txt",
            "content" : ""
        },
        "stage": stage,
        "result": stage_result,
        "step": step,
        "logs": ""
    }
    
    if requirements:
        node["requirements"]["content"] = requirements
    
    return node

def tvibe(D, timeout=None, tries = None):
    intent = D["intent"]
    history = []
    trace = []
    it = 0
    fcount = 0

    t0 = time.time()

    print(f"Intent: {intent}")
    current = node("", "", "", "", 0)
    stage = "GENERATE"

    while True:
        history.append(current.copy())
        D["node"] = current.copy()

        if stage in ("SUCCESS", "FAIL"):
            print()
            break

        # Here we apply the result of the state
        tm, new_current, success = execute_stage(stage, D)
        success = bool(success)
        print(colorise("violet", f"successsssss: {success}"))

        new_current["step"] = it

        if fcount >= 10:
            print("fail loop")
            stage = "FAIL"
            break
            
        #if not exec_ok:
        #    print("stage execution failed")
        #    stage = "FAIL"
        #    break
            
        if success == 2:
            print("Manually stopped")
            break
        
        # Decide next stage
        if stage == "FIX":
            if success == 0:
                fcount += 1
                next_stage = fsm.NEXT_ON_FAIL.get("FIX", "FIX")
            else:
                fcount = 0
                if fixfromzero:
                    next_stage = "GENERATE"
                else:
                    next_stage = "BUILD"
                #i = -1
                #last = "FIX"
                #while last == "FIX" and ( i >= - len(history)):
                #    last = history[i]["stage"]
                #    i -= 1
                #next_stage = last if last not in ("", "FIX") else "GENERATE"
        else:
            if success == 1:
                fcount = 0
                next_stage = fsm.NEXT_ON_SUCCESS[stage]
            else:
                fcount += 1
                if fixfromzero:
                    next_stage = "GENERATE"
                else:
                    next_stage = fsm.NEXT_ON_FAIL[stage]

        #print(f"From {stage} ({'success' if success==1 else 'fail'}) -> {next_stage}")
        trace.append({"step": it+1, "from": stage, "result": success, "to": next_stage})

        stage = next_stage
        current = new_current
        it += 1

        if timeout and ( (time.time() - t0) > timeout ):
            success = 0
            break
        if tries and (it > tries):
            success = 0
            break
    
    tf = time.time()
    tm = tf - t0
    return tm, current, history, trace, success


def build_dot_math(stages, actions, trace, out_path="graph.dot"):
    from collections import defaultdict
    edge_steps = defaultdict(list)
    for t in trace:
        edge_steps[(t["from"], t["to"])].append(t["step"])

    def esc(s): return s.replace('"', '\\"')

    lines = []
    lines.append('digraph FSM {')
    lines.append('  rankdir=LR;')
    lines.append('  nodesep=0.6; ranksep=0.5;')
    lines.append('  node [shape=circle, fontsize=14, fontname="Times-Italic", width=0.8, height=0.8];')
    lines.append('  edge [fontname="Times-Italic", fontsize=12, arrowsize=0.8];')

    for n in stages:
        if n in ("SUCCESS", "FAIL"):
            lines.append(f'  "{esc(n)}" [peripheries=2];')  # doble círculo
        else:
            lines.append(f'  "{esc(n)}";')

    seen = set()
    for (src, res), dst in actions.items():
        key = (src, dst)
        if key in seen: 
            continue
        seen.add(key)
        if key not in edge_steps:
            lines.append(f'  "{esc(src)}" -> "{esc(dst)}" [color=gray50, label=""];')

    for (src, dst), steps in edge_steps.items():
        label = ",".join(map(str, sorted(steps)))
        lines.append(
            f'  "{esc(src)}" -> "{esc(dst)}" [penwidth=1.8, color=black, label="{esc(label)}"];'
        )

    lines.append('}')

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"DOT on {out_path}.dot")

    p = subprocess.run(f"dot -Tsvg {out_path} -o {out_path}.svg", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        print(f"Graph not generated")
    else:
        print(f"SVG graph on {out_path}")


if __name__ == "__main__":

    envfixfromzero = os.getenv("FIXFZERO")
    if envfixfromzero:
        fixfromzero = bool(int(envfixfromzero))

    # Avoid endless loop:
    envtimeout = os.getenv("TIMEOUT")
    envtries = os.getenv("N")

    do_graph = False
    envdograph = os.getenv("GRAPH")
    if envdograph:
        do_graph = bool(int(envdograph))

    # model for generation and intent curation (if selected)
    # currently we let both operations to be done by the same model
    model = "deepseek-r1:32b"
    envmodel = os.getenv("MODEL")
    if envmodel:
        model = envmodel
    
    # == Directories ==
    date_str = f"{datetime.datetime.now().strftime("%d-%m-%Y_%H_%M_%S")}"
    outputfolder = f"myto/{model}/{date_str}_output" # we should include the date here to make experiments easier
    if not os.path.isdir(outputfolder):
        os.makedirs(outputfolder)
    
    logfile = "kubevibe.rawlog"
    rawlogfile = os.path.join(outputfolder, "kubevibe.rawlog")
    f = open(rawlogfile, "w")
    f.close()

    # Intent extraction loop
    intentmethod = "none"
    envintentmethod = os.getenv("INTENT_METHOD")
    if envintentmethod:
        intentmethod = envintentmethod
    
    validationmethod = "none"
    envalidationmethod = os.getenv("IVAL_METHOD")
    if envalidationmethod:
        validationmethod = envalidationmethod
    
    if len(sys.argv) == 1:
        print("Rapid service prototyping for Kubernetes. Prompt: ")
        prompt = input()
    else:
        prompt = " ".join(sys.argv[1:])
        print("Rapid service prototyping for Kubernetes")
    
    timeout_string = f"\nTimeout: {colorise("violet", envtimeout)}" if envtimeout else ""
    tries_string = f"\nAttempts: {colorise("violet", envtries)}" if envtries else ""
    summ_text = (
        "Parameters summary:"
        f"\nUsing model for artifact generation: {colorise("violet", model)}"
        f"\nIntent extraction method: {colorise("violet", intentmethod)}"
        f"\nIntent validation method: {colorise("violet", validationmethod)}"
        f"\nFix from zero: {colorise("violet", str(fixfromzero))}"
    )

    if len(timeout_string)>2:
        summ_text += timeout_string
    if len(tries_string)>2:
        summ_text += tries_string
    
    print(summ_text)
    log(rawlogfile, f"{(
        "Parameters summary:"
        f"\nUsing model for artifact generation: {model}"
        f"\nIntent extraction method: {intentmethod}"
        f"\nIntent validation method: {validationmethod}"
        f"\nPrompt: {prompt}"
    )}", "control")
    log(rawlogfile, f"Received intent: {prompt}", "intent-extraction")

    tm, intent, intent_success = get_intent(prompt, model, intentmethod, outputfolder, rawlogfile)

    log(rawlogfile, f"Intent extraction applied with result {intent_success} in {tm} seconds", "intent-extraction")

    if not intent_success:
        print("Fail during intent handling")
        exit
    #intent = "Develop a credit card validation server"

    D = {
        "intent": intent,
        "node": node("", "", "", "", 0),
        "outputfolder": outputfolder,
        "logfile": logfile,
        "rev": 1,
        "model": model
    }

    #print(json.dumps(D))
    tt, current, history, trace, ok = tvibe(D, int(envtimeout) if envtimeout else None, int(envtries) if envtries else None)


    print(f"Process finished in {tt} seconds with result {ok}")
    log(rawlogfile, f"Process finished in {tt} seconds with result {ok}")
    #print(current)
    #print(colorise("green", json.dumps(D, indent=4)))

    #print(trace)
    #print(colorise("green", json.dumps(current, indent=4)))
    #print(json.dumps(D, indent=4))

    if do_graph:
        output_graph = f"{outputfolder}/{date_str}_dot"
        build_dot_math(fsm.stages, fsm.actions, trace, output_graph)