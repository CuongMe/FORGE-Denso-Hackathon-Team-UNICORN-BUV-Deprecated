import { useRef } from 'react';
import { useTranslations } from 'next-intl';

export type PromptItem = {
  label: string;
  description: string;
  question: string;
  expectedAnswer: string;
};

type PromptTableProps = {
  prompts: readonly PromptItem[];
  disabled: boolean;
  onSelect: (question: string) => void;
};

const accentColors = ["red", "orange", "yellow", "green", "blue", "indigo"];

export function PromptTable({ prompts, disabled, onSelect }: PromptTableProps) {
  const t = useTranslations();
  const promptList = useRef<HTMLDivElement>(null);
  return (
    <section className="forge-prompt-section" aria-labelledby="prompt-table-heading">
      <div className="forge-section-heading"><div><p className="forge-eyebrow">{t('prompt.heading')}</p><p id="prompt-table-heading" className="forge-prompt-helper">{t('prompt.helper')}</p></div></div>
      <div className="forge-prompt-table" role="table" aria-label={t('prompt.table')}>
        <div className="forge-prompt-header" role="row"><span role="columnheader">#</span><span role="columnheader">{t('prompt.column')}</span><span role="columnheader">{t('prompt.behavior')}</span></div>
        <div className="forge-prompt-scroll" ref={promptList}>{prompts.map((prompt, index) => <button key={prompt.label} type="button" className="forge-prompt-row" onClick={() => onSelect(prompt.question)} disabled={disabled} role="row"><span className={"forge-prompt-number " + accentColors[index % accentColors.length]} role="cell">{String(index + 1).padStart(2, "0")}</span><span className="forge-prompt-question" role="cell"><span>{prompt.question}</span><small>{prompt.label}</small></span><span className="forge-prompt-answer" role="cell">{prompt.expectedAnswer}</span></button>)}</div>
        <button type="button" className="forge-prompt-scroll-down" onClick={() => promptList.current?.scrollBy({ top: promptList.current.clientHeight * 0.8, behavior: 'smooth' })} aria-label={t('prompt.scrollDown')}>↓ {t('prompt.scrollDown')}</button>
        <div className="forge-prompt-scrollbar" aria-hidden="true"><span /></div>
      </div>
    </section>
  );
}
