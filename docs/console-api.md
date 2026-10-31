# Local read-only Console API

The Python standard-library API exposes only `GET /api/health`,
`GET /api/agents`, and `GET /api/benchmarks`. It reads validated
repository agent metadata and an optional operator-supplied directory of
benchmark trial JSON records. No provider execution, prompt submission,
filesystem browsing, credentials, write routes or model access is exposed.

## Start locally

Terminal A:

```bash
python3 scripts/console_api.py --port 8765
# optional: --records-dir /private/benchmark-trials
```

Terminal B:

```bash
cd web
npm install
npm run dev
npm run build
```

Vite proxies `/api` to the loopback-only Python API. **Do not expose
the development server or API to untrusted networks.** No authentication
is implemented: production requires authentication, authorization,
TLS, CSRF/CORS policy review, resource limits and an explicit API threat model.

The API deliberately returns a summary rather than untrusted raw benchmark
transcripts. Matrix trial flags are operator-provided; they are not independent
attestation by this server. If the API is unavailable, the UI shows
illustrative agent profiles and no benchmark score. The chat remains
in-memory and does not invoke any model.

## Test

```bash
python3 -m unittest discover -s tests -p 'test_console_api.py'
```
