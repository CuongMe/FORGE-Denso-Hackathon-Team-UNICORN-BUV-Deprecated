import { GlobeIcon, SearchIcon, ShieldIcon } from "./ForgeIcons";

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

export function PromptTable({ prompts, disabled, onSelect }: PromptTableProps) {
  return (
    <section className="forge-prompt-section" aria-labelledby="prompt-table-heading">
      <div className="forge-section-heading">
        <div>
          <p className="forge-eyebrow">START WITH A PROOF POINT</p>
          <h2 id="prompt-table-heading">Three questions, three system behaviors</h2>
        </div>
        <p>Select a prompt to run the live path.</p>
      </div>
      <div className="forge-prompt-table" role="table" aria-label="Demo questions">
        <div className="forge-prompt-header" role="row">
          <span role="columnheader">CASE</span>
          <span role="columnheader">BEHAVIOR</span>
          <span role="columnheader">QUESTION</span>
          <span aria-hidden="true" />
        </div>
        <div className="forge-prompt-scroll">
          {prompts.map((prompt, index) => {
            const Icon = index === 1 ? GlobeIcon : index === 2 ? ShieldIcon : SearchIcon;
            return (
              <button
                key={prompt.label}
                type="button"
                className="forge-prompt-row"
                onClick={() => onSelect(prompt.question)}
                disabled={disabled}
                role="row"
              >
                <span className="forge-prompt-number" role="cell">0{index + 1}</span>
                <span className="forge-prompt-behavior" role="cell"><Icon className="forge-prompt-icon" />{prompt.label}</span>
                <span className="forge-prompt-question" role="cell"><strong>{prompt.description}</strong><small>{prompt.question}</small></span>
                <span className="forge-prompt-arrow" aria-hidden="true">&rarr;</span>
              </button>
            );
          })}
        </div>
        <div className="forge-prompt-scrollbar" aria-hidden="true"><span /></div>
      </div>
    </section>
  );
}
