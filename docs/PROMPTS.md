---
template-id: T-PRM
template-version: 1.0
applies-to: docs/PROMPTS.md
registry: service
required: must-have
when-applicable: ""
template-last-updated: 2026-06-12
template-owner: platform-standards

project: notification-agent-mcp-server
doc-last-updated: 2026-06-18
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: 90d
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# Prompt Management Documentation
**Version:** 1.0 • 2025-11-26

## Overview
The Prompt Management system allows dynamic selection and customization of LLM prompts based on keywords, user preferences, group settings, and channel requirements.

## Key Features

### 1. Prompt Storage
- Database-backed prompt repository
- Version control and history
- Priority-based selection

### 2. Prompt Selection
- Keyword matching
- User/group preference matching
- Channel-specific prompts
- Fallback to default prompts

### 3. Prompt Customization
- Variable substitution
- Language-specific prompts
- Format-specific instructions
- Channel-specific constraints

## Main Components

### Prompt Manager (`src/core/prompts/prompt_manager.py`)
- Prompt CRUD operations
- Selection logic
- Priority resolution
- Template rendering

### Prompt Repository (`src/database/repositories.py`)
- Database storage
- Query operations
- Version management

## Prompt Selection Flow

```
Message received
  ↓
Extract keywords from content
  ↓
Get user/group preferences
  ↓
Get channel requirements
  ↓
Query prompts by:
  - Keywords (highest priority)
  - User/group preferences
  - Channel type
  - Default fallback
  ↓
Select highest priority matching prompt
  ↓
Customize with variables and instructions
  ↓
Pass to LLM formatter
```

## Prompt Structure

### Database Schema
- `id`: Unique identifier
- `name`: Prompt name/identifier
- `description`: Human-readable description
- `content`: Prompt template content
- `keywords`: Associated keywords (JSON array)
- `priority`: Selection priority (higher = preferred)
- `channel_type`: Channel-specific (optional)
- `language`: Language-specific (optional)
- `format`: Format-specific (optional)
- `enabled`: Active status

### Prompt Template Variables
- `{{content}}`: Original message content
- `{{subject}}`: Message subject
- `{{user_name}}`: User name
- `{{user_language}}`: User language preference
- `{{channel_type}}`: Target channel type
- `{{max_length}}`: Maximum content length
- `{{format_style}}`: Desired output format

## Usage Examples

### Create Prompt via API
```bash
curl -X POST <API_BASE_URL>/api/v1/prompts \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "urgent_notification",
    "description": "Urgent notification prompt",
    "content": "You are formatting an urgent notification. Be concise and clear.",
    "keywords": ["urgent", "important"],
    "priority": 100
  }'
```

### Prompt Selection Example
1. Message contains keyword "urgent"
2. System finds prompt with keyword "urgent" (priority 100)
3. System finds default prompt (priority 0)
4. Selects "urgent_notification" prompt (higher priority)

## Configuration

See `docs/PARAMETERS.md` for all configuration options.

Key settings:
- `prompts.enabled`: Enable prompt management
- `prompts.default_prompt`: Default prompt name
- `prompts.keyword_matching`: Enable keyword-based selection

## Integration

### LLM Formatter
The LLM Formatter (`src/core/formatters/llm_formatter.py`) uses the Prompt Manager to:
1. Select appropriate prompt
2. Customize with variables
3. Add channel/user-specific instructions
4. Format message content

### User/Group Preferences
- User keywords trigger keyword-based prompt selection
- Group keywords apply to all group members
- Language preferences can match language-specific prompts

## Best Practices

1. **Priority Management**: Use higher priorities for more specific prompts
2. **Keyword Selection**: Use specific, non-overlapping keywords
3. **Fallback**: Always have a default prompt (priority 0)
4. **Testing**: Test prompt selection with various message types
5. **Versioning**: Keep prompt history for rollback capability
