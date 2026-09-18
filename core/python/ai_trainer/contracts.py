"""Offline validator for the deliberately bounded JSON Schema subset in v1."""
import json
import math
from pathlib import Path
import re
from .domain import DomainError

REQUEST = json.loads(Path(__file__).with_name('request.schema.json').read_text())

def validate(value, schema, root=REQUEST):
    def fail(): raise DomainError('invalid', 'Invalid contract payload.')
    if '$ref' in schema: return validate(value, root['$defs'][schema['$ref'].split('/')[-1]], root)
    for keyword in ('oneOf','anyOf'):
        if keyword in schema:
            matches = 0
            for variant in schema[keyword]:
                try: validate(value, variant, root); matches += 1
                except DomainError: pass
            if matches == 0 or (keyword == 'oneOf' and matches != 1): fail()
    if 'const' in schema and (type(value) != type(schema['const']) or value != schema['const']): fail()
    if 'enum' in schema and value not in schema['enum']: fail()
    kind = schema.get('type')
    if kind == 'object':
        if not isinstance(value, dict) or not all(k in value for k in schema.get('required', [])): fail()
        properties = schema.get('properties', {})
        for key, item in value.items():
            if key in properties: validate(item, properties[key], root)
            elif schema.get('additionalProperties') is False: fail()
            elif isinstance(schema.get('additionalProperties'), dict): validate(item, schema['additionalProperties'], root)
    elif kind == 'array':
        if not isinstance(value, list): fail()
        if len(value) < schema.get('minItems', 0): fail()
        for item in value: validate(item, schema['items'], root)
    elif kind == 'string':
        if not isinstance(value, str): fail()
        if 'pattern' in schema and not re.fullmatch(schema['pattern'], value): fail()
    elif kind == 'boolean' and type(value) is not bool: fail()
    elif kind == 'integer' and type(value) is not int: fail()
    elif kind == 'number' and (type(value) not in (int,float) or not math.isfinite(value)): fail()
    elif kind == 'null' and value is not None: fail()
    if 'minimum' in schema and value < schema['minimum']: fail()
    if 'maximum' in schema and value > schema['maximum']: fail()
