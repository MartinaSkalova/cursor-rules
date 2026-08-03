# Coding Standards and Patterns

## Workflow Preferences

- Present options when there are multiple valid approaches (e.g., naming choices)
- Prefer simplification over justifying redundancy
- Keep explanations concise and actionable
- Verify changes actually persisted before moving on
- Do not use git worktrees; work directly in the main repository
- Verify code compiles after making changes before moving on
- Study existing code patterns before implementing new features
- Check for and remove unused imports after refactoring
- Consult `ai_ref` directory for documentation about how code should work
- always add Javadoc comments to public methods
- Always check external library behavior before making assumptions. Don't ask—just inspect the code. Check the Gradle cache to understand external library behavior:
```bash
find ~/.gradle/caches -name "library-name*.jar" 2>/dev/null
unzip -l /path/to/library.jar | grep ClassName
cd /tmp && unzip -o /path/to/library.jar 'com/path/to/ClassName.class' && javap -p -c -constants 'com/path/to/ClassName.class'
```

## Logging

- Always use structured KV logging with `kv()` helper
- Use appropriate log levels: `debug` for flow, `info` for operations, `warn` for recoverable issues, `error` for failures

## Code Organization

- Controllers: thin, delegate to services, handle request/response mapping
- Services: business logic, orchestration, exception translation
- Mappers: pure transformation logic, throw exceptions for invalid data
- When a method does multiple distinct operations, break it into private helper methods with descriptive names
- Always extract duplicate code into reusable methods

## Testing

- Mock external dependencies at appropriate boundaries
- Test both success and error paths
- Use descriptive test names: `methodName_scenario_expectedResult`
- When updating tests, ensure mocks match actual production code behavior


## API Design

- Use consistent error response format across all endpoints
- Return appropriate HTTP status codes for each error scenario
- Truncate sensitive data (tokens) in logs and error messages

## Defensive Coding

- Always check objects exist before accessing nested properties
- Don't assume values are non-null; validate at boundaries
- Address IDE warnings promptly rather than ignoring them

## Git Commit & PR Process

### Branches

- Branch name format: `<TICKET>-<short-description>` (e.g., `SPGM-2992-start-itunes-notification-pipe`)
- Always create a new branch from `main`

### Commits

- Commit message format: `<TICKET> <imperative summary>` on the first line, followed by a blank line and a short body explaining *why* the change was made
- Do not include unrelated files (e.g., local images, scratch files)

### Pull Requests

- Title format: `<TICKET> <imperative summary>` (matches the commit)
- Body must follow the repo's PR template (e.g., `.github/PULL_REQUEST_TEMPLATE.md`):
  - **Ticket**: link to the Jira ticket, derived from the branch name
  - **Why this change?**: one or two sentences explaining the problem and the fix
  - **Benefits**: what is enabled when this merges
  - **Possible Drawbacks**: note any risks, or state "None expected" with brief justification
- Keep the description concise; only include significant changes
- Check all checklist boxes in the template
- Provide as pastable markdown in a code block when requested

### General

- Fetch the ticket number from the current branch name rather than asking
- Push with `-u origin HEAD` to set upstream tracking
- Use `gh pr create` to open the PR from the command line
