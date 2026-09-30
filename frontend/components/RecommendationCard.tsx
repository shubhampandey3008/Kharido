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

interface RecommendationCardProps {
  recommendation: RecommendationData;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const { product, reasoning, key_evidence } = recommendation;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold leading-snug">{product.title}</h2>
          {product.brand && (
            <p className="mt-0.5 text-sm text-gray-500">{product.brand}</p>
          )}
        </div>
        {product.price_inr && (
          <span className="shrink-0 rounded-full bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700">
            ₹{product.price_inr.toLocaleString("en-IN")}
          </span>
        )}
      </div>

      {product.rating && (
        <p className="mt-2 text-sm text-gray-500">
          {product.rating}/5{product.rating_count ? ` · ${product.rating_count.toLocaleString()} reviews` : ""}
        </p>
      )}

      <p className="mt-4 text-sm leading-relaxed text-gray-700">{reasoning}</p>

      {key_evidence.length > 0 && (
        <ul className="mt-3 space-y-1">
          {key_evidence.map((point, i) => (
            <li key={i} className="flex gap-2 text-sm text-gray-600">
              <span className="mt-0.5 shrink-0 text-indigo-500">✓</span>
              {point}
            </li>
          ))}
        </ul>
      )}

      {product.product_url && (
        <a
          href={product.product_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:underline"
        >
          View product →
        </a>
      )}
    </div>
  );
}
