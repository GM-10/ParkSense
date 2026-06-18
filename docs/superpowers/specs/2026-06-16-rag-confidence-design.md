# Design: Formal RAG Confidence Scoring

## Overview
This design implements formal confidence scoring for the RAG agent's responses. This satisfies the project requirement to mitigate hallucination risks by making retrieval uncertainty explicit.

## Architecture Changes
1. **Retrieval Modification (`src/agent.py`):** Update the retriever to fetch document similarity scores (ChromaDB supports this via `similarity_search_with_score`).
2. **Confidence Calculation:** Compute an aggregated confidence score based on the similarity scores of the top retrieved documents.
3. **Prompt Update:** Update the LangChain prompt to accept the `{confidence_score}` and include it in the AI Briefing (Section 0).

## Components
- `src/agent.py`: 
  - Update `retriever` to `similarity_search_with_score`.
  - Update the RAG chain to pass the computed score into the `briefing_template`.

## Security
- None. This is a logic enhancement to existing RAG chain.
