"""Tests for the query_understanding node stub."""

from __future__ import annotations

from kharido.nodes.query_understanding import query_understanding_node


def test_returns_parsed_query_key():
    state = {"raw_query": "running shoes for rainy season, not white"}
    result = query_understanding_node(state)
    assert "parsed_query" in result


def test_parsed_query_has_category():
    state = {"raw_query": "wireless earbuds with noise cancellation"}
    result = query_understanding_node(state)
    parsed = result["parsed_query"]
    assert parsed.category != ""


def test_preserves_raw_query():
    raw = "laptop bag under 3000 rupees"
    state = {"raw_query": raw}
    result = query_understanding_node(state)
    # Stub sets raw_query on ParsedQuery
    assert result["parsed_query"].raw_query == raw
