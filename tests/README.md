# Test Suite

This directory contains tests for the Notification Agent MCP Server.

## Running Tests

### All Tests
```bash
make test
```

### Specific Test Files
```bash
# API tests (requires running server)
pytest tests/test_api_server.py -v

# Unit tests
pytest tests/test_config.py tests/test_database.py -v
```

## Test Categories

### Unit Tests
- `test_config.py` - Configuration system tests
- `test_database.py` - Database and repository tests
- `test_job_manager.py` - Job manager and state machine tests
- `test_adapters.py` - Channel adapter tests

### API Tests
- `test_api_server.py` - REST API endpoint tests

### Integration Tests
- `test_background_workers.py` - Background worker tests
- `test_reliability.py` - Rate limiting and circuit breaker tests

## Prerequisites

### For API Tests
Start the API server before running tests:
```bash
python start_api_server.py --env <ENV_FILE>
```

### For All Tests
Install test dependencies:
```bash
pip install -r requirements.txt
```

## Test Configuration

Tests use a separate test database to avoid conflicts with development data.

Default test configuration:
- Database: `sqlite3://./database/test.db`
- API URL: `<API_BASE_URL>`
- API Key: `<API_KEY>`

## Writing Tests

Follow these guidelines:
1. Use pytest fixtures for setup/teardown
2. Test both success and failure cases
3. Clean up test data after tests
4. Use descriptive test names
5. Add docstrings to test classes and methods

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch

See `.github/workflows/test.yml` for CI configuration.

