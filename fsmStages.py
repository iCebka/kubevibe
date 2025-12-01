
stages = [
    #"START",
    "GENERATE",
    "BUILD",
    "VALIDATE",
    "DEPLOY",
    "CONNECT",
    "CHART",
    "SUCCESS",
    "FIX",
    "FAIL"
]

NEXT_ON_SUCCESS = {
    "GENERATE": "BUILD",
    "BUILD": "VALIDATE",
    "VALIDATE": "DEPLOY",
    "DEPLOY": "CONNECT",
    "CONNECT": "CHART",
    "CHART": "SUCCESS"
}

NEXT_ON_FAIL = {
    "GENERATE": "FIX",
    "BUILD": "FIX",
    "VALIDATE": "FIX",
    "DEPLOY": "FIX",
    "CONNECT": "FIX",
    "CHART": "FIX",
    "FIX": "FIX"
}

actions = {
    ("START", 1): "GENERATE",
    ("GENERATE", 1): "BUILD",
    ("BUILD", 1): "VALIDATE",
    ("VALIDATE", 1): "DEPLOY",
    ("DEPLOY", 1): "CONNECT",
    ("CONNECT", 1): "CHART",
    ("CHART", 1): "SUCCESS",
    ("FIX", 1): "BUILD",
    ("FIX", 1): "VALIDATE",
    ("FIX", 1): "DEPLOY",
    ("FIX", 1): "CONNECT",
    ("FIX", 1): "CHART",
    ("FIX", 0): "FIX",
    ("GENERATE", 0): "FIX",
    ("BUILD", 0): "FIX",
    ("VALIDATE", 0): "FIX",
    ("DEPLOY", 0): "FIX",
    ("CONNECT", 0): "FIX",
    ("CHART", 0): "FIX",
    ("FIX", 0): "FAIL"
}

