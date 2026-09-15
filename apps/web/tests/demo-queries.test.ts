import { describe, expect, it } from "vitest";

import { demoQueries } from "@/lib/demo-queries";

describe("90-second demo script", () => {
  it("contains a structured lookup, cross-language query, and honest refusal query", () => {
    expect(demoQueries).toHaveLength(3);
    expect(demoQueries.map((item) => item.label)).toEqual([
      "Structured lookup",
      "Cross-language",
      "Honest Demo",
    ]);
    expect(demoQueries[1].description).toContain("Vietnamese");
    expect(demoQueries[2].question).toContain("football");
  });
});
