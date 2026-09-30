"use client";

import { useState } from "react";
import { SearchBar } from "@/components/SearchBar";
import { RecommendationCard } from "@/components/RecommendationCard";
import { AlternativeButton } from "@/components/AlternativeButton";

interface Product {
  product_id: string;
  title: string;
  brand: string;
  price_inr: number | null;
  rating: number | null;
  rating_count: number | null;
  image_url: string;
  product_url: string;
  key_specs: Record<string, string>;
}

interface RecommendationData {
  product: Product;
  composite_score: number;
  reasoning: string;
  key_evidence: string[];
  criteria_scores: Record<string, number>;
}

interface SearchResponse {
  thread_id: string;
  recommendation: RecommendationData | null;
  has_alternative: boolean;
  error: string | null;
}

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [altLoading, setAltLoading] = useState(false);

  async function handleSearch(query: string) {
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, user_id: "default" }),
      });
      const data: SearchResponse = await res.json();
      setResult(data);
    } catch (err) {
      setResult({
        thread_id: "",
        recommendation: null,
        has_alternative: false,
        error: "Failed to connect to the server. Is the API running?",
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleAlternative() {
    if (!result?.thread_id) return;
    setAltLoading(true);

    try {
      const res = await fetch(`/api/search/${result.thread_id}/alternative`);
      const data = await res.json();
      setResult((prev) =>
        prev
          ? {
              ...prev,
              recommendation: data.recommendation ?? prev.recommendation,
              has_alternative: false,
              error: data.error ?? null,
            }
          : null
      );
    } catch (err) {
      console.error("Failed to fetch alternative:", err);
    } finally {
      setAltLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Kharido</h1>
        <p className="mt-1 text-gray-500">Tell me what you want. I'll find the best one.</p>
      </div>

      <SearchBar onSearch={handleSearch} loading={loading} />

      {result?.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {result.error}
        </div>
      )}

      {result?.recommendation && (
        <div className="space-y-4">
          <RecommendationCard recommendation={result.recommendation} />
          {result.has_alternative && (
            <AlternativeButton onClick={handleAlternative} loading={altLoading} />
          )}
        </div>
      )}
    </div>
  );
}
