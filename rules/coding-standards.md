# Development Guidelines

Pick the cheapest sub-agent that fits the task — see Sub-Agent Selection. Reference commands with their full plugin prefix (`/nyt-flow:push`, not `/push`). Ticket workflows live in the `plan-ticket` and `create-jira-ticket` skills.

## Git Workflow

- **Never push or merge directly to `main` or `dev`.** Every change goes worktree → commit → push → PR → merge.
- The ticket name prefixes everything: branches and worktrees as `<TICKET>-<description>` (`SPGM-2992-fix-renewal-handler`), PR titles as `<TICKET> <description>` (`SPGM-3358 Set subject field on published events`), and `[PROJECT-1234]` in the commit message. Never prefix with `worktree-` or anything else. Read the ticket from the current branch name — never ask for it.
- Only add relevant files — never `git add -A` or `git add .`
- PR body follows `.github/PULL_REQUEST_TEMPLATE.md` if the repo has one
- Every commit must compile, pass tests, and include tests for new functionality
- `nyt-flow:push` and `nyt-flow:ship` handle commit and PR format

### Worktree safety

1. `pwd` to confirm the directory
2. `git rev-parse --git-dir` — output must contain `/worktrees/`
3. Never modify files outside the current worktree
4. STOP and ask if git says you're not in a worktree

## Behavior

- Be a critical thinking partner, not a yes-person — challenge assumptions, question unclear requirements, give honest trade-offs, never default to agreement
- Working through a list, present only the next item as each is resolved — don't re-list every time
- Verify a potential issue before reporting it: check infra, configs, monitors, and surrounding code. Either confirm the impact or say it's a non-issue — don't present unverified concerns as problems.

## Process

- Understand existing patterns → test first → implement minimal code → verify (linters and all tests, including integration) → commit
- Choose the boring, obvious solution — avoid premature abstractions and clever tricks
- Never disable or skip tests to make them pass — fix them
- Present options when there are multiple valid approaches (e.g. naming choices)
- Verify changes persisted and the code compiles before moving on
- Remove unused imports after refactoring
- Consult the repo's `ai_ref` directory for how the code is meant to work

## Security

- No secrets in code — use Vault
- Watch for XSS, SQL injection, command injection

## When Stuck

Maximum 3 attempts per issue, then STOP.

1. Document what failed — specific error messages and why
2. Research alternatives — find 2–3 similar implementations
3. Question fundamentals — simpler approach? different abstraction?
4. Try a different angle

## Code Style

- **Never** use "utils" or "helpers" in file names — name for the concern: `validation.go`, `formatting.go`, `parsing.go`
- Comments are for "why", not "what". One line beats a paragraph; cut anything the code already makes obvious.
- Add Javadoc to public methods you write or modify — never retroactively to untouched ones
- Tests must call actual production code, not simulate it
- Table-driven tests are mandatory for Go
- Address IDE warnings promptly

## Java Patterns

- Controllers: thin — delegate to services, handle request/response mapping only
- Services: business logic and orchestration
- Mappers: pure transformation, throw on invalid data
- Break a method doing multiple distinct operations into private helpers with descriptive names
- Test naming: `methodName_scenario_expectedResult`
- When updating tests, ensure mocks match actual production behaviour
- Test helpers: hardcode values that never vary; add a parameter only when a test passes something different. Don't create a helper called once — inline it.
- Prefer `@MockitoBean` over the deprecated `@MockBean` (removed in Spring Boot 4)
- Match the repo's existing logging style. Levels: `debug` flow, `info` operations, `warn` recoverable, `error` failures

## Reading Dependencies and Downstream Systems

Before claiming how a library or downstream service behaves, read its code — don't infer. Pass this directive to subagents.

- Check `~/repos/` for a local clone first, then `~/.gradle/caches` or `~/.m2/repository`
- Pin to the version the app uses (`build.gradle` / `pom.xml` / `go.mod` / `package.json`) — `HEAD` may not match
- For services, check the integration boundary too: terraform, event filters, Spring wiring. A handler that exists may never be reached.
- If you can't reach the right code, say so — don't fill the gap with inference

```bash
find ~/.gradle/caches -name "library-name*.jar" 2>/dev/null
unzip -l /path/to/library.jar | grep ClassName
cd /tmp && unzip -o /path/to/library.jar 'com/path/to/ClassName.class' && javap -p -c -constants 'com/path/to/ClassName.class'
```

## Sub-Agent Selection

Use tiered command-runners for ALL terminal command execution, starting with the cheapest tier that fits. Escalate only when a lower tier returns an escalation report.

- **nyt-command:easy** (haiku) — simple tests, linters, formatters, git status, builds, CLI tools
- **nyt-command:medium** (sonnet) — debugging failures, multi-step operations, complex output interpretation
- **nyt-command:hard** (opus) — architecture decisions, complex debugging, ambiguous errors, security-sensitive ops

Language-specific agents: `golang` (nyt-golang) for Go, `typescript-pro` (nyt-typescript) for TypeScript/JavaScript.

For other sub-agents, pick the cheapest model that fits:

- **haiku** — file search, grep/glob, formatting, boilerplate
- **sonnet** — multi-file implementation, refactoring, code review, clear-repro debugging
- **opus** — architecture decisions, complex debugging, ambiguous requirements, security review
