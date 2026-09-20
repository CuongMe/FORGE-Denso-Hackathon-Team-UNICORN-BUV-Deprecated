'use client';

import type { ReactNode } from 'react';

import type { HealthResponse } from '@/lib/types';

import { TableIcon } from './ForgeIcons';

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
  { id: 'ask', label: 'Ask' },
  { id: 'documents', label: 'Documents', icon: TableIcon },
  { id: 'metrics', label: 'Metrics' },
  { id: 'evaluations', label: 'Evaluations' },
];

export function ForgeShell({ activeView, onViewChange, health, connectionError, rail, children }: ForgeShellProps) {
  const apiState = connectionError ? 'API OFFLINE' : health ? (health.ready ? 'API READY' : 'API DEGRADED') : 'CONNECTING';
  const statusClass = connectionError ? 'is-warning' : health?.ready ? 'is-ready' : 'is-loading';

  return (
    <main className='forge-app'>
      <header className='forge-header'>
        <div className='forge-brand' aria-label='FORGE Factory Operations Retrieval Generation Engine'>
          <div className='forge-mark'><img src='/forge-mark.svg' alt='' className='forge-logo' /></div>
          <div className='forge-brand-copy'>
            <div className='forge-wordmark'>FORGE</div>
            <div className='forge-descriptor' aria-label='Factory Operations Retrieval Generation Engine'>
              <span>Factory Operations Retrieval</span>
              <span>Generation Engine</span>
            </div>
          </div>
        </div>
        <div className='forge-navigation-wrap'>
          <span className='forge-workspace-label'>WORKSPACE</span>
          <nav className='forge-navigation' aria-label='Workspace navigation'>
            {navItems.map(({ id, label, icon: Icon }) => (
              <button key={id} type='button' className={'forge-nav-item ' + (activeView === id ? 'is-active' : '')} onClick={() => onViewChange(id)} aria-current={activeView === id ? 'page' : undefined}>
                {Icon && <Icon className='forge-nav-icon' />}{label}
              </button>
            ))}
          </nav>
        </div>
        <div className='forge-header-tools'>
          <div className='forge-spectrum' aria-label='FORGE seven color spectrum'>
            {['#E85D75', '#F49B50', '#EAC456', '#4FBD7B', '#4D83E6', '#6868C9', '#A568C7'].map((color) => <span key={color} style={{ backgroundColor: color }} />)}
          </div>
          <div className={'forge-api-status ' + statusClass} role='status'>
            <span className='forge-status-dot' /><span>{apiState}</span><small>GEMINI</small>
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
