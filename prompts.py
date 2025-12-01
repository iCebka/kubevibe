import json
import schemas as sch
import urllib.request
import sys

DEFAULT_ACTIONS = ["approve", "ask", "retry"]

PRESETS = {
    "generic": {
        "domain": "general task solving",
        "deliverable": "a structured answer that strictly follows the provided JSON schema",
        "constraints": [
            "No meta-commentary or apologies",
            "Be deterministic: avoid randomness and vague language",
            "Do not invent external data; if required, propose placeholders"
        ],
        "acceptance": [
            "Valid: the output matches the schema exactly.",
            "Aligned: it answers the user's request directly.",
            "Complete: no key steps or fields are missing.",
            "Accurate: no contradictions or invented facts relevant to the task."
        ]
    },
    "kubernetes_service_structured": {
        "domain": "cloud-native service intent specification for Kubernetes artifact generation",
        "deliverable": "a structured object that matches the provided service_schema exactly",
        "constraints": [
            "Prefer safe defaults where explicitly allowed; otherwise leave fields empty ('', null, []) rather than guessing.",
            "Do not add endpoints, env vars, or components that are not in the user's request.",
            "Keep values internally consistent (image name, ports, filenames).",
        ],
        "acceptance": [
            "Valid: the output matches service_schema exactly (types, enums, required keys).",
            "Aligned: the service intent reflects the user's request without scope creep.",
            "Complete: all required fields are provided (defaults acceptable where policy allows).",
            "Consistent: image/ports/files agree across sections (artifacts/deployment/service)."
        ],
        # Policy for when to ask vs. proceed for this preset
        "ask_when_missing": [
            "name, description, or functionality are entirely absent and cannot be reasonably inferred.",
            "artifacts.layout.codefile is required by policy but HTTP interface is empty (no routes).",
            "The user mentions a specific language/runtime/image that conflicts with the schema enum or safe defaults.",
            "Ports are contradictory (e.g., service.port != 80 if schema expects 80) or invalid given enums."
        ],
        "safe_defaults": [
            "codefile.language=python; codefile.version=3.11; codefile.file=myapp.py",
            "containerfile.runtime=docker; containerfile.base_image=python:3.11-slim; containerfile.image_name=localhost:32000/myapp:latest; containerfile.file=Dockerfile",
            "yamlfile.file=vibe.yaml; yamlfile.include=[deployment, service]; yamlfile.image=localhost:32000/myapp:latest",
            "deployment.replicas=1; service.type=ClusterIP; service.port=80; service.target_port=5000",
            "resources.requests: cpu=100m, memory=128Mi; resources.limits: cpu=200m, memory=256Mi"
        ]
    },
    "kubernetes_service_plain": {
      "domain": "intent extraction for the rapid prototyping of cloud-native applications",
      "deliverable": "ONLY a textual/structured specification of what must be implemented (components, languages, versions, filenames, images, ports, resources). DO NOT generate any code, YAML, shell commands, or fenced code blocks.",
      "constraints": [
         "You do not implement any code or yaml, just the description.",
         "Output MUST NOT include fenced code blocks (```), snippets, manifests, apiVersion/kind sections, or shell commands.",
         "Restrict language to Python only (no Go/Node/Java/etc.).",
         "Restrict runtime to Docker only (no Podman/Buildpacks/OCI variants).",
         "Prefer safe defaults where explicitly allowed; otherwise leave fields empty (\"\"), null, or [] rather than guessing.",
         "Do not add endpoints, environment variables, volumes, or components that are not in the user's request.",
         "Keep values internally consistent (image name, ports, filenames).",
         "If the user explicitly asks for a non-Python language or non-Docker runtime, treat it as a conflict and use ask_when_missing to request clarification instead of changing the stack.",
         "Mention default Kubernetes artifacts (deployment, service) only as items in the specification; DO NOT emit their YAML."
      ],
      "acceptance": [
         "Valid: the output specifies completely the requirements for generating a cloud-native service for the given intent, without any implementation artifacts.",
         "Aligned: the service intent reflects the user's request without scope creep and without adding endpoints or env vars not requested.",
         "Complete: all required information are provided or safely defaulted; unknowns are left as \"\", null, or [].",
         "Consistent: image/ports/files agree across sections (artifacts/deployment/service) and match safe defaults.",
         "No code or YAML present anywhere in the output."
      ],
      "ask_when_missing": [
         "Service name, high-level description, or core functionality are absent and cannot be reasonably inferred.",
         "HTTP interface is required by the caller's schema (e.g., an artifacts.layout.codefile is expected) but no routes/HTTP behavior were provided.",
         "The user requests a specific language/runtime/image that conflicts with the policy (allowed: Python 3.11 + Docker).",
         "Provided ports are contradictory or invalid given the safe defaults (e.g., service.port not 80, target_port not 5000) and no justification was given.",
         "Image repository or naming convention must be customized (e.g., non-local registry) and the user has not supplied one."
      ],
      "safe_defaults": [
         "Language: python; Version=3.11; File: myapp.py",
         "Runtime: Docker; Base image: python:3.11-slim; Image name: localhost:32000/myapp:latest; File: Dockerfile",
         "Yamlfile: vibe.yaml; Include in yamlfile: deployment, service; Yamlfile image: localhost:32000/myapp:latest (reference only; do not emit YAML)",
         "deployment.replicas=1; service.type=ClusterIP; service.port=80; service.target_port=5000",
         "resources.requests: cpu=100m, memory=128Mi; resources.limits: cpu=200m, memory=256Mi"
      ]
}

}

def colorise(col, s):
    color = {}
    color["red"] = "\033[0;31m"
    color["green"] = "\033[0;32m"
    color["yellow"] = "\033[1;33m"
    color["blue"] = "\033[0;34m"
    color["violet"] = "\033[0;35m"
    reset = "\033[0m"
    return color[col] + s + reset

def generate(coreintent, model, method, context=""):
    intent = coreintent["request"]
    gen_context = build_generation_context(coreintent, preset="generic")
    last_iteration = coreintent["last-try"]["iteration"]
    
    #print(colorise("yellow", f"te dispararo {gen_context}"))

    if last_iteration < 0:
        prefix = f"Context: {gen_context}\nTask: {intent}"
    else:
        last = coreintent["last-try"]
        last_answer_temp = last["answer"]
        last_answer = {k: v for k, v in last_answer_temp.items() if k != "improvement_plan"}
        last_grade = last["grade"]
        not_include_in_grade = ["ask_clarification", "clarification_question", "clarification_answer"]
        #print(f"answer: {json.dumps(last_answer, indent=4)}")

        last_score = last_grade["score"]
        last_score_explanation = last_grade["explanation"]
        last_suggestion = last_grade["suggested_action"]
        last_rationale = "" 

        if "regenerate" in last_rationale:
            last_rationale = last_grade["regenerate_rationale"]

        grade_str = f"Previous score: {last_score}\nReason: {last_score_explanation}\n"

        prefix = (
            f"Context: {gen_context}\nTask: {intent}\n"
            f"Previous answer:\n{json.dumps(last_answer, indent=2)}\n"
            f"{grade_str}\n"
        )    
    txt = prefix
    print(colorise("yellow", txt))

    print("Using model: ", colorise("violet", model))
    print("Using method for intent curation:", colorise("violet", method))

    data = {
        "model": model,
        "prompt": txt,
        "stream": False,
        "think": False,
    }

    if method == "plain":
        i = 0
    elif method == "only-json-as-format":
        data["format"] = "json"
    elif method == "json-with-required":
        schema = sch.recipe_schema()
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

    try:
        f = urllib.request.urlopen("http://localhost:11435/api/generate", databinary, timeout=90)
        answerserial = f.read().decode()
    except:
        answerserial = None
    
    if not answerserial:
        return None, False

    outer = json.loads(answerserial)
    curatedintent = outer.get("response", "")
    return curatedintent, True


def judge(coreintent, method, model, hands_free=True):
    print("Using method for validation: ", colorise("violet", method))
    success = True
    valid = 0
    not_first = coreintent["last-try"]["iteration"] >= 0
    
    if method == "none":
        print("Proceeding without validation")
        grade = {
            "score": 5,
            "explanation": "ehhh",
            "suggested_action": "approve"
        }
    elif method == "llm-as-a-judge":

        val_context = build_validation_context(coreintent, preset="generic")
        answer = coreintent["answer"]
        txt = (
            f"Context: {val_context}\n"
            f"The assigned task was: {coreintent['request']}\n"
            f"The answer to evaluate is: {json.dumps(answer, indent=3)}"
        )
        print(colorise("green", txt))
    
        data = {
            "model": model,
            "prompt": txt,
            "stream": False,
            "think": False
        }

        schema = sch.validation_schema_strict()
        if not hands_free:
            schema["properties"]["suggested_action"]["enum"] = {
                "approve",
                "ask",
                "no_ask"
            }

        data["format"] = schema
        dataserial = json.dumps(data)
        databinary = dataserial.encode()

        try:
            f = urllib.request.urlopen("http://localhost:11435/api/generate", databinary, timeout=90)
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
            "explanation": "ehhh"
        }
    
    score = grade["score"]
    action = grade["suggested_action"]
    
    if score == 5 and action == "approve":
        valid = 1
    """
    elif action == "ask":
        question = grade["clarification_question"]
        print(colorise("green", f"Clarification question: {question}"))
        aclaration = input(colorise("green", "> "))
        grade["clarification_answer"] = aclaration
    """
        
    return grade, valid, success

def join_bullets(title, items):
    if not items: return ""
    return title + "\n- " + "\n- ".join(items)

def _clarification_policy_text(preset_cfg):
    ask_when = preset_cfg.get("ask_when_missing", [])
    safe_def = preset_cfg.get("safe_defaults", [])
    lines = []
    if ask_when:
        lines.append(join_bullets("Ask for clarification if ANY of the following hold:", ask_when))
    if safe_def:
        lines.append(join_bullets("Otherwise, apply these safe defaults if a required field is unspecified:", safe_def))
    return "\n".join(lines)

def build_generation_context(coreintent, preset="generic", extra_constraints=None, extra_acceptance=None, require_improvement_plan=True):
    p = PRESETS[preset]
    domain = p["domain"]
    deliverable = p["deliverable"]
    constraints = (p["constraints"] + (extra_constraints or []))
    acceptance = (p["acceptance"] + (extra_acceptance or []))

    last_try = coreintent["last-try"]
    last_iteration = last_try["iteration"]
    clarification = ""
    first_iter = last_iteration < 0

    if last_iteration >= 0:
        last_grade = last_try["grade"]
        last_suggested = last_grade["suggested_action"]
        if last_suggested == "ask":
            question = last_grade["clarification_question"]
            answer = last_grade["clarification_answer"]
            #print(colorise("violet", json.dumps(last_suggested, indent=5)))
            #print(colorise("violet", f"{question}:{answer}"))
            clarification += f"""
Clarifications from the user after last attempt to be considered:
Question: {question}
Answer: {answer}
"""


    base = f"""You are a senior specialist in {domain}.
Your job is to produce {deliverable}.


Rules for generation:
- Do NOT ask questions or request confirmation.
- Be specific and operational; avoid vague phrases.
- If something is unknown and cannot be inferred, use explicit placeholders ("", null, []) or the safe defaults below.

{join_bullets("Constraints:", constraints)}
{join_bullets("Acceptance criteria you must satisfy:", acceptance)}
{clarification if (len(clarification)>2) else ""}
"""

    if first_iter or not require_improvement_plan:
        tail = """Output: a single answer conforming exactly to the request provided by the caller."""
    else:
        tail = """Because there is a previous attempt and a grade, you MUST:
1) Produce 'improvement_plan': an array of objects [{"issue", "fix", "evidence_from_previous"}], grounded in the prior answer and its grade.
2) Produce the revised deliverable under the schema (same keys the caller expects).
Return both in a format that mathches the caller's format.
"""

    return base + tail

def build_validation_context(coreintent, preset="generic", allowed_actions=None):
    
    last_try = coreintent["last-try"]
    last_iteration = last_try["iteration"]
    clarification = ""
    if last_iteration >= 0:
        last_grade = last_try["grade"]
        last_suggested = last_grade["suggested_action"]
        if last_suggested == "ask":
            question = last_grade["clarification_question"]
            answer = last_grade["clarification_answer"]
            #print(colorise("red", json.dumps(last_suggested, indent=5)))
            #print(colorise("red", f"{question}:{answer}"))
            clarification += f"""
Clarifications from the user to be considered:
Question: {question}
Answer: {answer}         
"""

    actions = allowed_actions or DEFAULT_ACTIONS
    p = PRESETS[preset]

    policy_lines = [
        "1) \"approve\" — Output fully meets the request and acceptance criteria. Nothing essential is missing. (score = 5)",
        "2) \"retry\" — On-topic but fixable issues exist that do not require user input (missing fields, unclear steps, inconsistencies). Provide a concise \"retry_rationale\". (typical score 3–4)",
        "3) \"ask\" — Missing/unknown/ambiguous information that cannot be safely defaulted. Provide ONE concrete \"clarification_question\". (typical score ≤ 3)"
    ]
    hard_rules = [
        "Do NOT choose \"approve\" unless score is exactly 5 and all acceptance criteria are met.",
        "If a critical field is absent and not covered by safe defaults, choose \"ask\" and write ONE specific question.",
        "Include a clarification question ONLY if action is \"ask\".",
        "Include a retry rationale ONLY if action is \"retry\".",
        "If both \"ask\" and \"retry\" seem plausible, choose \"ask\"."
    ]
    policy = "\n".join(policy_lines)
    hard_rules = "\n".join(hard_rules)

    return f"""You are an impartial expert reviewed for {p['domain']}.
Evaluate the candidate strictly against the acceptance criteria below.
Score on a 1-5 scale where 5 means fully acceptable.

Acceptance criteria:
{''.join([f'\n- {c}' for c in p['acceptance'][1:]])}
{"- "+p['acceptance'][0] if p['acceptance'] else ""}

Decision policy (choose exactly one action from {actions}):
{policy}

Hard rules:
{hard_rules}

Precedence:
- If both \"ask\" and \"retry\" seem plausible, choose \"ask\".
- If it already meets the bar, choose \"approve\" even if minor stylistic tweaks are possible.
{ clarification if (len(clarification)>2) else "" } 
Return JSON that matches the validator schema from the caller (includes: explanation, score, suggested_action, and conditional fields). Keep explanation concise and actionable.
"""

def normalize_kubevibe_intent(spec: dict) -> dict:
    s = json.loads(json.dumps(spec))  # deep copy

    # === rename yamlfile -> manifest (si aparece)
    arts = s.setdefault("artifacts", {})
    layout = arts.setdefault("layout", {})
    if "yamlfile" in layout and "manifest" not in layout:
        layout["manifest"] = layout.pop("yamlfile")

    # === ensure artifacts.generate coherente
    gen = set(arts.get("generate", []))
    if "codefile" in layout: gen.add("codefile")
    if "containerfile" in layout: gen.add("containerfile")
    if "manifest" in layout: gen.add("manifest")
    # el generador siempre requiere manifest
    gen.add("manifest")
    arts["generate"] = list(gen)

    # === defaults seguros
    code = layout.setdefault("codefile", {})
    code.setdefault("language", "python")
    code.setdefault("version", "3.11")
    code.setdefault("file", "myapp.py")
    code.setdefault("dependencies", [])
    code.setdefault("env", [])

    cont = layout.setdefault("containerfile", {})
    cont.setdefault("runtime", "docker")
    cont.setdefault("base_image", "python:3.11-slim")
    cont.setdefault("image_name", "localhost:32000/myapp:latest")
    cont.setdefault("file", "Dockerfile")

    mani = layout.setdefault("manifest", {})
    inc = mani.get("include", ["deployment","service"])
    # de-dup + orden estable: deployment, service
    order = ["deployment", "service"]
    inc = [x for x in order if x in set(inc)]
    if not inc: inc = ["deployment","service"]
    mani["include"] = inc
    mani.setdefault("file", "vibe.yaml")
    mani.setdefault("image", cont.get("image_name", "localhost:32000/myapp:latest"))

    # === deployment/service: tipos y defaults
    dep = s.setdefault("deployment", {})
    dep.setdefault("replicas", 1)
    res = dep.setdefault("resources", {})
    req = res.setdefault("requests", {})
    lim = res.setdefault("limits", {})
    req.setdefault("cpu", "100m"); req.setdefault("memory", "128Mi")
    lim.setdefault("cpu", "200m"); lim.setdefault("memory", "256Mi")

    svc = dep.setdefault("service", {})
    svc.setdefault("type", "ClusterIP")
    # coerce to int
    def _to_int(x, default):
        try: return int(x)
        except: return default
    svc["port"] = _to_int(svc.get("port", 80), 80)
    svc["target_port"] = _to_int(svc.get("target_port", 5000), 5000)

    # === interface/tests placeholders
    iface = s.setdefault("interface", {})
    iface.setdefault("http", [])
    tests = s.setdefault("tests", {})
    tests.setdefault("cases", [])

    # === mínimos de metadata
    s.setdefault("version", "1.0")
    s.setdefault("name", "myapp")
    s.setdefault("description", "")
    s.setdefault("functionality", "")

    return s

def render_kubevibe_intent_to_prompt(spec: dict) -> str:
    name = spec.get("name","myapp").strip()
    desc = spec.get("description","").strip()
    func = spec.get("functionality","").strip()

    arts = spec["artifacts"]; layout = arts["layout"]
    gen_list = arts.get("generate", ["manifest"])

    code = layout.get("codefile", {})
    cont = layout.get("containerfile", {})
    mani = layout.get("manifest", {})

    dep = spec["deployment"]; svc = dep["service"]
    iface = spec.get("interface", {}); http_eps = iface.get("http", [])
    tests = spec.get("tests", {}); cases = tests.get("cases", [])

    lines = []
    lines.append(f"Service name: {name}")
    if desc: lines.append(f"Description: {desc}")
    if func: lines.append(f"Functionality: {func}")
    lines.append("")
    lines.append("Artifacts to generate: " + ", ".join(gen_list))

    if "codefile" in gen_list:
        lines.append("Codefile:")
        lines.append(f"  language: {code.get('language')}")
        lines.append(f"  version: {code.get('version')}")
        lines.append(f"  file: {code.get('file')}")
        deps = code.get("dependencies", [])
        if deps: lines.append("  dependencies: " + ", ".join(deps))
        envs = code.get("env", [])
        if envs:
            lines.append("  env:")
            for e in envs:
                lines.append(f"    - {e.get('name')}={e.get('value')}")

    if "containerfile" in gen_list:
        lines.append("Containerfile:")
        lines.append(f"  runtime: {cont.get('runtime')}")
        lines.append(f"  base_image: {cont.get('base_image')}")
        lines.append(f"  image_name: {cont.get('image_name')}")
        lines.append(f"  file: {cont.get('file')}")

    # Manifest siempre requerido por el pipeline actual
    lines.append("Manifest:")
    lines.append(f"  include: {', '.join(mani.get('include', []))}")
    lines.append(f"  file: {mani.get('file')}")
    lines.append(f"  image: {mani.get('image')}")

    lines.append("Deployment:")
    lines.append(f"  replicas: {dep.get('replicas')}")
    req = dep["resources"]["requests"]; lim = dep["resources"]["limits"]
    lines.append(f"  resources.requests: cpu={req['cpu']}, memory={req['memory']}")
    lines.append(f"  resources.limits: cpu={lim['cpu']}, memory={lim['memory']}")
    lines.append("Service:")
    lines.append(f"  type: {svc['type']}")
    lines.append(f"  port: {svc['port']}")
    lines.append(f"  target_port: {svc['target_port']}")

    if http_eps:
        lines.append("HTTP interface:")
        for ep in http_eps:
            lines.append(f"  - {ep.get('method','GET')} {ep.get('path','/')}  # {ep.get('summary','')}")

    if cases:
        lines.append("Test cases:")
        for c in cases:
            lines.append(f"  - input: {c.get('input','')}")
            lines.append(f"    expect_output: {c.get('expect_output','')}")

    # Contrato de salida (tu generador ya lo espera)
    lines.append("")
    lines.append("Output contract for generator:")
    lines.append("- Return JSON with keys: yamlfilecontent (required), containerfilecontent (optional), pythonfilecontent (optional).")
    lines.append("- YAML must include a Deployment and a Service consistent with the spec.")
    lines.append("- If 'codefile' and 'containerfile' were requested, provide both pythonfilecontent and containerfilecontent consistent with image_name.")

    return "\n".join(lines)



if __name__ == "__main__":

    model = "deepseek-r1:32b"
    method = "json-with-required"

    coreintent0 = {
   "request": "how to bake an asdfjai cake",
   "answer": "-1",
   "iteration": 0,
   "last-try": {
      "iteration": -1,
      "answer": "-1",
      "grade": {
         "score": -1,
         "explanation": "-1"
      },
      "valid": 0
   },
   "grade": {
      "score": -1,
      "explanation": "-1"
   },
   "valid": 0
}

    coreintent1 = {
    "request": "how to bake a cake",
    "answer": {
        "improvement_plan": [
            "Provide a detailed list of ingredients required for baking a cake, including quantities.",
            "Develop clear and concise step-by-step instructions covering preparation, mixing, baking, and cooling processes.",
            "Include essential tips to ensure successful baking, such as preheating the oven and avoiding overmixing."
        ],
        "answer": {
            "ingredients": [
                "1 \u00bd cups all-purpose flour",
                "1 cup sugar",
                "1 \u00be teaspoons baking powder",
                "\u00bc teaspoon salt",
                "\u00bd cup unsalted butter (softened)",
                "2 large eggs",
                "2 teaspoons vanilla extract",
                "1 cup milk"
            ],
            "steps": [
                1.0,
                2.0,
                3.0,
                4.0,
                5.0,
                6.0
            ],
            "tips": [
                "Preheat your oven and prepare the cake pan before you start mixing.",
                "Don't overmix the batter; stop when just combined to keep the cake tender.",
                "Let the cake cool completely in the pan set on a wire rack to prevent sogginess."
            ]
        },
        "score": 5
    },
    "iteration": 8,
    "last-try": {
        "iteration": 7,
        "answer": {
            "improvement_plan": [
                "Include comprehensive details about ingredients required for baking a cake.",
                "Add step-by-step instructions to guide through the baking process.",
                "Provide tips or common mistakes to avoid in cake baking."
            ]
        },
        "grade": {
            "explanation": "The improvement plan suggests adding specific details about ingredients, step-by-step instructions, and tips or common mistakes. However, it does not provide the actual content required to bake a cake. Therefore, while the suggestions are relevant, they do not fulfill the request to explain how to bake a cake.",
            "score": 2,
            "suggested_action": "regenerate_from_zero",
            "clarification_question": "Could you provide a step-by-step guide on how to bake a cake?",
            "regenerate_rationale": "The answer needs to include specific ingredients and detailed steps to bake a cake."
        },
        "valid": 0
    },
    "grade": {
        "explanation": "The answer provides a comprehensive list of ingredients, clear step-by-step instructions, and useful tips for baking a cake. It addresses all necessary aspects without missing key points.",
        "score": 5,
        "suggested_action": "approve",
        "regenerate_rationale": "The answer is perfect."
    },
    "valid": 1
    }

    coreintent2 = {
    "request": "how to bake a cake",
    "answer": {
       "improvement_plan": {
          "issue": "The current score is 1 because the answer did not provide a recipe or instructions for baking a cake.",
          "fix": "To improve, we will include a detailed recipe and step-by-step instructions for baking a cake.",
          "evidence_from_previous": "The previous response focused on an improvement plan rather than addressing the user's request."
       },
       "steps": [
          {
             "step": 1,
             "description": "Preheat your oven to 350\u00b0F (175\u00b0C). Grease and flour a 9-inch cake pan or line it with parchment paper."
          },
          {
             "step": 2,
             "description": "In a large bowl, whisk together 1\u00be cups (220g) all-purpose flour, \u00bd teaspoon baking powder, and \u00bd teaspoon salt."
          },
          {
             "step": 3,
             "description": "In another bowl, beat \u00bd cup (115g) unsalted butter until creamy. Gradually add 1 cup (200g) granulated sugar and beat until light and fluffy. Add 2 large eggs, one at a time, beating well after each addition."
          },
          {
             "step": 4,
             "description": "Stir in 2 teaspoons vanilla extract."
          },
          {
             "step": 5,
             "description": "Gradually add the dry ingredients to the butter mixture alternately with \u2153 cup (78ml) milk, beginning and ending with the dry ingredients. Mix until just combined."
          },
          {
             "step": 6,
             "description": "Pour the batter into the prepared pan and smooth the top with a spatula."
          },
          {
             "step": 7,
             "description": "Bake for 25-30 minutes or until a toothpick inserted into the center comes out clean."
          },
          {
             "step": 8,
             "description": "Let the cake cool in the pan for 10 minutes, then transfer it to a wire rack to cool completely before serving."
          }
       ]
    },
    "iteration": 2,
    "last-try": {
       "iteration": 1,
       "answer": {
          "improvement_plan": {
             "issue": "The current score is 5 because the answer already fully meets the request with clear ingredients and logical steps.",
             "fix": "No further improvement is needed as the answer already provides a complete and accurate guide to baking a cake.",
             "evidence_from_previous": "All necessary ingredients are listed with specific measurements, and the steps are ordered logically."
          }
       },
       "grade": {
          "explanation": "The request was asking for how to bake a cake. The answer provided a detailed improvement plan but did not include an actual recipe or instructions on baking a cake. Therefore, it does not directly address the user's request.",
          "score": 1,
          "suggested_action": "regenerate_from_zero",
          "clarification_question": "Could you provide a step-by-step guide for baking a cake including ingredients and measurements?"
       },
       "valid": 0
    },
    "grade": {
       "explanation": "The response provides a clear and detailed step-by-step recipe for baking a cake, addressing all aspects of the request. The instructions are thorough, including ingredients, measurements, and specific cooking times. There is no missing information, and each step logically follows the previous one. The language is straightforward and easy to follow, making it accessible for both novice and experienced bakers.",
       "score": 5,
       "suggested_action": "approve"
    },
    "valid": 1
    }

    coreintent3 = {
   "request": "how to bake an asdfjai cake",
   "answer": {
      "title": "Baking an Asdfjai Cake",
      "ingredients": [
         {
            "name": "Flour",
            "amount": "2 cups"
         },
         {
            "name": "Sugar",
            "amount": "1 3/4 cups"
         },
         {
            "name": "Baking powder",
            "amount": "1 1/2 tsp"
         },
         {
            "name": "Salt",
            "amount": "1/2 tsp"
         },
         {
            "name": "Milk",
            "amount": "1 cup"
         },
         {
            "name": "Vegetable oil",
            "amount": "1/2 cup"
         },
         {
            "name": "Eggs",
            "amount": "2 large"
         },
         {
            "name": "Vanilla extract",
            "amount": "2 tsp"
         },
         {
            "name": "Asdfjai (Cuban fruit similar to apples)",
            "amount": "4 medium, peeled and chopped"
         }
      ],
      "steps": [
         {
            "step": 1,
            "description": "Preheat your oven to 350\u00b0F (175\u00b0C)."
         },
         {
            "step": 2,
            "description": "Mix dry ingredients in a large bowl: flour, sugar, baking powder, and salt."
         },
         {
            "step": 3,
            "description": "Add wet ingredients to the dry mixture: milk, oil, eggs, vanilla extract, and chopped asdfjai. Mix until well combined."
         },
         {
            "step": 4,
            "description": "Pour the batter into a greased cake pan."
         },
         {
            "step": 5,
            "description": "Bake for about 25-30 minutes, or until a toothpick inserted into the center comes out clean."
         },
         {
            "step": 6,
            "description": "Cool the cake in the pan for 10 minutes before transferring to a wire rack to cool completely."
         }
      ],
      "improvement_plan": {
         "issue": "The original answer did not address incorporating asdfjai into the cake.",
         "fix": "Added asdfjai (described as a Cuban fruit similar to apples) to the ingredients list and included it in the mixing step to integrate it into the cake batter.",
         "evidence_from_previous": "Previous response lacked specific information about asdfjai, which was clarified by the user as a unique ingredient."
      }
   },
   "iteration": 2,
   "last-try": {
      "iteration": 1,
      "answer": {
         "title": "Baking an Asdfjai Cake",
         "ingredients": [
            {
               "name": "Flour",
               "amount": "2 cups"
            },
            {
               "name": "Sugar",
               "amount": "1 3/4 cups"
            },
            {
               "name": "Baking powder",
               "amount": "1 1/2 tsp"
            },
            {
               "name": "Salt",
               "amount": "1/2 tsp"
            },
            {
               "name": "Milk",
               "amount": "1 cup"
            },
            {
               "name": "Vegetable oil",
               "amount": "1/2 cup"
            },
            {
               "name": "Eggs",
               "amount": "2 large"
            },
            {
               "name": "Vanilla extract",
               "amount": "2 tsp"
            },
            {
               "name": "Asdfjai (Cuban fruit similar to apples)",
               "amount": "4 medium, peeled and chopped"
            }
         ],
         "steps": [
            {
               "step": 1,
               "description": "Preheat your oven to 350\u00b0F (175\u00b0C)."
            },
            {
               "step": 2,
               "description": "Mix dry ingredients in a large bowl: flour, sugar, baking powder, and salt."
            },
            {
               "step": 3,
               "description": "Add wet ingredients to the dry mixture: milk, oil, eggs, vanilla extract, and chopped asdfjai. Mix until well combined."
            },
            {
               "step": 4,
               "description": "Pour the batter into a greased cake pan."
            },
            {
               "step": 5,
               "description": "Bake for about 25-30 minutes, or until a toothpick inserted into the center comes out clean."
            },
            {
               "step": 6,
               "description": "Cool the cake in the pan for 10 minutes before transferring to a wire rack to cool completely."
            }
         ],
         "improvement_plan": {
            "issue": "The original answer did not address incorporating asdfjai into the cake.",
            "fix": "Added asdfjai (described as a Cuban fruit similar to apples) to the ingredients list and included it in the mixing step to integrate it into the cake batter.",
            "evidence_from_previous": "Previous response lacked specific information about asdfjai, which was clarified by the user as a unique ingredient."
         }
      },
      "grade": {
         "explanation": "The answer provided is comprehensive and addresses the user's request effectively by incorporating asdfjai into the cake recipe. The ingredients list includes the specified fruit, and the steps clearly outline its inclusion. The improvement plan also shows a good understanding of the original query's intent. However, since 'asdfjai' isn't a recognized term, it's essential to confirm that this is indeed the correct fruit intended by the user to ensure the recipe's accuracy.",
         "score": 4,
         "suggested_action": "ask_clarification",
         "clarification_question": "Could you clarify what kind of cake you're referring to? The term 'asdfjai' doesn't correspond to any known type of cake.",
         "clarification_answer": "'asdfjai' is a cuban fruit, i want to include them in my cake"
      },
      "valid": 0
   },
   "grade": {
      "explanation": "The user initially asked about baking an 'asdfjai' cake. Upon noticing that 'asdfjai' doesn't correspond to a known type of cake, I requested clarification. The user specified that 'asdfjai' is a Cuban fruit similar to apples and wanted it included in their cake. With this information, the recipe was adjusted to include asdfjai as an ingredient, ensuring it's properly integrated into the batter for flavor and texture.",
      "score": 5,
      "suggested_action": "approve"
   },
   "valid": 1
}

    coreintent4 = {
   "request": "how to bake an asdfjai cake",
   "answer": {
      "title": "Baking an Asdfjai Cake",
      "ingredients": [
         {
            "name": "Flour",
            "amount": "2 cups"
         },
         {
            "name": "Sugar",
            "amount": "1 3/4 cups"
         },
         {
            "name": "Baking powder",
            "amount": "1 1/2 tsp"
         },
         {
            "name": "Salt",
            "amount": "1/2 tsp"
         },
         {
            "name": "Milk",
            "amount": "1 cup"
         },
         {
            "name": "Vegetable oil",
            "amount": "1/2 cup"
         },
         {
            "name": "Eggs",
            "amount": "2 large"
         },
         {
            "name": "Vanilla extract",
            "amount": "2 tsp"
         },
         {
            "name": "Asdfjai (Cuban fruit similar to apples)",
            "amount": "4 medium, peeled and chopped"
         }
      ],
      "steps": [
         {
            "step": 1,
            "description": "Preheat your oven to 350\u00b0F (175\u00b0C)."
         },
         {
            "step": 2,
            "description": "Mix dry ingredients in a large bowl: flour, sugar, baking powder, and salt."
         },
         {
            "step": 3,
            "description": "Add wet ingredients to the dry mixture: milk, oil, eggs, vanilla extract, and chopped asdfjai. Mix until well combined."
         },
         {
            "step": 4,
            "description": "Pour the batter into a greased cake pan."
         },
         {
            "step": 5,
            "description": "Bake for about 25-30 minutes, or until a toothpick inserted into the center comes out clean."
         },
         {
            "step": 6,
            "description": "Cool the cake in the pan for 10 minutes before transferring to a wire rack to cool completely."
         }
      ],
      "improvement_plan": {
         "issue": "The original answer did not address incorporating asdfjai into the cake.",
         "fix": "Added asdfjai (described as a Cuban fruit similar to apples) to the ingredients list and included it in the mixing step to integrate it into the cake batter.",
         "evidence_from_previous": "Previous response lacked specific information about asdfjai, which was clarified by the user as a unique ingredient."
      }
   },
   "iteration": 2,
   "last-try": {
      "iteration": 1,
      "answer": {
         "title": "Baking an Asdfjai Cake",
         "ingredients": [
            {
               "name": "Flour",
               "amount": "2 cups"
            },
            {
               "name": "Sugar",
               "amount": "1 3/4 cups"
            },
            {
               "name": "Baking powder",
               "amount": "1 1/2 tsp"
            },
            {
               "name": "Salt",
               "amount": "1/2 tsp"
            },
            {
               "name": "Milk",
               "amount": "1 cup"
            },
            {
               "name": "Vegetable oil",
               "amount": "1/2 cup"
            },
            {
               "name": "Eggs",
               "amount": "2 large"
            },
            {
               "name": "Vanilla extract",
               "amount": "2 tsp"
            },
            {
               "name": "Asdfjai (Cuban fruit similar to apples)",
               "amount": "4 medium, peeled and chopped"
            }
         ],
         "steps": [
            {
               "step": 1,
               "description": "Preheat your oven to 350\u00b0F (175\u00b0C)."
            },
            {
               "step": 2,
               "description": "Mix dry ingredients in a large bowl: flour, sugar, baking powder, and salt."
            },
            {
               "step": 3,
               "description": "Add wet ingredients to the dry mixture: milk, oil, eggs, vanilla extract, and chopped asdfjai. Mix until well combined."
            },
            {
               "step": 4,
               "description": "Pour the batter into a greased cake pan."
            },
            {
               "step": 5,
               "description": "Bake for about 25-30 minutes, or until a toothpick inserted into the center comes out clean."
            },
            {
               "step": 6,
               "description": "Cool the cake in the pan for 10 minutes before transferring to a wire rack to cool completely."
            }
         ],
         "improvement_plan": {
            "issue": "The original answer did not address incorporating asdfjai into the cake.",
            "fix": "Added asdfjai (described as a Cuban fruit similar to apples) to the ingredients list and included it in the mixing step to integrate it into the cake batter.",
            "evidence_from_previous": "Previous response lacked specific information about asdfjai, which was clarified by the user as a unique ingredient."
         }
      },
      "grade": {
         "explanation": "The answer provided is comprehensive and addresses the user's request effectively by incorporating asdfjai into the cake recipe. The ingredients list includes the specified fruit, and the steps clearly outline its inclusion. The improvement plan also shows a good understanding of the original query's intent. However, since 'asdfjai' isn't a recognized term, it's essential to confirm that this is indeed the correct fruit intended by the user to ensure the recipe's accuracy.",
         "score": 4,
         "suggested_action": "ask_clarification",
         "clarification_question": "Could you clarify what kind of cake you're referring to? The term 'asdfjai' doesn't correspond to any known type of cake.",
         "clarification_answer": "'asdfjai' is a cuban fruit, i want to include them in my cake"
      },
      "valid": 0
   },
   "grade": {
      "explanation": "The answer provided is comprehensive and addresses the user's request effectively by incorporating asdfjai into the cake recipe. The ingredients list includes the specified fruit, and the steps clearly outline its inclusion. The improvement plan also shows a good understanding of the original query's intent. However, since 'asdfjai' isn't a recognized term, it's essential to confirm that this is indeed the correct fruit intended by the user to ensure the recipe's accuracy.",
      "score": 4,
      "suggested_action": "ask_clarification",
      "clarification_question": "Could you clarify what kind of cake you're referring to? The term 'asdfjai' doesn't correspond to any known type of cake.",
      "clarification_answer": "'asdfjai' is a cuban fruit, i want to include them in my cake"
   },
   "valid": 0
}

    coreintent5 = {
   "request": "how to bake an asdfjai cake",
   "answer": {
      "title": "Baking a Cake",
      "ingredients": [
         {
            "name": "Flour",
            "amount": "2 cups"
         },
         {
            "name": "Sugar",
            "amount": "1 3/4 cups"
         },
         {
            "name": "Baking powder",
            "amount": "1 1/2 tsp"
         },
         {
            "name": "Salt",
            "amount": "1/2 tsp"
         },
         {
            "name": "Milk",
            "amount": "1 cup"
         },
         {
            "name": "Vegetable oil",
            "amount": "1/2 cup"
         },
         {
            "name": "Eggs",
            "amount": "2 large"
         },
         {
            "name": "Vanilla extract",
            "amount": "2 tsp"
         }
      ],
      "steps": [
         {
            "step": 1,
            "description": "Preheat your oven to 350\u00b0F (175\u00b0C)."
         },
         {
            "step": 2,
            "description": "Mix dry ingredients in a large bowl: flour, sugar, baking powder, and salt."
         },
         {
            "step": 3,
            "description": "Add wet ingredients to the dry mixture: milk, oil, eggs, and vanilla extract. Mix until well combined."
         },
         {
            "step": 4,
            "description": "Pour the batter into a greased cake pan."
         },
         {
            "step": 5,
            "description": "Bake for about 25-30 minutes, or until a toothpick inserted into the center comes out clean."
         },
         {
            "step": 6,
            "description": "Cool the cake in the pan for 10 minutes before transferring to a wire rack to cool completely."
         }
      ]
   },
   "iteration": 1,
   "last-try": {
      "iteration": 0,
      "answer": {
         "title": "Baking a Cake",
         "ingredients": [
            {
               "name": "Flour",
               "amount": "2 cups"
            },
            {
               "name": "Sugar",
               "amount": "1 3/4 cups"
            },
            {
               "name": "Baking powder",
               "amount": "1 1/2 tsp"
            },
            {
               "name": "Salt",
               "amount": "1/2 tsp"
            },
            {
               "name": "Milk",
               "amount": "1 cup"
            },
            {
               "name": "Vegetable oil",
               "amount": "1/2 cup"
            },
            {
               "name": "Eggs",
               "amount": "2 large"
            },
            {
               "name": "Vanilla extract",
               "amount": "2 tsp"
            }
         ],
         "steps": [
            {
               "step": 1,
               "description": "Preheat your oven to 350\u00b0F (175\u00b0C)."
            },
            {
               "step": 2,
               "description": "Mix dry ingredients in a large bowl: flour, sugar, baking powder, and salt."
            },
            {
               "step": 3,
               "description": "Add wet ingredients to the dry mixture: milk, oil, eggs, and vanilla extract. Mix until well combined."
            },
            {
               "step": 4,
               "description": "Pour the batter into a greased cake pan."
            },
            {
               "step": 5,
               "description": "Bake for about 25-30 minutes, or until a toothpick inserted into the center comes out clean."
            },
            {
               "step": 6,
               "description": "Cool the cake in the pan for 10 minutes before transferring to a wire rack to cool completely."
            }
         ]
      },
      "grade": {
         "explanation": "The response provided does not address baking an 'asdfjai' cake, which seems to be a typo or fictional term. Instead, it offers a general cake recipe.",
         "score": 2,
         "suggested_action": "ask_clarification",
         "clarification_question": "Could you clarify what kind of cake you're referring to? The term 'asdfjai' doesn't correspond to any known type of cake.",
         "clarification_answer": "'asdfjai' is a cuban fruit, very similar to apples, only their name is different, i want to include them in my cake"
      },
      "valid": 0
   },
   "grade": {
      "explanation": "The response provided does not address baking an 'asdfjai' cake, which seems to be a typo or fictional term. Instead, it offers a general cake recipe.",
      "score": 2,
      "suggested_action": "ask_clarification",
      "clarification_question": "Could you clarify what kind of cake you're referring to? The term 'asdfjai' doesn't correspond to any known type of cake.",
      "clarification_answer": "'asdfjai' is a cuban fruit, very similar to apples, only their name is different, i want to include them in my cake"
   },
   "valid": 0
}

    constraints = join_bullets("Constraints", PRESETS["generic"]["constraints"])
    acceptance = join_bullets("Acceptance", PRESETS["generic"]["acceptance"])
    #print(f"{constraints}\n{acceptance}")

    #print("==================")
    generation_context = build_generation_context(coreintent3, "kubernetes_service")
    #print(generation_context)
    #print("==================")
    validation_context = build_validation_context(coreintent3, "kubernetes_service")
    #print(validation_context)

    if (len(sys.argv) > 1 ):
        act = int(sys.argv[1])
        if act == 1:
            intent, success = generate(coreintent4, model, method)
            intent = json.loads(intent)
            print(json.dumps(intent, indent=4))
        elif act == 2:
            grade, valid, success = judge(coreintent5, method="llm-as-a-judge", model="deepseek-r1:32b")
            print(json.dumps(grade, indent=4))
        elif act == 3:
            print(generation_context)
        elif act == 4:
            print(validation_context)