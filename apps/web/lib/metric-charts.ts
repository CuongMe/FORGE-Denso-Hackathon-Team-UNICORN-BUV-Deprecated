import type { QueryMetrics } from './types';

export type MetricBucket = {
  end: string;
  requests: number;
  p50: number;
  p95: number;
};

function percentile(values: number[], fraction: number) {
  return values.length ? values[Math.max(0, Math.ceil(values.length * fraction) - 1)] : 0;
}

export function buildMetricBuckets(recent: QueryMetrics['recent']): MetricBucket[] {
  const ordered = [...recent].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const buckets: MetricBucket[] = [];

  for (let index = 0; index < ordered.length; index += 10) {
    const requests = ordered.slice(index, index + 10);
    buckets.push({
      end: requests[requests.length - 1].created_at,
      requests: requests.length,
      p50: percentile(requests.map((request) => request.latency_ms), 0.5),
      p95: percentile(requests.map((request) => request.latency_ms), 0.95),
    });
  }
  return buckets;
}
