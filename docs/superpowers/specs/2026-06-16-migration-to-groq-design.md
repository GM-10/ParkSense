# Design: Migrating to Free API Tier (Groq)

## Overview
This design outlines the transition from paid OpenRouter/OpenAI dependencies to free-tier API services (Groq) to eliminate API costs while maintaining application functionality.

## Architecture Changes
1. **API Client:** Replace `ChatOpenAI` (OpenRouter) with a free-tier compatible client.
2. **Dependency Management:** Remove `openai` and `langchain-openai`. Add `langchain-groq`.
3. **Environment Configuration:** Deprecate `OPENROUTER_API_KEY` and implement `GROQ_API_KEY`.
4. **Validation:** Add an agent startup check to verify connectivity to the free endpoint.

## Components
- `requirements.txt`: Update to remove paid-service dependencies.
- `src/agent.py`: Refactor to use `ChatGroq`.
- `.env`: Update documentation/example for `GROQ_API_KEY`.

## Trade-offs
- **Pros:** Zero cost, high performance (Groq is faster than many paid alternatives).
- **Cons:** Requires a new free API key from Groq.

## Security
- `OPENROUTER_API_KEY` will be removed.
- `GROQ_API_KEY` will be managed exclusively via `.env`.
