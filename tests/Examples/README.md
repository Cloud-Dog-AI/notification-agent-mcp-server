# Test Message Examples

This directory contains test messages of varying complexity for use in T26 and other integration tests.

## Available Test Messages

### Test-Simple.md
- **Purpose**: Basic functionality testing
- **Length**: ~200 words
- **Complexity**: Low
- **Use Cases**: Quick tests, basic delivery validation

### Test-Brief-News.md / Test-Brief-News.txt
- **Purpose**: News-style brief content
- **Length**: ~1000 words
- **Complexity**: Medium
- **Use Cases**: Summarization tests, format conversion, multi-channel delivery
- **Content**: Daily Ukraine War Brief (example news content)

### Test-Large-Text.md
- **Purpose**: Large document testing
- **Length**: ~2000+ words
- **Complexity**: High
- **Use Cases**: Summarization, translation, long-form content processing, attachment testing
- **Content**: Academic-style article on LLMs and information dissemination

## Usage in Tests

Tests should select appropriate test messages based on their requirements:

- **Basic delivery tests**: Use `Test-Simple.md`
- **Format conversion tests**: Use `Test-Brief-News.md`
- **Summarization tests**: Use `Test-Large-Text.md`
- **Translation tests**: Use any message, specify target language
- **Multi-channel tests**: Use `Test-Brief-News.md` (good for Slack/Email)

## Naming Convention

- `Test-{Description}.md` - Markdown format
- `Test-{Description}.txt` - Plain text format

