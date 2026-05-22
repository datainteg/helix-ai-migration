# LLM Router

## Purpose

The LLM Router provides a single backend abstraction for model/provider routing, structured output requests, provider health, retries, usage logging, and agent-wise model mapping.

Supported providers:

- OpenAI / ChatGPT
- Google Gemini
- Anthropic Claude
- DeepSeek
- OpenRouter
- Custom OpenAI-compatible API
- Local model URL
- Future Ollama / vLLM / LM Studio

## Router Contract

The router should normalize:

- Provider name
- Base URL
- Model
- System prompt
- Messages
- Structured output schema
- Temperature
- Max tokens
- Timeout
- Retry policy
- Token usage
- Latency
- Error mapping

## Routing Modes

- Default model for all agents
- Agent-wise model mapping
- Future fallback chain per agent or project

## Security

Provider API keys must be encrypted before storage and masked after save. Router logs must not include raw keys, raw auth headers, or unredacted secrets.

## Observability

Track provider, model, agent type, prompt version, input tokens, output tokens, latency, status, retry count, and error code in LLM usage logs.

