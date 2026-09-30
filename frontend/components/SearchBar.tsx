"use client";

import { useState } from "react";

interface SearchBarProps {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: SearchBarProps) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g. running shoes for rainy season, not white, under ₹5000"
        className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !query.trim()}
        className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
      >
        {loading ? "Searching…" : "Find"}
      </button>
    </form>
  );
}
