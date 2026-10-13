"""Tests for the query_understanding node (LLM chain mocked — no network)."""

from __future__ import annotations

import pytest

from kharido.models import ParsedQuery, PriceRange
from kharido.nodes import query_understanding
from kharido.nodes.query_understanding import query_understanding_node


class _FakeChain:
    """Stands in for `prompt | llm.with_structured_output(ParsedQuery)`."""

    def __init__(self, parsed: ParsedQuery):
        self.parsed = parsed
        self.inputs: list[dict] = []

    def invoke(self, inputs: dict) -> ParsedQuery:
        self.inputs.append(inputs)
        return self.parsed


@pytest.fixture
def fake_chain(monkeypatch):
    chain = _FakeChain(
        ParsedQuery(
            category="running_shoes",
            price_range=PriceRange(max_inr=5000),
            must_avoid=["white_color"],
            use_case_context="rainy season",
            raw_query="llm paraphrased this",
        )
    )
    monkeypatch.setattr(query_understanding, "_build_chain", lambda: chain)
    return chain


def test_returns_parsed_query(fake_chain):
    raw = "running shoes for rainy season, not white, under 5000 rupees"
    result = query_understanding_node({"raw_query": raw})

    assert fake_chain.inputs == [{"raw_query": raw}]
    parsed = result["parsed_query"]
    assert parsed.category == "running_shoes"
    assert parsed.price_range.max_inr == 5000
    assert parsed.must_avoid == ["white_color"]


def test_preserves_raw_query(fake_chain):
    raw = "laptop bag under 3000 rupees"
    result = query_understanding_node({"raw_query": raw})
    # Node overwrites whatever the LLM put in raw_query
    assert result["parsed_query"].raw_query == raw
