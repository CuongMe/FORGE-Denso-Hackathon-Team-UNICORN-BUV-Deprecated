'use client';

import Image from 'next/image';
import type { ReactNode } from 'react';
import { useTranslations } from 'next-intl';
import type { Language } from '@/lib/i18n';

import type { HealthResponse } from '@/lib/types';

import { JapanFlagIcon, TableIcon, UkFlagIcon, VietnamFlagIcon } from './ForgeIcons';

export type ForgeView = 'ask' | 'documents' | 'metrics' | 'evaluations';

type ForgeShellProps = {
  activeView: ForgeView;
  onViewChange: (view: ForgeView) => void;
  health: HealthResponse | null;
  connectionError: string | null;
  rail: ReactNode;
  children: ReactNode;
};

const navItems: Array<{ id: ForgeView; label: string; icon?: typeof TableIcon }> = [
  { id: 'ask', label: 'nav.ask' },
  { id: 'documents', label: 'nav.documents', icon: TableIcon },
  { id: 'metrics', label: 'nav.metrics' },
  { id: 'evaluations', label: 'nav.evaluations' },
];

const languageOptions = [
  { id: 'en', label: 'language.en', Flag: UkFlagIcon },
  { id: 'ja', label: 'language.ja', Flag: JapanFlagIcon },
  { id: 'vi', label: 'language.vi', Flag: VietnamFlagIcon },
] as const;

export function ForgeShell({ activeView, onViewChange, health, connectionError, rail, children, language, onLanguageChange }: ForgeShellProps & { language: Language; onLanguageChange: (language: Language) => void }) {
  const t = useTranslations();
  const apiState = connectionError ? t('api.offline') : health ? (health.ready ? t('api.ready') : t('api.degraded')) : t('api.connecting');
  const statusClass = connectionError ? 'is-warning' : health?.ready ? 'is-ready' : 'is-loading';

  return (
    <main className='forge-app'>
      <header className='forge-header'>
        <div className='forge-brand' aria-label='FORGE Factory Operations Retrieval Generation Engine'>
          <div className='forge-mark'><Image src='/unicorn-logo.png' alt='' className='forge-logo' width={38} height={38} priority /></div>
          <div className='forge-brand-copy'>
            <div className='forge-wordmark'>FORGE</div>
            <div className='forge-descriptor' aria-label='Factory Operations Retrieval Generation Engine'>
              <span>{t('brand.descriptor1')}</span>
              <span>{t('brand.descriptor2')}</span>
            </div>
          </div>
        </div>
        <div className='forge-navigation-wrap'>
          <span className='forge-workspace-label'>{t('workspace')}</span>
          <nav className='forge-navigation' aria-label='Workspace navigation'>
            {navItems.filter(({ id }) => id !== 'evaluations').map(({ id, label, icon: Icon }) => (
              <button key={id} type='button' className={'forge-nav-item ' + (activeView === id ? 'is-active' : '')} onClick={() => onViewChange(id)} aria-current={activeView === id ? 'page' : undefined}>
                {Icon && <Icon className='forge-nav-icon' />}{t(label)}
              </button>
            ))}
          </nav>
        </div>
        <div className='forge-header-tools'>
          <div className={'forge-api-status ' + statusClass} role='status'>
            <span className='forge-status-dot' /><span>{apiState}</span><small>{t('api.gemini')}</small>
          </div>
          <div className='forge-language-switch' aria-label={t('language.selector')}>
            {languageOptions.map(({ id, label, Flag }) => (
              <button key={id} type='button' className={language === id ? 'is-active' : ''} aria-label={t(label)} aria-pressed={language === id} onClick={() => onLanguageChange(id)}>
                <Flag className='forge-flag' />
              </button>
            ))}
          </div>
        </div>
      </header>
      <div className='forge-body'>
        <aside className='forge-context-rail'>{rail}</aside>
        <section className='forge-main'>{children}</section>
      </div>
    </main>
  );
}
