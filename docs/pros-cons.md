# Pros and cons

## Pros

- Install only the Java, Spring, React, Platform or Shared specialists required.
- Reuse the same canonical definitions across four supported coding tools.
- Work directly in an existing repository without adopting a new software-delivery method.
- Use domain-specific review checklists and evidence requirements.
- Validate catalog/install behavior in CI and score recorded benchmark findings separately.

## Cons and trade-offs

- No orchestration, project planning, sprint management or automatic agent handoffs.
- Adapter generation does not guarantee identical behavior in different hosts.
- Human review remains essential for security, correctness and production changes.
- Agent prompts are not access-control enforcement; host permission settings matter.
- Benchmarks are preliminary, narrow and susceptible to answer leakage.
- Maintaining version-specific expertise and runtime integrations requires continual testing.

## Decision guide

Choose this toolkit for targeted coding, architecture or review tasks in repositories you already manage. Choose a workflow methodology such as BMAD when coordination, requirements tracking and role-based planning are the main problem. Combine them when both needs exist.

The framework is **experimental**, not certified for production and not validated as superior to other agent collections.
