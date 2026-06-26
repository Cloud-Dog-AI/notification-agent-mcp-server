# TEST SCRIPT REQUIREMENTS

## Core Principles

Ensure you have fully developed this test to be to the same level of quality, detail, where you confirm all functionality within the scope (both positive and negative tests), to a forensic level, picking test cases that exercise against the use cases provided.

## Validation Requirements

Validate. Ensure it is to the full level of detail, quality, confirming all outputs format, structure, contents, language, file type as appropriate. Ensure all output is clearly available for me to watch, log test activity and all outputs so they can be recovered/reviewed. Ensure you 100% check the test run for ZERO warnings and ZERO errors. Ensure tests use 100% API and src/ code and do not stub, hack, fallback any functionality - the test is to test 100% final functionality/performance/capability. Ensure you try all CRUD operations where appropriate. Your tests should exercise all different external subsystem types where possible.

## Configuration & Environment

- Any test MUST hard fail if it does not have a `--env <env-file>` setting
- There are to be NO hard coded test values
- Use the application environment/config routines to get test values: `os.environ → env files → tests/config.yaml → tests/default.yaml`
- **SPECIFICALLY**: Write tests to use the API_SERVER code in all cases unless it cannot be done for a reason
- **DO NOT** code around using the REAL API_SERVER in ANY INSTANCE

## Test Data

Test DATA should be as meaningful and representative as possible, aligned to the use cases, with fields filled with test content. You will ensure you run the tests one at a time, not batching into a script - you will ensure that all outputs are visible to the terminal prompt so that it can be watched/monitored as it runs. You will closely monitor for:
- Stuck tests that timeout
- No response
- Any errors or warnings
- Any code failings

Interrupt and resolve immediately.

## Dependency Management (CRITICAL)

**ALL tests MUST include dependency validation and cleanup:**

### Setup Phase (Step 0):
1. **Validate API connectivity** - Check server is responding
2. **Check required resources exist** - Channels, groups, etc.
3. **Create missing dependencies** - Via API only
4. **Track all created resources** - Users, prompts, groups, etc. in lists for cleanup

Example:
```python
# Track created resources
created_users = []
created_prompts = []
created_groups = []

# Validate API
health_response = await client.get(f"{api_base_url}/health")
assert health_response.status_code == 200

# Check/create dependencies
channels_response = await client.get(f"{api_base_url}/channels")
assert email_channel exists
```

### Test Execution:
- As resources are created, add them to tracking lists
- Example: `created_users.append({"id": user_id, "email": email})`

### Cleanup Phase (Final Step):
1. **Delete all created users** - Via API DELETE endpoints
2. **Delete all created prompts** - Via API DELETE endpoints  
3. **Delete all created groups** - Via API DELETE endpoints
4. **Verify cleanup completed** - Log what was removed

Example:
```python
# Cleanup
for user in created_users:
    await client.delete(f"{api_base_url}/users/{user['id']}")
    print(f"✅ Deleted user: {user['email']}")

for prompt_id in created_prompts:
    await client.delete(f"{api_base_url}/prompts/{prompt_id}")
    print(f"✅ Deleted prompt: ID={prompt_id}")
```

**WHY THIS IS CRITICAL:**
- Tests must not leave orphaned data in the system
- Tests must be repeatable without manual cleanup
- Tests must validate their dependencies before running
- Cleanup ensures test isolation and prevents test pollution

## Output & Reporting

At the end you will provide a summary table in markdown of all these tests, one row per test case, with summary of the test, with a URI/URL link to the test inputs (including parameters), test output(s) and files, and the test log(s) for review and inspection.

Display to the terminal/console output for review.

Update the TESTS.md with your status/progress.

## Critical Reminders

- **NO DEBUG HACKS** - Remove any debug logging added to fix issues
- **READ YOUR INSTRUCTIONS** - Follow these requirements 100%
- **100% REVIEW** - Confirm you are doing as instructed
- **NO LYING** - Do not claim tests pass when they don't