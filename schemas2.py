
def recipe_schema():
    return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string"
                    },
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string"
                                },
                            "amount": {
                                "type": "string"
                                }
                            },
                        "required": ["name", "amount"]
                        }
                    },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": { 
                                "type": "number"
                                },
                            "description": {
                                "type": "string"
                                }
                            },
                        "required": ["step", "description"]
                        }
                    },
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["title", "ingredients", "steps"]
        }

def service_schema():
    return {
        "type": "object",
        "properties": {
            "version": {
                "type": "string",
                "enum": ["1.0"]
            },
            "name": {
                "type": "string"
            },
            "description": {
                "type": "string"
            },
            "functionality": {
                "type": "string"
            },
            "artifacts": {
                "type": "object",
                "properties": {
                    "layout": {
                        "type": "object",
                        "properties": {
                            "codefile": {
                                "type": "object",
                                "properties": {
                                    "language":{
                                        "type": "string",
                                        "enum": ["python"]
                                    },
                                    "version": {
                                        "type": "string"
                                    },
                                    "dependencies": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        }
                                    },
                                    # env
                                    "file": {
                                        "type": "string",
                                        "enum": ["myapp.py"]
                                    },
                                },
                                "required": ["language", "version", "file"]
                            },
                            "containerfile": {
                                "type": "object",
                                "properties": {
                                    "runtime": {
                                        "type": "string",
                                        "enum": ["docker"]
                                    },
                                    "base_image": {
                                        "type": "string"
                                    },
                                    "image_name": {
                                        "type": "string",
                                        "enum": ["localhost:32000/myapp:latest"]
                                    },
                                    "file": {
                                        "type": "string",
                                        "enum": ["Dockerfile"]
                                    }
                                },
                                "required": ["runtime", "base_image", "image_name", "file"]
                            },
                            "yamlfile": {
                                "type": "object",
                                "properties": {
                                    "include": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "enum": ["deployment", "service"],
                                            "minItems": 2
                                        }
                                    },
                                    "image": {
                                        "type": "string",
                                         "enum": ["localhost:32000/myapp:latest"]
                                    },
                                    "file": {
                                        "type": "string",
                                        "enum": ["vibe.yaml"]
                                    }
                                },
                                "required": ["include", "image", "file"]
                            },
			    "requirements": {
				"type": "array",
				"items": {
				    "items": {
				        "type": "string"
				    }
				}
			    }
                        },
                        "required": ["codefile", "containerfile", "yamlfile"]
                    }
                },
                "required": ["layout"]
            },
            "deployment": {
                "type": "object",
                "properties": {
                    "replicas": {
                        "type": "integer",
                        "minimum": 1
                    },
                    "resources": {
                        "type": "object",
                        "properties": {
                            "requests": {
                                "type": "object",
                                "properties": {
                                    "cpu": {
                                        "type": "string"
                                    },
                                    "memory": {
                                        "type": "string"
                                    }
                                },
                                "required": [ "cpu", "memory"]
                            },
                            "limits": {
                                "type": "object",
                                "properties": {
                                    "cpu": {
                                        "type": "string"
                                    },
                                    "memory": {
                                        "type": "string"
                                    }
                                },
                                "required": ["cpu", "memory"]
                            }
                        },
                        "required": ["requests", "limits"]
                    },
                    "service": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["ClusterIP", "NodePort"]
                            },
                            "port": {
                                "type": "integer",
                                "enum": ["80", "443", "5000"]
                            },
                            "target_port": {
                                "type": "integer",
                                "enum": ["80", "443", "5000"]
                            }
                        },
                        "required": ["type", "port", "target_port"]
                    }
                },
                "required": ["replicas", "resources", "service"]
            },
            "interface": {
                "type": "object",
                "properties": {
                    "http": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "method": {
                                    "type": "string",
                                    "enum": ["GET", "POST"]
                                },
                                "path": {
                                    "type": "string"
                                },
                                "summary": {
                                    "type": "string"
                                }
                            },
                            "required": ["method", "path"]
                        }
                    }
                },
                "required": ["http"] #not sure if neccesarily required
            },
            "tests": {
                "type": "object",
                "properties": {
                    "cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "input": {
                                    "type": "string"
                                },
                                "expect_output": {
                                    "type": "string"
                                }
                            },
                            "required": ["input", "expect_output"]
                        }
                    }
                },
                "required": ["cases"]
            }
        },
        "required": ["version", "name", "description", "functionality", "artifacts", "deployment", "interface"]
    }


def answer_schema():
    return {
        "type": "object",
        "properties": { 
            "title": {
                "type": "string"
            },
            "explanation":{
                "type": "string"
            },
            "notes":{
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["explanation"]
    }

def validation_schema():
    return {
        "type": "object",
        "properties": { 
            "explanation": {
                "type": "string"
            },
            "score": {
                "type": "number"
            },
            "suggested_action": {
                "type": "string",
                "enum": [
                    "approve",
                    #"ask_clarification",
                    "retry"
                ]
            },
            "clarification_question": { "type": "string" },
            "retry_rationale": { "type": "string" }
        },
        "required": ["explanation", "score", "suggested_action"],
        "allOf": [
                {
                    "if": {
                        "properties": {
                            "suggested_action": {
                                "const": "ask"
                            }
                        }
                    },
                    "then": {
                        "required": ["clarification_question"]
                    }
                },
                {
                    "if": {
                        "properties": {
                            "suggested_action": {
                                "const": "no_ask"
                                }
                        }
                    },
                    "then": {
                        "required": ["rationale"]
                    }
                }
            ]
    }

def validation_schema_strict():
    return {
        "type": "object",
        "properties": {
            "explanation": {"type": "string"},
            "score": {"type": "number"},  # allow 1..5, we constrain via if/then
            "suggested_action": {
                "type": "string",
                "enum": ["approve", 
                        # "ask",
                         "retry"]
            },
            "clarification_question": {"type": "string"},
            "retry_rationale": {"type": "string"},
            # optional signals the judge can set; you can use them in your fallback
            "ambiguity_detected": {"type": "boolean"},
            "unknown_terms": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["explanation", "score", "suggested_action"],
        "allOf": [
            # approve ⇒ score must be exactly 5; must NOT include retry/ask fields
            {
                "if": {"properties": {"suggested_action": {"const": "approve"}}},
                "then": {
                    "properties": {"score": {"minimum": 5, "maximum": 5}},
                    "not": {"anyOf": [
                        {"required": ["clarification_question"]},
                        {"required": ["retry_rationale"]}
                    ]}
                }
            },
            # ask ⇒ must include clarification_question; score <= 3; must NOT include retry_rationale
            {
                "if": {"properties": {"suggested_action": {"const": "ask"}}},
                "then": {
                    "required": ["clarification_question"],
                    "properties": {"score": {"maximum": 3}},
                    "not": {"required": ["retry_rationale"]}
                }
            },
            # retry ⇒ must include retry_rationale; score <= 4; must NOT include clarification_question
            {
                "if": {"properties": {"suggested_action": {"const": "retry"}}},
                "then": {
                    "required": ["retry_rationale"],
                    "properties": {"score": {"maximum": 4}},
                    "not": {"required": ["clarification_question"]}
                }
            }
        ]
    }


def improvement_schema():
    return {
        "type": "object",
        "properties": {
            "issue": {"type": "string"},
            "fix": {"type": "string"},
            "evidence_from_previous": {"type": "string"}
        },
        "required": ["issue", "fix", "evidence_from_previous"]
    }
