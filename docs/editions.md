# Community and Enterprise editions

This project follows an **Open Core plan**. The Enterprise offering is planned, not yet a released or certified product.

| | Community | Enterprise (planned) |
| --- | --- | --- |
| Distribution | Public repository | Separately distributed private product |
| License | MIT (existing source files) | Commercial agreement for separately authored Enterprise code |
| Agents | Current Java, Spring, React, Platform and Shared definitions | Community agents plus organization-specific packs |
| Workflows | DAG planning, local handoffs, experimental security components | Managed orchestration with protected server-side authorization |
| Identity | Experimental offline JWT verification | SSO/OIDC onboarding, enforced tenant policies and RBAC |
| Operations | Developer-managed local tools | Managed credentials, immutable audit storage, support and deployment controls |
| Availability | Developer preview | Not available yet |

## License boundaries

- The published Community code remains available under MIT, including any orchestration or approval components already distributed in this repository.
- A separate commercial license may apply to **new, separately distributed Enterprise code**. Merely renaming or moving MIT files does not cancel their MIT grants.
- Enterprise components that incorporate MIT code must retain the MIT copyright and permission notice for those portions.
- Contributions and third-party dependencies require individual license and intellectual-property review. This document does not change the MIT LICENSE file.
- Product names and branding should be assessed separately from copyright licensing; do not imply trademark protection without an actual legal basis.

## Enterprise MVP backlog

1. Server-side run API with a protected trust boundary and isolated worker identity.
2. Persistent tenant boundaries, role permissions and audited approval policies.
3. Provider adapters with explicit opt-in, secret broker, network and tool allowlists.
4. Immutable or independently secured audit records, operation IDs and replay prevention.
5. Cancellation, idempotency, retries, crash recovery and budget limits.
6. E2E security tests proving that unapproved and cross-tenant actions never run.
7. Commercial packaging, operational runbooks, deployment architecture and support terms.

**Security gate:** Do not sell the current local OIDC/SQLite CLI as production authorization or connect it to customer infrastructure without independent security review and verified E2E tests.

## Repository layout

Keep the current Community repository public and MIT-licensed. Develop the Enterprise service, deployment charts, private test fixtures and contractual material in a **separate private repository**. Do not commit customer data, secrets, credentials or private commercial terms to this repository.
