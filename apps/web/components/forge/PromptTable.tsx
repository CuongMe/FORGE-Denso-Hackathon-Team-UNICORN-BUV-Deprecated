export type PromptItem = {
  label: string;
  description: string;
  question: string;
};

type PromptTableProps = {
  prompts: readonly PromptItem[];
  disabled: boolean;
  onSelect: (question: string) => void;
};

const accentColors = ["red", "orange", "yellow", "green", "blue", "indigo"];

export function PromptTable({ prompts, disabled, onSelect }: PromptTableProps) {
  return (
    <section className="forge-prompt-section" aria-labelledby="prompt-table-heading">
      <div className="forge-section-heading"><div><p className="forge-eyebrow">SAMPLE PROMPTS</p><p id="prompt-table-heading" className="forge-prompt-helper">Choose a question to test FORGE</p></div></div>
      <div className="forge-prompt-table" role="table" aria-label="Sample prompts">
        <div className="forge-prompt-header" role="row"><span role="columnheader">#</span><span role="columnheader">SAMPLE PROMPT</span><span role="columnheader">BEHAVIOR</span></div>
        <div className="forge-prompt-scroll">{prompts.map((prompt, index) => <button key={prompt.label} type="button" className="forge-prompt-row" onClick={() => onSelect(prompt.question)} disabled={disabled} role="row"><span className={"forge-prompt-number " + accentColors[index % accentColors.length]} role="cell">{String(index + 1).padStart(2, "0")}</span><span className="forge-prompt-question" role="cell">{prompt.question}</span><span className="forge-prompt-behavior" role="cell">{prompt.label.toUpperCase()}</span></button>)}</div>
        <div className="forge-prompt-scrollbar" aria-hidden="true"><span /></div>
      </div>
    </section>
  );
}
