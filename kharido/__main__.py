"""CLI entry point — run the graph against a test query via `python -m kharido`."""

from __future__ import annotations

import uuid

from kharido.config import configure_tracing, get_settings
from kharido.graph import build_graph


def main() -> None:
    configure_tracing()
    settings = get_settings()

    graph = build_graph()
    query = "running shoes for rainy season, not white, under 5000 rupees"
    thread_id = f"cli-{uuid.uuid4().hex[:8]}"

    print(f"[kharido] query: {query!r}")
    print(f"[kharido] thread_id: {thread_id}")

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"raw_query": query, "thread_id": thread_id}, config=config)

    error = result.get("error")
    if error:
        print(f"\n[error] {error}")
        return

    rec = result.get("recommendation")
    if rec:
        print(f"\nTop pick : {rec.product.title}")
        print(f"Score    : {rec.composite_score:.2f}")
        print(f"Reasoning: {rec.reasoning}")
    else:
        print("\nNo recommendation produced yet (pipeline stubs active).")


if __name__ == "__main__":
    main()
