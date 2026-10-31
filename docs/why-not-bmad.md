# Why not BMAD?

This repository is intentionally **independent from BMAD**. The goal is a small, reusable library of technology-specific engineering agents that can be installed directly into developer tools. It does not aim to replace BMAD Method.

| Dimension | Enterprise Engineering Agents | BMAD Method |
| --- | --- | --- |
| Primary focus | Implementation and technical review specialists | Structured discovery, planning and software delivery workflows |
| Setup | Pick modules and install agent definitions | Follow BMAD installation and method conventions |
| Workflow orchestration | Not included | A core part of its approach |
| Requirements and story lifecycle | Bring your own process | Formalized workflows and artifacts |
| Technology-specific agents | Built-in for Java, Spring, React and Platform | Customizable or extendable |
| Best fit | Existing repos, focused engineering tasks, code reviews | Complex greenfield initiatives, multi-role planning and traceability |

### Reasons for independence

1. A Java reviewer should be reusable in any project without forcing planning ceremonies.
2. Installation can be scoped to a single tool and technology module.
3. Review/test quality can be evaluated separately from process effectiveness.
4. The project remains portable across Codex, Claude Code, Copilot and Gemini CLI without relying on a BMAD runtime.

### When BMAD is a better choice

BMAD may be preferable for product discovery, stakeholder alignment, requirements traceability, complex architecture planning and multi-step delivery coordination. You can use both: BMAD for planning and these agents for implementation/reviews. This project does not claim better output quality than BMAD without controlled comparative evaluations.

BMAD and third-party tools retain their respective licenses and trademarks. This repository does not copy their agent instructions.
