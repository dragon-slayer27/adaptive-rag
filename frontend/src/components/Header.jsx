import React from 'react';

export default function Header({ activeTab, setActiveTab, healthStatus, latencyMs }) {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-title-group">
          <span className="brand-title">AdaptiveRAG</span>
          <span className="brand-badge">Corpus Explorer</span>
        </div>
      </div>

      <nav className="header-nav" aria-label="Main Navigation">
        <button
          type="button"
          className={`nav-tab ${activeTab === 'documents' ? 'nav-tab-active' : ''}`}
          onClick={() => setActiveTab('documents')}
          aria-current={activeTab === 'documents' ? 'page' : undefined}
        >
          Knowledge Base
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === 'chunks' ? 'nav-tab-active' : ''}`}
          onClick={() => setActiveTab('chunks')}
          aria-current={activeTab === 'chunks' ? 'page' : undefined}
        >
          Chunk Explorer
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === 'status' ? 'nav-tab-active' : ''}`}
          onClick={() => setActiveTab('status')}
          aria-current={activeTab === 'status' ? 'page' : undefined}
        >
          Diagnostics
        </button>
      </nav>

      <div className="header-health">
        <span className={`health-pill health-pill-${healthStatus}`}>
          <span className={`status-dot dot-${healthStatus}`} />
          {healthStatus === 'connected' && `Backend: Connected (${latencyMs}ms)`}
          {healthStatus === 'disconnected' && 'Backend: Offline'}
          {healthStatus === 'checking' && 'Backend: Checking...'}
        </span>
      </div>
    </header>
  );
}
