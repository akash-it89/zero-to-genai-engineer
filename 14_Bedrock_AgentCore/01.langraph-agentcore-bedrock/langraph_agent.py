import csv
import os
import re
from typing import List

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from bedrock_agentcore.runtime import BedrockAgentCoreApp

load_dotenv()

app = BedrockAgentCoreApp()


def load_faq_csv(path: str) -> List[Document]:
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row["question"].strip()
            a = row["answer"].strip()
            docs.append(Document(page_content=f"Q: {q}\nA: {a}"))
    return docs


# Instant at import — no Bedrock embed calls (avoids Titan throttling / cold-start crash)
FAQ_DOCS = load_faq_csv("./lauki_qna.csv")


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def keyword_search(query: str, k: int = 3) -> List[Document]:
    """Simple token-overlap retrieval — no embeddings, no quota burn."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return FAQ_DOCS[:k]

    scored: list[tuple[int, Document]] = []
    for doc in FAQ_DOCS:
        doc_tokens = _tokenize(doc.page_content)
        score = len(q_tokens & doc_tokens)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:k]]


def _format_results(results: List[Document], label: str = "FAQ Entry") -> str:
    if not results:
        return "No relevant FAQ entries found."
    context = "\n\n---\n\n".join(
        f"{label} {i + 1}:\n{doc.page_content}" for i, doc in enumerate(results)
    )
    return f"Found {len(results)} relevant FAQ entries:\n\n{context}"


@tool
def search_faq(query: str) -> str:
    """Search the FAQ knowledge base for relevant information.
    Use this tool when the user asks questions about products, services, or policies.

    Args:
        query: The search query to find relevant FAQ entries

    Returns:
        Relevant FAQ entries that might answer the question
    """
    return _format_results(keyword_search(query, k=3))


@tool
def search_detailed_faq(query: str, num_results: int = 5) -> str:
    """Search the FAQ knowledge base with more results for complex queries.
    Use this when the initial search doesn't provide enough information.

    Args:
        query: The search query
        num_results: Number of results to retrieve (default: 5)

    Returns:
        More comprehensive FAQ entries
    """
    return _format_results(keyword_search(query, k=num_results))


@tool
def reformulate_query(original_query: str, focus_aspect: str) -> str:
    """Reformulate the query to focus on a specific aspect.
    Use this when you need to search for a different angle of the question.

    Args:
        original_query: The original user question
        focus_aspect: The specific aspect to focus on (e.g., "pricing", "activation", "troubleshooting")

    Returns:
        A reformulated query focused on the specified aspect
    """
    reformulated = f"{focus_aspect} {original_query}"
    results = keyword_search(reformulated, k=3)
    if not results:
        return f"No results found for aspect: {focus_aspect}"
    return _format_results(results, label="Entry")


tools = [search_faq, search_detailed_faq, reformulate_query]


def build_model():
    """Prefer OpenAI when key is present (Bedrock on-demand daily quotas are easy to burn)."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("Using ChatOpenAI (OPENAI_API_KEY set)")
        return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=openai_key)

    print("Using ChatBedrockConverse (no OPENAI_API_KEY)")
    return ChatBedrockConverse(
        model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        temperature=0,
    )


model = build_model()

system_prompt = """You are a helpful FAQ assistant with access to a knowledge base.

Your goal is to answer user questions accurately using the available tools.

Guidelines:
1. Start by using the search_faq tool to find relevant information
2. If the initial search doesn't provide enough info, use search_detailed_faq for more results
3. If the query is complex, use reformulate_query to search different aspects
4. Synthesize information from multiple tool calls if needed
5. Always provide a clear, concise answer based on the retrieved information
6. If you cannot find relevant information, clearly state that

Think step-by-step and use tools strategically to provide the best answer."""

agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
)


@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation in AgentCore runtime"""
    print("Received payload:", payload)
    print("Context:", context)

    query = payload.get("prompt", "No prompt found in input")
    result = agent.invoke({"messages": [("human", query)]})
    print("Result:", result)
    return {"result": result["messages"][-1].content}


if __name__ == "__main__":
    app.run()
