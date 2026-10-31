"""Content-free local spans; optional caller-supplied exporter.

Raw prompts, paths, model output, errors and arbitrary attributes are never logged.
Sink failures do not change a business outcome. Not a tamper-proof audit store.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
import uuid

ALLOWED = {'input_sha256', 'artifact_sha256', 'input_tokens', 'output_tokens',
           'cached_tokens', 'attempt', 'exit_code'}


class Telemetry:
    def __init__(self, path=None, exporter=None):
        self.path = Path(path) if path is not None else None
        self.exporter = exporter
        self.dropped = 0

    @contextmanager
    def span(self, trace_id, stage, attributes=None):
        if stage not in ('review', 'implement', 'verify', 'handoff', 'context'):
            raise ValueError('unknown span stage')
        if not isinstance(trace_id, str) or len(trace_id) != 32 or any(c not in '0123456789abcdef' for c in trace_id):
            raise ValueError('trace_id must be a 32-character lowercase hex id')
        attributes = attributes if attributes is not None else {}
        start = time.time_ns()
        status = 'completed'
        try:
            yield attributes
        except BaseException:
            status = 'failed'
            raise
        finally:
            attrs = {}
            for key, value in attributes.items():
                if key not in ALLOWED:
                    continue
                if key.endswith('_sha256'):
                    if isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value):
                        attrs[key] = value
                elif type(value) is int and (value >= 0 or key == 'exit_code'):
                    attrs[key] = value
            record = {'trace_id': trace_id, 'span_id': uuid.uuid4().hex[:16],
                      'name': stage, 'started_at_ns': start, 'ended_at_ns': time.time_ns(),
                      'status': status, 'attributes': attrs}
            try:
                if self.path is not None:
                    if self.path.resolve() != self.path.absolute():
                        raise ValueError('telemetry symlink path rejected')
                    fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT
                                 | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                    with os.fdopen(fd, 'a', encoding='utf-8') as out:
                        out.write(json.dumps(record, separators=(',', ':')) + '\n')
                if self.exporter is not None:
                    # Export only the sanitized record, never the caller's attributes.
                    self.exporter(record)
            except Exception:
                self.dropped += 1


def otel_exporter(tracer):
    """Bridge to an operator-configured OpenTelemetry SDK tracer; no exporter setup here."""
    def export(record):
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, set_span_in_context
        context = set_span_in_context(NonRecordingSpan(SpanContext(
            trace_id=int(record['trace_id'], 16), span_id=int(record['span_id'], 16),
            is_remote=False, trace_flags=TraceFlags(1))))
        span = tracer.start_span('daeloryn.' + record['name'], context=context,
                                 start_time=record['started_at_ns'],
                                 attributes={**record['attributes'], 'outcome': record['status']})
        span.end(end_time=record['ended_at_ns'])
    return export
