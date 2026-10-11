import { describe, expect, it } from 'vitest';
import { buildMetricBuckets } from '@/lib/metric-charts';
import type { QueryMetrics } from '@/lib/types';

const request = (index: number, values: Partial<QueryMetrics['recent'][number]> = {}): QueryMetrics['recent'][number] => ({
  id: index,
  created_at: new Date(Date.UTC(2026, 9, 11, 0, index)).toISOString(),
  latency_ms: index * 100,
  succeeded: 1,
  abstained: 0,
  citations: 1,
  prompt_tokens: 100,
  completion_tokens: 20,
  total_tokens: 120,
  estimated_cost_usd: null,
  ...values,
});

describe('metric chart buckets', () => {
  it('orders requests and calculates latency percentiles in groups of ten', () => {
    const rows = Array.from({ length: 11 }, (_, index) => request(index));
    const buckets = buildMetricBuckets(rows.reverse());

    expect(buckets).toHaveLength(2);
    expect(buckets[0]).toMatchObject({ requests: 10, p50: 400, p95: 900 });
    expect(buckets[1]).toMatchObject({ requests: 1, p50: 1000, p95: 1000 });
  });
});
