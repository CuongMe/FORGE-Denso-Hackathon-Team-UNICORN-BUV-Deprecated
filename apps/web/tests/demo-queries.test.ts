import { describe, expect, it } from "vitest";

import { demoQueries } from "@/lib/demo-queries";
import { demoAnswers } from "@/lib/demo-answers";
import { flatMessages } from "@/lib/i18n";
import corpus from "@/data/denso-corpus.json";
import { rankDemoChunks } from "@/lib/vercel-demo";

describe("90-second demo script", () => {
  it("contains a structured lookup, cross-language query, and honest refusal query", () => {
    expect(demoQueries).toHaveLength(14);
    expect(demoQueries.slice(0, 6).map((item) => item.label)).toEqual([
      "Structured lookup",
      "Cross-language",
      "Honest Demo",
      "Out-of-range response",
      "Defect escalation",
      "Maintenance limits",
    ]);
    expect(demoQueries[1].description).toContain("Vietnamese");
    expect(demoQueries[2].question).toContain("football");
  });

  it("includes grounded Japanese and Vietnamese prompts with same-language answers", () => {
    const nativePrompts = demoQueries.filter((prompt) => prompt.nativeLanguage);
    expect(nativePrompts.filter((prompt) => prompt.nativeLanguage === "ja")).toHaveLength(4);
    expect(nativePrompts.filter((prompt) => prompt.nativeLanguage === "vi")).toHaveLength(4);
    expect(nativePrompts.map((prompt) => rankDemoChunks(prompt.question)[0]?.chunk.doc_id)).toEqual([
      "JA-BIZ-0001",
      "JA-BIZ-0004",
      "JA-BIZ-0006",
      "JA-BIZ-0009",
      "JA-BIZ-0001",
      "JA-BIZ-0004",
      "JA-BIZ-0006",
      "JA-BIZ-0009",
    ]);

    for (const prompt of nativePrompts) {
      expect(prompt.expectedAnswer).toBeTruthy();
      expect(prompt.question).toMatch(prompt.nativeLanguage === "ja" ? /[\u3040-\u30ff\u4e00-\u9faf]/u : /[à-ỹđĐ]/iu);
      expect(prompt.expectedAnswer).toMatch(prompt.nativeLanguage === "ja" ? /[\u3040-\u30ff\u4e00-\u9faf]/u : /[à-ỹđĐ]/iu);
    }
  });

  it("ships extra prebuilt answers with evidence from the prepared corpus", () => {
    expect(demoAnswers).toHaveLength(3);

    for (const sample of demoAnswers) {
      for (const language of ["en", "ja", "vi"] as const) {
        expect(flatMessages[language][sample.questionKey]).toBeTruthy();
        expect(flatMessages[language][sample.answerKey]).toBeTruthy();
        expect(flatMessages[language][sample.sourcesKey]).toBeTruthy();
      }

      const evidence = corpus.chunks
        .filter((chunk) => sample.evidenceChunkIds.some((chunkId) => chunkId === chunk.chunk_id))
        .map((chunk) => chunk.content.toLocaleLowerCase())
        .join(" ");
      expect(evidence).not.toBe("");
      for (const fact of sample.evidenceFacts) {
        expect(evidence).toContain(fact.toLocaleLowerCase());
      }
    }
  });

  it("retrieves the cited source first for each new sample question", () => {
    for (const sample of demoAnswers) {
      const question = flatMessages.en[sample.questionKey]!;
      const [bestMatch] = rankDemoChunks(question);
      expect(bestMatch?.chunk.doc_id).toBe(sample.evidenceChunkIds[0].split(":")[0]);
    }
  });
});
