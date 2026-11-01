"""Sequential agent-specific A/B campaign planning and source-safe export.

No provider call, code modification, autonomous rule rewrite or verified winner.
Each agent's paired benchmark must still receive its own explicit consent.
"""
from datetime import datetime, timezone
from agents import catalog

# Domain-specific prompts are identical for baseline and specialist.
# Cases deliberately test different responsibilities rather than overfitting a
# generic Java-review prompt across unrelated agent profiles.
SCENARIOS = {
    "java-architect": ("architecture", "Assess Java module boundaries, dependency direction, data ownership, migration and failure isolation."),
    "java-developer": ("fix-plan", "Identify Java correctness hazards and propose minimal version-compatible implementation changes with regression checks."),
    "java-reviewer": ("review", "Inspect Java concurrency, null-handling, resource lifecycle and exception propagation."),
    "java-testing": ("fix-plan", "Assess JUnit test coverage, determinism, isolation, boundary conditions and missing regression tests."),
    "cicd-engineer": ("architecture", "Inspect CI pipelines, release reproducibility, approvals, artifact provenance and rollback controls."),
    "docker-engineer": ("review", "Inspect Dockerfiles and Compose files for reproducible builds, privilege, secrets, resource limits and health checks."),
    "gitops-engineer": ("architecture", "Assess GitOps desired-state flow, drift detection, permissions and progressive deployment/rollback."),
    "kubernetes-engineer": ("review", "Inspect Kubernetes deployments, probes, service exposure, policy and scheduling resilience."),
    "platform-security-engineer": ("review", "Inspect supply-chain, workload identity, secret management, network boundaries and privilege."),
    "reliability-engineer": ("architecture", "Assess SLOs, backpressure, failure recovery, observability and incident response evidence."),
    "react-architect": ("architecture", "Assess React state boundaries, component ownership, dependency design and accessibility."),
    "react-developer": ("fix-plan", "Find React rendering and state-management defects; propose minimal fixes and test cases."),
    "react-reviewer": ("review", "Inspect React hooks, async race conditions, XSS defenses and accessibility."),
    "react-testing": ("fix-plan", "Assess React component and browser test coverage, isolation and reproducible regression cases."),
    "integration-reviewer": ("review", "Inspect integration contracts, timeouts, retries, idempotency and failure handling."),
    "security-reviewer": ("review", "Inspect authentication, authorization, input validation, injection and sensitive-data handling."),
    "spring-boot-engineer": ("fix-plan", "Assess Spring Boot configuration, dependency compatibility, auto-configuration and startup failures."),
    "spring-data-engineer": ("review", "Inspect JPA queries, transaction boundaries, N+1 risks, consistency and migration safety."),
    "spring-framework-expert": ("architecture", "Assess Spring lifecycle, dependency injection, transaction semantics and component boundaries."),
    "spring-reactive-engineer": ("review", "Inspect Reactor/WebFlux backpressure, blocking calls, context propagation and cancellation."),
    "spring-security-engineer": ("review", "Inspect Spring Security filter chains, authorization rules, OAuth2 and method security."),
    "spring-testing-engineer": ("fix-plan", "Assess Spring slice/integration tests, Testcontainers, transactional test isolation and coverage."),
}
MODE_ADVICE = {"review":"For every finding cite exact file:line, failure condition and a falsifiable regression check.",
               "architecture":"Tie every design observation to inspected code; distinguish verified coupling from hypotheses.",
               "fix-plan":"Provide a minimal evidence-backed patch plan and runnable regression-test descriptions, without claiming execution."}


def task_for_agent(agent, mode, base_task):
    if agent not in SCENARIOS or mode not in MODE_ADVICE:
        raise ValueError("Agent or benchmark mode not in trusted scenario catalog")
    _, focus = SCENARIOS[agent]
    return base_task + "\nDomain-specific assessment for " + agent + ": " + focus + " " + MODE_ADVICE[mode]


def candidate_rules(agent, comparison):
    """Suggest testable rules, never rewrite a profile or claim an improved result."""
    baseline = comparison["baseline_score"]
    challenger = comparison["daeloryn_score"]
    status = comparison["evaluation_status"]
    if status == "partial_or_incomplete":
        return ["Complete both benchmark arms before comparing. Preserve completed batches and avoid automatic retries."]
    if challenger >= baseline:
        return []
    focus = SCENARIOS[agent][1]
    return [
        "Candidate amendment for " + agent + ": Before concluding, use the approved source snapshot and cite precise, existing file:line references. If a relevant source is absent, label the issue unverified instead of inventing a location.",
        "Domain-focused review checklist: " + focus,
        "After manual review of the proposed rule diff, validate on a NEW held-out project and separately record true defects, false positives, regression results and costs. An increased citation score alone is not proof of superiority.",
    ]


def campaign_report(runs, comparisons, *, agents=None):
    """One step per catalogued specialist, in deterministic catalog order.

    No code paths or provider answers are exported; only sanitized observation
    scores, task descriptions, statuses and candidate rule amendments.
    """
    if agents is None:
        agents = [meta for meta, _ in catalog()]
    names = [meta["name"] for meta in agents]
    if len(names) != len(set(names)):
        raise ValueError("duplicate agent metadata")
    if set(names) != set(SCENARIOS):
        raise ValueError("scenario catalog must cover exactly the trusted agent catalog")
    by_agent = {}
    for run in runs:
        name = run.get("agent")
        if name in names and name not in by_agent:
            by_agent[name] = run
    by_comparison = {}
    for comparison in comparisons:
        name = comparison.get("agent")
        if name in names and name not in by_comparison:
            by_comparison[name] = comparison
    entries = []
    next_agent = None
    for index, meta in enumerate(agents, 1):
        name = meta["name"]
        latest = by_agent.get(name)
        evaluated = by_comparison.get(name)
        comparable = (evaluated is not None and evaluated.get("status") == "completed" and
                      evaluated.get("evaluation_status") not in ("partial_or_incomplete",))
        state = ("assessed_provisionally" if comparable else
                 "incomplete" if latest and latest.get("status") in ("running","stopping","partial","failed","stopped","interrupted") else
                 "needs_evaluation" if latest and latest.get("status") == "completed" else
                 "not_started")
        if next_agent is None and state != "assessed_provisionally":
            next_agent = name
        scenario_mode, focus = SCENARIOS[name]
        lead = evaluated["provisional_evidence_lead"] if comparable else "not_determined"
        recs = candidate_rules(name, evaluated) if comparable else []
        entries.append({
            "order": index, "agent": name, "scope": meta["scope"],
            "benchmark_mode": scenario_mode, "domain_scenario": focus,
            "state": state,
            "latest_run_id": latest["run_id"] if latest else None,
            "latest_run_status": latest["status"] if latest else None,
            "traceability_scores": ({"baseline": evaluated["baseline_score"], "daeloryn": evaluated["daeloryn_score"]}
                                     if comparable else None),
            "provisional_evidence_lead": lead,
            "verified_winner": None,
            "candidate_rule_improvements": recs,
        })
    completed = sum(row["state"] == "assessed_provisionally" for row in entries)
    weaker = sum(bool(row["candidate_rule_improvements"]) for row in entries)
    return {
        "schema_version": 1,
        "kind": "daeloryn-sequential-agent-campaign",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(entries), "provisionally_assessed": completed,
        "next_agent": next_agent,
        "weaker_traceability_agents": weaker,
        "entries": entries,
        "provider_calls_started": False,
        "rules_modified": False,
        "independently_verified_winners": 0,
        "warning": ("All 22 roles are planned sequentially with role-specific questions. "
                    "Start/approve each paired run separately; this report never launches provider calls. "
                    "Scores measure source citation traceability, not true bug-finding skill. "
                    "Candidate rule amendments are NOT automatically applied or declared successful. "
                    "Use blinded held-out validation and human evidence adjudication before a superiority claim."),
    }
