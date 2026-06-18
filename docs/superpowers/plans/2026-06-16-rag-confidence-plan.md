# RAG Confidence Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a formal confidence scoring mechanism based on vector retrieval similarity.

**Architecture:** Modify the retrieval pipeline to calculate a score from ChromaDB results and inject this score into the agent's prompt.

**Tech Stack:** `langchain`, `chromadb`.

---

### Task 1: Refactor Retrieval Pipeline

**Files:**
- Modify: `src/agent.py`

- [ ] **Step 1: Update retriever**
Modify `build_vector_store` and `get_agent` to use `similarity_search_with_score` instead of `as_retriever`.

```python
# Change in get_agent:
# Instead of retriever = vectorstore.as_retriever(...)
# Use:
results = vectorstore.similarity_search_with_score(question, k=5)
context = "\n\n".join([doc.page_content for doc, score in results])
avg_score = sum([score for doc, score in results]) / len(results)
confidence_score = max(0, min(100, (1 - avg_score) * 100)) # Simple mapping
```

- [ ] **Step 2: Update prompt**
Pass `{confidence_score}` to the `briefing_template`.

- [ ] **Step 3: Commit**
```bash
git add src/agent.py
git commit -m "feat: implement formal RAG confidence scoring"
```
