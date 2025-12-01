def artifacts_schema():
    return {
        "type": "object",
        "properties": {
            "yamlfilecontent": {
                "type": "string"
            },
            "containerfilecontent": {
                "type": "string"
            },
            "pythonfilecontent": {
                "type": "string"
            },
            "requirements": {
                "type": "string"
            }
        },
        "required": ["pythonfilecontent", "containerfilecontent", "yamlfilecontent","requirements"]
    }

def fix_schema():
    return {
        "type": "object",
        "properties": {
            "vibe.yaml": {
                "type": "string"
            },
            "Dockerfile": {
                "type": "string"
            },
            "myapp.py": {
                "type": "string"
            },
            "requirements.txt": {
                "type": "string"
            },
            "explanation": {
                "type": "string"
            }
        },
        "required": ["explanation", "vibe.yaml", "Dockerfile", "requirements.txt", "myapp.py"]
    }