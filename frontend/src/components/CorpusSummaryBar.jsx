import React from 'react';

export default function CorpusSummaryBar({ stats, loading, onRefresh }) {
  const docs = stats?.total_documents ?? 0;
  const sections = stats?.total_sections ?? 0;
  const chunks = stats?.total_chunks ?? 0;
  const tokens = stats?.total_chunk_tokens ?? 0;

  return (
    <div className="corpus-summary-bar">
      <div className="summary-metrics">
        <span className="summary-item">
          <strong>{docs.toLocaleString()}</strong> {docs === 1 ? 'document' : 'documents'}
        </span>
        <span className="summary-divider">·</span>
        <span className="summary-item">
          <strong>{sections.toLocaleString()}</strong> {sections === 1 ? 'section' : 'sections'}
        </span>
        <span className="summary-divider">·</span>
        <span className="summary-item">
          <strong>{chunks.toLocaleString()}</strong> {chunks === 1 ? 'chunk' : 'chunks'}
        </span>
        <span className="summary-divider">·</span>
        <span
          className="summary-item summary-tokens"
          title="Sum of token counts across all stored chunks; includes tokens counted multiple times due to chunk overlap"
        >
          <strong>{tokens.toLocaleString()}</strong> total chunk tokens
          <span className="summary-hint">(includes overlap)</span>
        </span>
      </div>

      <div className="summary-actions">
        <button
          type="button"
          className="btn-refresh"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh corpus statistics"
          aria-label="Refresh corpus statistics"
        >
          {loading ? 'Refreshing...' : '↻ Refresh'}
        </button>
      </div>
    </div>
  );
}
