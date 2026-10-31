"""Real Apache Avro checks and conservative directional HTTP schema contracts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from service_compatibility import avro_compatible, openapi_compatible, matrix, pin_contracts, Unknown
from verify_implementation import digest


def record(fields):
    return {'type': 'record', 'name': 'Order', 'namespace': 'example', 'fields': fields}


def api(request=None, response=None):
    operation = {'responses': {'200': {'description':'ok', 'content': {
        'application/json': {'schema': response or {'type':'object', 'properties':{
            'id':{'type':'string'}}, 'required':['id'], 'additionalProperties':False}}}}}}
    if request is not None:
        operation['requestBody'] = {'required':False, 'content':{'application/json':{'schema':request}}}
    return {'openapi':'3.0.3','info':{'title':'example','version':'1'},'paths':{'/orders':{'post':operation}}}


class AvroCompatibilityTests(unittest.TestCase):
    def test_numeric_promotion_is_directional(self):
        self.assertTrue(avro_compatible('int','long')['compatible'])
        self.assertFalse(avro_compatible('long','int')['compatible'])

    def test_reader_added_required_field_needs_default(self):
        writer = record([{'name':'id','type':'string'}])
        reader = record([{'name':'id','type':'string'}, {'name':'amount','type':'long'}])
        self.assertFalse(avro_compatible(writer,reader)['compatible'])
        reader['fields'][1]['default'] = 0
        self.assertTrue(avro_compatible(writer,reader)['compatible'])

    def test_invalid_default_and_logical_types_are_not_green(self):
        reader = record([{'name':'id','type':'string','default':99}])
        with self.assertRaises(Unknown):
            avro_compatible(record([]),reader)
        with self.assertRaises(Unknown):
            avro_compatible({'type':'long','logicalType':'timestamp-millis'},'long')

    def test_union_and_namespaced_record_aliases_use_native_checker(self):
        self.assertFalse(avro_compatible(['null','string'],'string')['compatible'])
        self.assertTrue(avro_compatible('string',['null','string'])['compatible'])
        writer=record([{'name':'id','type':'string'}])
        reader=copy.deepcopy(writer)
        reader['name']='Renamed'; reader['aliases']=['example.Order']
        self.assertTrue(avro_compatible(writer,reader)['compatible'])

    def test_enum_symbol_removal_and_recursive_records(self):
        writer={'type':'enum','name':'State','symbols':['OPEN','DONE']}
        reader={'type':'enum','name':'State','symbols':['OPEN']}
        self.assertFalse(avro_compatible(writer,reader)['compatible'])
        node={'type':'record','name':'Node','fields':[{'name':'next','type':['null','Node'],'default':None}]}
        self.assertTrue(avro_compatible(node,node)['compatible'])


class HttpCompatibilityTests(unittest.TestCase):
    def test_unchanged_contract_is_compatible(self):
        value=api()
        self.assertTrue(openapi_compatible(value,value)['compatible'])

    def test_response_required_field_removed_breaks_consumer(self):
        old=api(); new=api(response={'type':'object','properties':{},'additionalProperties':False})
        self.assertFalse(openapi_compatible(old,new)['compatible'])

    def test_optional_response_field_breaks_closed_reader_but_not_open_reader(self):
        new=api(response={'type':'object','properties':{'id':{'type':'string'},'extra':{'type':'string'}},
                          'required':['id'],'additionalProperties':False})
        old=api()
        self.assertFalse(openapi_compatible(old,new)['compatible'])
        old['paths']['/orders']['post']['responses']['200']['content']['application/json']['schema']['additionalProperties']=True
        self.assertTrue(openapi_compatible(old,new)['compatible'])

    def test_new_required_request_field_and_body_break_old_clients(self):
        schema={'type':'object','properties':{'id':{'type':'string'}},'required':['id'],'additionalProperties':False}
        old=api(request=schema); new=copy.deepcopy(old)
        target=new['paths']['/orders']['post']['requestBody']['content']['application/json']['schema']
        target['properties']['amount']={'type':'integer'}; target['required'].append('amount')
        self.assertFalse(openapi_compatible(old,new)['compatible'])
        new=copy.deepcopy(old); new['paths']['/orders']['post']['requestBody']['required']=True
        self.assertFalse(openapi_compatible(old,new)['compatible'])

    def test_request_enum_can_widen_response_enum_cannot_widen(self):
        old=api(request={'type':'string','enum':['A']},response={'type':'string','enum':['A']})
        new=api(request={'type':'string','enum':['A','B']},response={'type':'string','enum':['A']})
        self.assertTrue(openapi_compatible(old,new)['compatible'])
        new['paths']['/orders']['post']['responses']['200']['content']['application/json']['schema']['enum'].append('B')
        self.assertFalse(openapi_compatible(old,new)['compatible'])

    def test_removed_operation_and_new_unrecognized_response_status(self):
        old=api(); new=copy.deepcopy(old)
        new['paths']['/orders']={}
        self.assertFalse(openapi_compatible(old,new)['compatible'])
        new=copy.deepcopy(old)
        new['paths']['/orders']['post']['responses']['201']=new['paths']['/orders']['post']['responses'].pop('200')
        self.assertFalse(openapi_compatible(old,new)['compatible'])

    def test_local_refs_resolve_external_recursive_and_complex_schemas_are_unknown(self):
        old=api(response={'$ref':'#/components/schemas/Receipt'})
        old['components']={'schemas':{'Receipt':{'type':'string'}}}
        self.assertTrue(openapi_compatible(old,old)['compatible'])
        for schema in ({'$ref':'https://outside.invalid/schema'}, {'type':'string','pattern':'x'},
                       {'type':'string','enum':[1]}, {'oneOf':[{'type':'string'}]}):
            with self.subTest(schema=schema), self.assertRaises(Unknown):
                openapi_compatible(api(response=schema),api(response=schema))
        recursive=api(response={'$ref':'#/components/schemas/Node'})
        recursive['components']={'schemas':{'Node':{'type':'object','properties':{'next':{'$ref':'#/components/schemas/Node'}}}}}
        with self.assertRaises(Unknown):
            openapi_compatible(recursive,recursive)

    def test_security_changes_not_claimed_compatible(self):
        old=api(); new=api()
        new['security']=[{'oauth':['write']}]
        with self.assertRaises(Unknown):
            openapi_compatible(old,new)


class MatrixTests(unittest.TestCase):
    def test_explicit_consumer_matrix_hashes_and_no_deployment_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            files={'writer.avsc':json.dumps('int').encode(),'reader.avsc':json.dumps('long').encode()}
            for name,data in files.items(): (root/name).write_bytes(data)
            manifest={'schema_version':1,'contracts':[{'id':'order-event','provider':'orders','consumer':'billing',
                'kind':'avro','writer':'writer.avsc','reader':'reader.avsc',
                'sha256':{'writer':digest(files['writer.avsc']),'reader':digest(files['reader.avsc'])}}]}
            unpinned=copy.deepcopy(manifest)
            del unpinned['contracts'][0]['sha256']
            with self.assertRaises(ValueError):
                matrix(root,unpinned)
            self.assertEqual(manifest,pin_contracts(root,unpinned))
            result=matrix(root,manifest)
            self.assertEqual('compatible',result['status'])
            self.assertFalse(result['production_ready'])
            self.assertEqual('not_run',result['runtime_consumer_tests'])
            (root/'writer.avsc').write_text('"string"')
            with self.assertRaises(ValueError): matrix(root,manifest)

    def test_unknown_never_silently_passes_and_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=json.dumps(api(response={'type':'string','format':'uuid'})).encode()
            (root/'api.json').write_bytes(data)
            entry={'id':'http','provider':'orders','consumer':'web','kind':'openapi','before':'api.json','after':'api.json',
                   'sha256':{'before':digest(data),'after':digest(data)}}
            self.assertEqual('unknown',matrix(root,{'schema_version':1,'contracts':[entry]})['status'])
            with self.assertRaises(ValueError): matrix(root,{'schema_version':1,'contracts':[entry,entry]})


if __name__ == '__main__':
    unittest.main()
