# Migration to Groq API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition the traffic intelligence agent from OpenRouter/OpenAI to the Groq API to eliminate costs and maintain performance.

**Architecture:** Replace the LangChain `ChatOpenAI` client with `ChatGroq`, update dependencies, and reconfigure environment variables.

**Tech Stack:** LangChain, Groq API.

---

### Task 1: Prepare Environment and Dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `.env`

- [ ] **Step 1: Update requirements**
Replace `openai` and `langchain-openai` with `langchain-groq`.
Run: `pip uninstall openai langchain-openai -y && pip install langchain-groq`

- [ ] **Step 2: Update `.env`**
Add `GROQ_API_KEY=` and remove `OPENROUTER_API_KEY=`.

### Task 2: Refactor Agent to Use Groq

**Files:**
- Modify: `src/agent.py`

- [ ] **Step 1: Replace imports**
Remove `from langchain_openai import ChatOpenAI` and add `from langchain_groq import ChatGroq`.

- [ ] **Step 2: Update LLM initialization**
Refactor the agent setup to use `ChatGroq` with a free-tier model (e.g., `llama-3.1-8b-instant`).

```python
# Before
llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    openai_api_base=OPENROUTER_BASE_URL,
    ...
)

# After
llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    ...
)
```

- [ ] **Step 3: Update connection check**
Ensure the agent checks for `GROQ_API_KEY` instead of `OPENROUTER_API_KEY`.

### Task 3: Verification and Cleanup

**Files:**
- Modify: `src/agent.py` (if needed for final cleanup)
- Modify: `README.md`

- [ ] **Step 1: Run agent to verify**
Run the agent startup test in `src/agent.py` to ensure it initializes successfully with Groq.

- [ ] **Step 2: Update Documentation**
Update `README.md` to reflect the change from OpenRouter to Groq.

- [ ] **Step 3: Final Commit**
Commit all changes to git.
