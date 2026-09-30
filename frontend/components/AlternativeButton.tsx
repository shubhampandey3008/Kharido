interface AlternativeButtonProps {
  onClick: () => void;
  loading: boolean;
}

export function AlternativeButton({ onClick, loading }: AlternativeButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
    >
      {loading ? "Finding alternative…" : "Show me an alternative"}
    </button>
  );
}
