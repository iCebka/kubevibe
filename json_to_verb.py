import json

"""
def dict_to_text(dito, ind=0):
    print(f"ind: {ind}")
    for i in dito:
        stru = ""
        for m in range(ind):
            stru += " "
        if isinstance(dito, list):
            element = i
        else:
            element = dito[i]

        if isinstance(element, str):
            stru += f"{i}: {element}"
            print(stru)
        elif isinstance(element, dict):
            print("aqui entro a dict")
            print(f"{i}: ")
            dict_to_text(element, ind+1)
        elif isinstance(element, list):
            print(f"{i}:")
            for l in element:
                if isinstance(lc, str):
                    print(l)
                else:
                    dict_to_text(l, ind+1)
        else:
            print(f"{i}: {element}")
"""
            
def dict_to_text(data, indent=0, step=2):
    """
    Pretty-prints a dict/list in a YAML-like layout.
    - Skips empty values (None, '', [], {})
    - Dict -> 'key: value' or 'key:' + nested
    - List of scalars -> '- value'
    - List of dicts -> '- first_key: value' inline, rest indented
    """
    lines = []
    pad = " " * indent

    # Handle dicts
    if isinstance(data, dict):
        for k, v in data.items():
            # Skip empty or None values
            if v in (None, "", [], {}):
                continue

            if isinstance(v, (dict, list)):
                # Only print header if non-empty after filtering
                subtext = dict_to_text(v, indent + step, step)
                if subtext.strip():
                    lines.append(f"{pad}{k}:")
                    lines.append(subtext)
            else:
                lines.append(f"{pad}{k}: {v}")

    # Handle lists
    elif isinstance(data, list):
        for item in data:
            # Skip empty items
            if item in (None, "", [], {}):
                continue

            # Scalar item
            if not isinstance(item, (dict, list)):
                lines.append(f"{pad}- {item}")
                continue

            # Dict item
            if isinstance(item, dict):
                items = [(k, v) for k, v in item.items() if v not in (None, "", [], {})]
                if not items:
                    continue

                first_k, first_v = items[0]

                # Print first key inline
                if isinstance(first_v, (dict, list)):
                    lines.append(f"{pad}- {first_k}:")
                    lines.append(dict_to_text(first_v, indent + step + 2, step))
                else:
                    lines.append(f"{pad}- {first_k}: {first_v}")

                # Print the rest indented
                subpad = " " * (indent + 2)
                for k, v in items[1:]:
                    if isinstance(v, (dict, list)):
                        subtext = dict_to_text(v, indent + 2 + step, step)
                        if subtext.strip():
                            lines.append(f"{subpad}{k}:")
                            lines.append(subtext)
                    else:
                        lines.append(f"{subpad}{k}: {v}")

            # Nested list item
            else:
                subtext = dict_to_text(item, indent + step, step)
                if subtext.strip():
                    lines.append(f"{pad}-")
                    lines.append(subtext)

    # Handle scalars
    else:
        lines.append(f"{pad}{data}")

    return "\n".join(lines)

def schema_to_text(spec):
    for i in spec:
        if isinstance(spec[i], str):
            print(f"{i}: {spec[i]}")


if __name__ == "__main__":

    example1 = {
        'version': '1.0', 
        'name': 'credit-card-validation-service', 
        'description': 'A cloud-native microservice for validating credit card information.', 
        'functionality': 'Receives credit card details and validates them based on predefined criteria.', ''
        'artifacts': {
            'layout': {
                'codefile': {
                    'language': 'python', 
                    'version': '3.9', 
                    'file': 'myapp.py', 
                    'dependencies': [], 
                    'env': []
                }, 
                'containerfile': {
                    'runtime': 'docker', 
                    'base_image': 'python:3.9-slim', 
                    'image_name': 'localhost:32000/myapp:latest', 
                    'file': 'Dockerfile'
                }, 
                'requirements': [], 
                'manifest': {
                    'include': ['deployment', 'service'], 
                    'image': 'localhost:32000/myapp:latest', 
                    'file': 'vibe.yaml'
                }
            }, 
            'generate': ['containerfile', 'codefile', 'manifest']
        }, 
        'deployment': {
            'replicas': 1, 
            'resources': {
                'requests': {
                    'cpu': '50m', 
                    'memory': '64Mi'
                }, 
                'limits': {
                    'cpu': '200m', 
                    'memory': '256Mi'
                }
            }, 
            'service': {
                'type': 'ClusterIP', 
                'port': 80, 
                'target_port': 80
            }
        }, 
        'interface': {
            'http': [{
                'method': 'POST', 
                'path': '/validate', 
                'summary': 'Validate credit card information.'
            }]
        }, 
        'tests': {
            'cases': []
        }
    }

    example2 = {
    "service_name": "credit-card-validation-service",
    "image": "creditcardvalidationsvc:v1.0",
    "version": "v1.0",
    "replicas": 2,
    "port": 8080,
    "type": "ClusterIP",
    "env_vars": {
        "CARD_SERVICE_URL": "",
        "SECRET_KEY": ""
    },
    "resources": {
        "limits": {
        "cpu": "500m",
        "memory": "256Mi"
        },
        "requests": {
        "cpu": "250m",
        "memory": "128Mi"
        }
    },
    "volumes": [],
    "volume_mounts": [],
    "liveness_probe": {
        "http_get": {
        "path": "/healthz",
        "port": 8080
        },
        "initial_delay_seconds": 30,
        "timeout_seconds": 5
    },
    "readiness_probe": {
        "http_get": {
        "path": "/ready",
        "port": 8080
        },
        "initial_delay_seconds": 10,
        "timeout_seconds": 2
    }
    }


    #print(json.dumps(example, indent=4))

    verb = dict_to_text(example1)
    print(verb)