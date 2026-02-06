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



