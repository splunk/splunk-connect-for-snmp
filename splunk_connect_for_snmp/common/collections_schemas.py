varbinds_type = {
    "type": "array",
    "items": {"type": "array", "items": {"type": ["integer", "string"]}},
}

standard_profile_schema = {
    "type": "object",
    "properties": {
        "frequency": {"type": "integer"},
        "varBinds": varbinds_type,
    },
    "required": ["frequency", "varBinds"],
    "additionalProperties": False,
}

walk_profile_schema = {
    "type": "object",
    "properties": {
        "varBinds": varbinds_type,
        "condition": {
            "type": "object",
            "properties": {"type": {"type": "string", "enum": ["walk"]}},
            "required": ["type"],
            "additionalProperties": False,
        },
    },
    "required": ["condition", "varBinds"],
    "additionalProperties": False,
}

base_profile_schema = {
    "type": "object",
    "properties": {
        "frequency": {"type": "integer"},
        "varBinds": varbinds_type,
        "condition": {
            "type": "object",
            "properties": {"type": {"type": "string", "enum": ["base", "mandatory"]}},
            "required": ["type"],
            "additionalProperties": False,
        },
    },
    "required": ["condition", "varBinds", "frequency"],
    "additionalProperties": False,
}

smart_profile_schema = {
    "type": "object",
    "properties": {
        "frequency": {"type": "integer"},
        "varBinds": varbinds_type,
        "condition": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["field"]},
                "field": {"type": "string"},
                "patterns": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type", "field", "patterns"],
            "additionalProperties": False,
        },
    },
    "required": ["condition", "varBinds", "frequency"],
    "additionalProperties": False,
}

conditional_profile_schema = {
    "type": "object",
    "properties": {
        "frequency": {"type": "integer"},
        "varBinds": varbinds_type,
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "operation": {
                        "type": "string",
                        "enum": ["lt", "gt", "regex", "in", "equals"],
                    },
                    "value": {"type": ["number", "string", "array"]},
                    "negate_operation": {"type": ["boolean", "string"]},
                },
                "required": ["field", "operation", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["conditions", "varBinds", "frequency"],
    "additionalProperties": False,
}


def get_all_profile_schemas():
    return [
        standard_profile_schema,
        walk_profile_schema,
        base_profile_schema,
        smart_profile_schema,
        conditional_profile_schema,
    ]


group_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "address": {"type": "string"},
            "port": {"type": "integer"},
            "community": {"type": "string"},
            "secret": {"type": "string"},
            "version": {"type": "string"},
            "security_engine": {"type": "string"},
            "max_oid_to_process": {"type": "integer"},
        },
        "required": ["address"],
        "additionalProperties": False,
    },
}


def get_all_group_schemas():
    return [group_schema]


engine_id_record_schema = {
    "type": "object",
    "properties": {
        "security_engine_id": {"type": "string", "pattern": "^[0-9a-fA-F]+$"},
        "host": {"type": "string"},
    },
    "required": ["security_engine_id", "host"],
    "additionalProperties": False,
}


def get_engine_id_record_schema():
    return engine_id_record_schema
