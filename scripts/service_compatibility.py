#!/usr/bin/env python3
"""Consumer/provider contract matrix: native Avro and conservative OpenAPI JSON.

Static compatibility is not a live consumer test or production deployment approval.
Unsupported schema constructs are UNKNOWN, never silently accepted.
"""
import argparse
import json
from pathlib import Path

from verify_implementation import digest, read_file


class Unknown(ValueError):
    pass


def avro_compatible(writer, reader):
    try:
        import avro.schema
        import avro.io
        from avro.compatibility import ReaderWriterCompatibilityChecker, SchemaCompatibilityType
    except ImportError as error:
        raise Unknown('install requirements-code-analysis.txt for native Avro checking') from error
    def logical(value):
        if isinstance(value, dict):
            return 'logicalType' in value or any(logical(v) for v in value.values())
        return isinstance(value, list) and any(logical(v) for v in value)
    if logical(writer) or logical(reader):
        raise Unknown('logical-type semantic compatibility requires an explicit codec/version check')
    try:
        w = avro.schema.parse(json.dumps(writer))
        r = avro.schema.parse(json.dumps(reader))
        def defaults(schema, seen):
            if id(schema) in seen:
                return
            seen.add(id(schema))
            for field in getattr(schema, 'fields', []):
                if field.has_default and not avro.io.validate(field.type, field.default):
                    raise Unknown('invalid Avro field default')
                defaults(field.type, seen)
            for child in getattr(schema, 'schemas', []):
                defaults(child, seen)
            for attribute in ('items', 'values'):
                child = getattr(schema, attribute, None)
                if child is not None:
                    defaults(child, seen)
        defaults(w, set()); defaults(r, set())
        result = ReaderWriterCompatibilityChecker().get_compatibility(r, w)
    except Exception as error:
        raise Unknown('invalid or unsupported Avro schema: ' + type(error).__name__) from None
    return {'compatible': result.compatibility == SchemaCompatibilityType.compatible,
            'issues': sorted(str(message) for message in result.messages),
            'checker': 'apache-avro-reader-writer', 'checker_version': avro.__version__}


def resolve(value, document, seen=()):
    if not isinstance(value, dict):
        raise Unknown('schema/operation must be an object')
    if '$ref' not in value:
        return value
    ref = value['$ref']
    if (not isinstance(ref, str) or not ref.startswith('#/') or ref in seen
            or set(value) != {'$ref'}):
        raise Unknown('external, recursive or sibling-bearing $ref requires another checker')
    result = document
    try:
        for part in ref[2:].split('/'):
            result = result[part.replace('~1', '/').replace('~0', '~')]
    except (KeyError, TypeError):
        raise Unknown('unresolved local $ref') from None
    return resolve(result, document, seen + (ref,))


def normalize(schema, document, stack=()):
    # Recursive refs also occur below properties; limit their traversal explicitly.
    ref = schema.get('$ref') if isinstance(schema, dict) else None
    if ref is not None and ref in stack:
        raise Unknown('recursive schemas require another checker')
    schema = resolve(schema, document)
    allowed = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum',
               'nullable', 'description', 'title', 'default', 'example', 'examples', 'deprecated'}
    if set(schema) - allowed:
        raise Unknown('unsupported schema keywords: ' + ','.join(sorted(set(schema) - allowed)))
    kind = schema.get('type')
    if kind not in ('object', 'array', 'string', 'integer', 'number', 'boolean'):
        raise Unknown('explicit supported scalar/object/array type required')
    if type(schema.get('nullable', False)) is not bool:
        raise Unknown('nullable must be boolean')
    result = {'type': kind, 'nullable': schema.get('nullable', False)}
    if 'enum' in schema:
        enum = schema['enum']
        if (not isinstance(enum, list) or not enum
                or any(isinstance(v, (dict, list)) for v in enum)):
            raise Unknown('only nonempty scalar enums supported')
        def valid_enum(value):
            if value is None:
                return result['nullable']
            return ((kind == 'string' and isinstance(value, str))
                    or (kind == 'integer' and type(value) is int)
                    or (kind == 'number' and type(value) in (int, float))
                    or (kind == 'boolean' and type(value) is bool))
        if not all(valid_enum(value) for value in enum):
            raise Unknown('invalid enum member type')
        result['enum'] = {json.dumps(v, sort_keys=True) for v in enum}
    stack = stack + ((ref,) if ref else ())
    if kind == 'object':
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        extra = schema.get('additionalProperties', True)
        if (not isinstance(properties, dict) or not isinstance(required, list)
                or not all(isinstance(name, str) and name in properties for name in required)
                or len(required) != len(set(required))):
            raise Unknown('invalid object properties/required')
        result['properties'] = {n: normalize(v, document, stack) for n, v in properties.items()}
        result['required'] = set(required)
        result['additional'] = extra if type(extra) is bool else normalize(extra, document, stack)
    elif kind == 'array':
        if 'items' not in schema:
            raise Unknown('array items required')
        result['items'] = normalize(schema['items'], document, stack)
    return result


def accepts(reader, writer, path='$'):
    issues = []
    def fail(reason):
        issues.append(path + ': ' + reason)
    if writer['nullable'] and not reader['nullable']:
        fail('writer permits null but reader rejects it')
    rtype, wtype = reader['type'], writer['type']
    if rtype != wtype and not (rtype == 'number' and wtype == 'integer'):
        fail('incompatible types ' + wtype + ' -> ' + rtype)
        return issues
    if 'enum' in reader and ('enum' not in writer or not writer['enum'] <= reader['enum']):
        fail('writer values exceed reader enum')
    if rtype == 'object':
        if not reader['required'] <= writer['required']:
            fail('writer does not guarantee required reader fields')
        rp, wp = reader['properties'], writer['properties']
        ra, wa = reader['additional'], writer['additional']
        for name, value in wp.items():
            if name in rp:
                issues += accepts(rp[name], value, path + '.' + name)
            elif ra is False:
                fail('reader rejects extra field ' + name)
            elif isinstance(ra, dict):
                issues += accepts(ra, value, path + '.' + name)
        for name in rp.keys() - wp.keys():
            if wa is True:
                fail('unconstrained writer extra field can violate reader field ' + name)
            elif isinstance(wa, dict):
                issues += accepts(rp[name], wa, path + '.' + name)
        if ra is False and wa is not False:
            fail('writer permits unspecified fields rejected by reader')
        elif isinstance(ra, dict):
            if wa is True:
                fail('unconstrained writer extra fields violate reader schema')
            elif isinstance(wa, dict):
                issues += accepts(ra, wa, path + '.*')
    elif rtype == 'array':
        issues += accepts(reader['items'], writer['items'], path + '[]')
    return issues


def content(media, document):
    if not isinstance(media, dict) or not media:
        raise Unknown('explicit response/request media schemas required')
    result = {}
    for name, entry in media.items():
        if not isinstance(entry, dict) or set(entry) - {'schema', 'example', 'examples'}:
            raise Unknown('unsupported media encoding or malformed media')
        result[name] = normalize(entry.get('schema'), document)
    return result


def openapi_compatible(before, after):
    for doc in (before, after):
        if not isinstance(doc, dict) or not isinstance(doc.get('openapi'), str) or not doc['openapi'].startswith(('3.0.', '3.1.')):
            raise Unknown('OpenAPI 3.0/3.1 JSON documents required')
        if not isinstance(doc.get('paths'), dict) or not doc['paths']:
            raise Unknown('explicit API paths required')
        if doc.get('webhooks'):
            raise Unknown('webhook compatibility requires a dedicated checker')
    if before.get('servers', []) != after.get('servers', []):
        raise Unknown('server topology changed')
    old_security = before.get('components', {}).get('securitySchemes', {})
    new_security = after.get('components', {}).get('securitySchemes', {})
    if old_security != new_security:
        raise Unknown('security scheme changed')
    issues = []
    methods = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'}
    for path, old_path in before['paths'].items():
        old_path = resolve(old_path, before)
        new_path = resolve(after['paths'].get(path, {}), after)
        if old_path.get('parameters') or new_path.get('parameters'):
            raise Unknown('path-level parameters require an extended checker')
        for method in methods & old_path.keys():
            old = resolve(old_path[method], before)
            if method not in new_path:
                issues.append(path + ' ' + method + ': operation removed'); continue
            new = resolve(new_path[method], after)
            for op in (old, new):
                if op.get('callbacks') or op.get('parameters') or op.get('servers'):
                    raise Unknown('callbacks/parameters/operation servers require an extended checker')
            if old.get('security', before.get('security', [])) != new.get('security', after.get('security', [])):
                raise Unknown('effective authorization contract changed')
            ob = resolve(old.get('requestBody', {}), before)
            nb = resolve(new.get('requestBody', {}), after)
            if type(ob.get('required',False)) is not bool or type(nb.get('required',False)) is not bool:
                raise Unknown('request-body required must be boolean')
            if nb.get('required', False) and not ob.get('required', False):
                issues.append(path + ': request body became required')
            if ob:
                oc, nc = content(ob.get('content'), before), content(nb.get('content'), after)
                if not oc.keys() <= nc.keys():
                    issues.append(path + ': supported request media removed')
                for media in oc.keys() & nc.keys():
                    issues += accepts(nc[media], oc[media], path + ' request ' + media)
            old_responses, new_responses = old.get('responses'), new.get('responses')
            if not isinstance(old_responses, dict) or not old_responses or not isinstance(new_responses, dict) or not new_responses:
                raise Unknown('explicit response maps required')
            for status, new_response in new_responses.items():
                old_response = old_responses.get(status, old_responses.get('default'))
                if old_response is None:
                    issues.append(path + ': unrecognized response status ' + status); continue
                nr, ore = resolve(new_response, after), resolve(old_response, before)
                if nr.get('headers') or ore.get('headers') or nr.get('links') or ore.get('links'):
                    raise Unknown('response headers/links require an extended checker')
                if not nr.get('content') and not ore.get('content'):
                    continue
                nc, oc = content(nr.get('content'), after), content(ore.get('content'), before)
                if nc.keys() != oc.keys():
                    issues.append(path + ': response media negotiation changed')
                for media in nc.keys() & oc.keys():
                    issues += accepts(oc[media], nc[media], path + ' response ' + status + ' ' + media)
    return {'compatible': not issues, 'issues': sorted(issues), 'checker': 'openapi-conservative-json-subset'}


def matrix(root, manifest):
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('schema_version=1 required')
    contracts = manifest.get('contracts')
    if not isinstance(contracts, list) or not contracts:
        raise ValueError('nonempty contracts required')
    root = Path(root).resolve(strict=True)
    rows, seen = [], set()
    hashes = {}
    snapshots = {}
    for item in contracts:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip()
                or item['id'] in seen or not all(isinstance(item.get(n), str) and item[n].strip() for n in ('provider', 'consumer'))):
            raise ValueError('unique contract IDs and explicit provider/consumer required')
        seen.add(item['id'])
        kind = item.get('kind')
        names = ('writer', 'reader') if kind == 'avro' else ('before', 'after') if kind == 'openapi' else None
        if names is None:
            raise ValueError('supported kinds: avro, openapi')
        schemas = []
        for field in names:
            name = item.get(field)
            if not isinstance(name,str):
                raise ValueError('schema paths must be strings')
            if name not in snapshots:
                snapshots[name] = read_file(root, name)
            data = snapshots[name]
            hashes[name] = digest(data)
            schemas.append(json.loads(data))
        expected = item.get('sha256')
        if not isinstance(expected, dict) or expected != {field: hashes[item[field]] for field in names}:
            raise ValueError('contract hashes required and must match selected files')
        try:
            checked = avro_compatible(*schemas) if kind == 'avro' else openapi_compatible(*schemas)
            row = {'status': 'compatible' if checked['compatible'] else 'incompatible', **checked}
        except Unknown as error:
            row = {'status': 'unknown', 'issues': [str(error)]}
        rows.append({'id': item['id'], 'provider': item['provider'], 'consumer': item['consumer'], **row})
    if any(read_file(root,name) != data for name,data in snapshots.items()):
        raise ValueError('contract changed during analysis; rerun on a pinned snapshot')
    return {'schema_version': 1, 'contracts': rows, 'source_sha256': hashes,
            'status': 'incompatible' if any(r['status'] == 'incompatible' for r in rows) else
                      'unknown' if any(r['status'] == 'unknown' for r in rows) else 'compatible',
            'runtime_consumer_tests': 'not_run', 'production_ready': False,
            'limitations': 'Static recorded consumer/provider schema compatibility only; '
                          'does not discover deployed consumers, run consumer tests or authorize deployment.'}


def pin_contracts(root, manifest):
    if not isinstance(manifest,dict) or not isinstance(manifest.get('contracts'),list):
        raise ValueError('contract manifest required')
    result = json.loads(json.dumps(manifest))
    for item in result['contracts']:
        if not isinstance(item,dict):
            raise ValueError('contract must be an object')
        names = ('writer','reader') if item.get('kind') == 'avro' else ('before','after')
        item['sha256'] = {field:digest(read_file(Path(root).resolve(strict=True),item.get(field))) for field in names}
    matrix(root,result)  # Validate shape and paths; incompatibility/UNKNOWN does not prevent pinning.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--pin', action='store_true')
    args = parser.parse_args()
    try:
        document = json.loads(args.manifest.read_text())
        result = pin_contracts(args.root,document) if args.pin else matrix(args.root,document)
    except (ValueError, OSError, TypeError, AttributeError, KeyError):
        parser.exit(2, 'ERROR: invalid contract manifest, schema or stale source hashes\n')
    print(json.dumps(result, indent=2))
    if not args.pin and result['status'] != 'compatible':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
