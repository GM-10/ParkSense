import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from typing import Dict, Any, List

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()

# Constants
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.1-8b-instant"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DB_DIR = "chroma_db_parkguard"

# Global state for the RAG system
vector_stores = {}
llm = None
chain = None

def create_natural_language_string(row, type="junction"):
    """Converts a CSV row into a high-density descriptive sentence for embedding."""
    if type == "junction":
        return (f"TACTICAL RECORD: Junction {row['junction_name']}. "
                f"IMPACT: {row['mean_severity']} (Risk: {row.get('risk_tier', 'N/A')}). "
                f"PATTERNS: Peaks at {row['peak_hour']}:00 on {row['dominant_day_of_week']}. "
                f"VEHICLE: {row['dominant_vehicle']}. "
                f"SITUATIONAL: Managed by {row['police_station']}.")
    elif type == "station":
        return (f"SITUATIONAL RECORD: Police Station {row['police_station']}. "
                f"BURDEN: {row['total_violations']} violations. "
                f"KEY AREA: {row['top_junction']}. "
                f"VEHICLE: {row['dominant_vehicle']}. "
                f"SEVERITY: {row['mean_severity']}.")
    elif type == "hotspot":
        return (f"HOTSPOT RECORD: Locality {row['locality_name']}. "
                f"IMPACT: Congestion score {row['congestion_score']} (Risk: {row['risk_tier']}). "
                f"VOLUME: {row['violation_count']} violations.")
    return str(row.to_dict())

def initialize_rag():
    """Builds and loads ChromaDB collections for junctions, stations, and hotspots."""
    global vector_stores, llm, chain

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # Define collections and their source files
    collections_config = {
        "junctions": {"file": "data/junction_summary.csv", "type": "junction"},
        "stations": {"file": "data/police_station_summary.csv", "type": "station"},
        "hotspots": {"file": "data/hotspot_clusters.csv", "type": "hotspot"}
    }

    for col_name, config in collections_config.items():
        try:
            df = pd.read_csv(config["file"])
            texts = df.apply(lambda r: create_natural_language_string(r, config["type"]), axis=1).tolist()
            metadatas = df.to_dict('records')

            vector_stores[col_name] = Chroma.from_texts(
                texts=texts,
                embedding=embeddings,
                metadatas=metadatas,
                persist_directory=f"{DB_DIR}/{col_name}",
                collection_metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"Error initializing collection {col_name}: {e}")

    # Initialize LLM
    try:
        llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name=MODEL_NAME, temperature=0.1, max_tokens=1024)
    except Exception as e:
        print(f"LLM Initialization failed: {e}")

    # Define Tactical System Prompt
    prompt = ChatPromptTemplate.from_template("""You are a tactical police intelligence assistant for the Bengaluru Traffic Police (BTP).
You provide operational briefings based on retrieved data.

RETRIEVED DATA:
{context}

USER QUERY: {question}

STRICT OPERATIONAL GUIDELINES:
1. Be concise and operational. Use bullet points. No academic fluff.
2. Always cite the specific Junction, Station, or Hotspot you are referring to.
3. Language:
   - If the user asks in English, respond in English.
   - If the user asks in Kannada, respond in Kannada.
4. Integrity: Never hallucinate. If the retrieved data does not contain the answer, state "Insufficient data to provide a tactical recommendation."
5. Formatting: Use clear headings like RISK ASSESSMENT, PEAK WINDOW, and RESOURCE NEED.
""")

    # Custom retrieval logic to query all collections
    def hybrid_retrieve(inputs):
        question = inputs["question"]
        all_docs = []
        all_scores = []

        for name, store in vector_stores.items():
            docs_with_scores = store.similarity_search_with_score(question, k=2)
            all_docs.extend([doc for doc, score in docs_with_scores])
            all_scores.extend(score for _, score in docs_with_scores)

        # Return context and the best similarity score for confidence mapping
        # Note: Chroma distance is usually L2 or Cosine. For Cosine, lower is better.
        best_score = min(all_scores) if all_scores else 1.0
        context = "\n\n".join([doc.page_content for doc in all_docs])

        return {"context": context, "best_score": best_score, "question": question}

    chain = (
        RunnableLambda(hybrid_retrieve)
        | {
            "context": lambda x: x["context"],
            "question": lambda x: x["question"],
            "best_score": lambda x: x["best_score"]
          }
        | prompt
        | llm
        | StrOutputParser()
    )

    return True

def ask_agent(question: str) -> Dict[str, Any]:
    """Queries the RAG system and returns answer, confidence, and sources."""
    global chain, vector_stores

    if chain is None:
        return {"answer": "Agent not initialized.", "confidence": "N/A", "sources": []}

    try:
        # To get the score, we run the retrieval part separately first
        # because the chain consumes the score in the prompt (implicitly or explicitly)
        # We'll re-run retrieval logic to get the confidence score for the final output.

        # Step 1: Manual retrieval to get score
        all_docs = []
        all_scores = []
        for name, store in vector_stores.items():
            docs_with_scores = store.similarity_search_with_score(question, k=2)
            all_docs.extend([doc for doc, score in docs_with_scores])
            all_scores.extend(score for _, score in docs_with_scores)

        best_score = min(all_scores) if all_scores else 1.0

        # Step 2: Generate answer via chain
        answer = chain.invoke({"question": question})

        # Confidence Mapping (Assuming Cosine distance where 0 is identical, 1 is orthogonal)
        # Logic: score < 0.4 is high similarity (good), score > 0.7 is low.
        if best_score < 0.4:
            confidence = "✅ High confidence"
        elif best_score < 0.7:
            confidence = "⚠️ Moderate confidence"
        else:
            confidence = "❌ Low confidence — verify with field data"

        sources = [doc.metadata.get('junction_name') or doc.metadata.get('police_station') or doc.metadata.get('locality_name')
                   for doc in all_docs if doc.metadata]

        return {
            "answer": answer,
            "confidence": confidence,
            "sources": list(set(sources))
        }

    except Exception as e:
        return {"answer": f"Error processing query: {str(e)}", "confidence": "Error", "sources": []}
