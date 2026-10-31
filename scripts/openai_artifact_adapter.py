"""Opt-in OpenAI Responses adapter returning data artifacts, never executing tools.

Fixed HTTPS endpoint, no redirects, no automatic retries, no model-chosen commands.
Source transmission requires explicit operator opt-in. Live API behavior is not
established by mocked transport tests. API credentials are never included in artifacts.
"""
import json
import os
import urllib.error
import urllib.request

ENDPOINT = 'https://api.openai.com/v1/responses'
MAX_RESPONSE = 4 * 1024 * 1024
SCHEMA = {'type': 'object', 'properties': {'artifact_json': {'type': 'string'}},
          'required': ['artifact_json'], 'additionalProperties': False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ProviderOutcomeUnknown(RuntimeError):
    """Do not automatically retry: a paid request may already have completed."""


def transport(payload, key, timeout):
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                     headers={'Authorization': 'Bearer ' + key,
                                              'Content-Type': 'application/json'}, method='POST')
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as error:
        raise ProviderOutcomeUnknown(f'provider HTTP status {error.code}; review before retry') from None
    except (OSError, TimeoutError) as error:
        raise ProviderOutcomeUnknown('provider transport outcome unknown; do not automatically retry') from None
    if len(raw) > MAX_RESPONSE:
        raise ProviderOutcomeUnknown('oversized provider response; no automatic retry')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise ProviderOutcomeUnknown('invalid provider response; no automatic retry') from None


def invoke(context, model, *, enabled=False, timeout=60, max_output_tokens=8192,
           send=transport):
    if not enabled:
        raise ValueError('provider disabled; explicit --execute-provider required to transmit source')
    if not isinstance(model, str) or not model.strip() or len(model) > 128:
        raise ValueError('explicit model ID required')
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ValueError('timeout must be 1..120 seconds')
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768:
        raise ValueError('explicit bounded output token limit required')
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('OPENAI_API_KEY required; no credentials loaded from source files')
    payload = {'model': model, 'instructions': context['instructions'],
               'input': context['input'], 'store': False, 'tools': [],
               'max_output_tokens': max_output_tokens,
               'text': {'format': {'type': 'json_schema', 'name': 'engineering_artifact',
                                   'schema': SCHEMA, 'strict': True}}}
    response = send(payload, key, timeout)
    if not isinstance(response, dict) or response.get('status') != 'completed':
        raise ProviderOutcomeUnknown('provider did not complete; inspect outcome before retry')
    parts = []
    output = response.get('output')
    if not isinstance(output, list):
        raise ValueError('invalid provider output collection')
    for item in output:
        if not isinstance(item, dict):
            raise ValueError('invalid provider output item')
        if item.get('type') != 'message':
            continue  # e.g. model reasoning metadata is not an engineering artifact
        content = item.get('content')
        if not isinstance(content, list):
            raise ValueError('invalid message content')
        for part in content:
            if not isinstance(part, dict) or part.get('type') != 'output_text' or not isinstance(part.get('text'), str):
                raise ValueError('refusal or unexpected provider message; no usable artifact')
            parts.append(part['text'])
    try:
        envelope = json.loads(''.join(parts))
        if not isinstance(envelope, dict) or set(envelope) != {'artifact_json'} or not isinstance(envelope['artifact_json'], str):
            raise ValueError('invalid artifact envelope')
        artifact = json.loads(envelope['artifact_json'])
    except (ValueError, TypeError) as error:
        raise ValueError('provider returned no valid engineering artifact') from None
    if not isinstance(artifact, dict):
        raise ValueError('artifact must be an object')
    usage = response.get('usage')
    usage = usage if isinstance(usage, dict) else {}
    counts = {name: value for name in ('input_tokens', 'output_tokens')
              if type(value := usage.get(name)) is int and value >= 0}
    return {'artifact': artifact, 'usage': counts,
            'actual_model': response.get('model') if isinstance(response.get('model'), str) else None,
            'response_id': response.get('id') if isinstance(response.get('id'), str) else None}
