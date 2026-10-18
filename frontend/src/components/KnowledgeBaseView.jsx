import React, { useState, useEffect } from 'react';
import { fetchDocumentDetails } from '../api';

export default function KnowledgeBaseView({
  documents,
  loading,
  error,
  onRefresh,
  onInspectChunks,
}) {
  const [filterText, setFilterText] = useState('');
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [docDetail, setDocDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  // Filter documents client-side by filename, title, or format
  const filteredDocs = (documents || []).filter((doc) => {
    const q = filterText.toLowerCase();
    const nameMatch = doc.filename.toLowerCase().includes(q);
    const titleMatch = doc.title ? doc.title.toLowerCase().includes(q) : false;
    const formatMatch = doc.file_type.toLowerCase().includes(q);
    return nameMatch || titleMatch || formatMatch;
  });

  // Fetch document details when selected
  useEffect(() => {
    if (!selectedDocId) {
      setDocDetail(null);
      return;
    }

    let isMounted = true;
    setDetailLoading(true);
    setDetailError(null);

    fetchDocumentDetails(selectedDocId)
      .then((data) => {
        if (isMounted) {
          setDocDetail(data);
          setDetailLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setDetailError(err.message || 'Failed to load document details');
          setDetailLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedDocId]);

  return (
    <div className="view-container">
      <div className="view-header">
        <div>
          <h2 className="view-title">Knowledge Base</h2>
          <p className="view-subtitle">
            Inspect canonical documents, structural sections, and chunk allocation.
          </p>
        </div>
        <div className="filter-group">
          <input
            type="search"
            className="input-search"
            placeholder="Filter by name or format..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            aria-label="Filter documents by name or format"
          />
        </div>
      </div>

      {error && (
        <div className="alert-box alert-error" role="alert">
          <div>
            <strong>Error loading documents:</strong> {error}
          </div>
          <button type="button" className="btn-secondary btn-sm" onClick={onRefresh}>
            Retry
          </button>
        </div>
      )}

      {loading && !documents ? (
        <div className="loading-state">Loading document catalog...</div>
      ) : documents && documents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📄</div>
          <h3 className="empty-title">No documents in corpus</h3>
          <p className="empty-description">
            Place supported files (<code>.pdf</code>, <code>.docx</code>, <code>.md</code>, <code>.txt</code>) into <code>data/documents/</code> (or specify any folder/file path), then run the ingestion CLI from the project root:
          </p>
          <div className="cli-hint-container">
            <div className="cli-hint-item">
              <div className="cli-hint-header">
                <span className="cli-platform-badge">Windows PowerShell</span>
                <button
                  type="button"
                  className="btn-copy-hint"
                  onClick={() =>
                    navigator.clipboard?.writeText(
                      '$env:PYTHONPATH="backend"; python -m app.ingestion ingest data/documents'
                    )
                  }
                  title="Copy PowerShell command"
                >
                  Copy
                </button>
              </div>
              <pre className="cli-hint">$env:PYTHONPATH="backend"; python -m app.ingestion ingest data/documents</pre>
            </div>
            <div className="cli-hint-item">
              <div className="cli-hint-header">
                <span className="cli-platform-badge">Linux / macOS (Bash)</span>
                <button
                  type="button"
                  className="btn-copy-hint"
                  onClick={() =>
                    navigator.clipboard?.writeText(
                      'PYTHONPATH=backend python -m app.ingestion ingest data/documents'
                    )
                  }
                  title="Copy Bash command"
                >
                  Copy
                </button>
              </div>
              <pre className="cli-hint">PYTHONPATH=backend python -m app.ingestion ingest data/documents</pre>
            </div>
          </div>
          <button type="button" className="btn-primary" onClick={onRefresh}>
            Refresh Catalog
          </button>
        </div>
      ) : (
        <div className="catalog-layout">
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="th-filename">Document Name</th>
                  <th className="th-format">Format</th>
                  <th className="th-number th-sections">Sections</th>
                  <th className="th-number th-chunks">Chunks</th>
                  <th className="th-number th-tokens">Chunk Tokens</th>
                  <th className="th-date">Ingested At</th>
                  <th className="th-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="td-empty">
                      No documents match "{filterText}"
                    </td>
                  </tr>
                ) : (
                  filteredDocs.map((doc) => {
                    const isSelected = selectedDocId === doc.id;
                    return (
                      <tr
                        key={doc.id}
                        className={`table-row ${isSelected ? 'table-row-selected' : ''}`}
                        onClick={() => setSelectedDocId(isSelected ? null : doc.id)}
                      >
                        <td className="td-filename">
                          <div className="filename-primary" title={doc.filename}>
                            {doc.filename}
                          </div>
                          {doc.title && <div className="filename-title">{doc.title}</div>}
                        </td>
                        <td>
                          <span className={`format-badge format-${doc.file_type.toLowerCase()}`}>
                            {doc.file_type.toUpperCase()}
                          </span>
                        </td>
                        <td className="td-number">{doc.section_count}</td>
                        <td className="td-number">{doc.chunk_count}</td>
                        <td className="td-number font-mono">
                          {doc.total_chunk_tokens.toLocaleString()}
                        </td>
                        <td className="td-date">
                          {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="td-actions" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            className="btn-action"
                            onClick={() => onInspectChunks(doc.id)}
                            title="Inspect chunks for this document"
                          >
                            Inspect Chunks →
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Master-Detail Inspection Drawer */}
          {selectedDocId && (
            <aside className="detail-drawer" aria-label="Document Details">
              <div className="detail-header">
                <div>
                  <h3 className="detail-title">Document Inspection</h3>
                  <div className="detail-id font-mono">ID: {selectedDocId}</div>
                </div>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => setSelectedDocId(null)}
                  aria-label="Close document details"
                >
                  ✕
                </button>
              </div>

              {detailLoading && (
                <div className="loading-state">Loading document breakdown...</div>
              )}

              {detailError && (
                <div className="alert-box alert-error">{detailError}</div>
              )}

              {docDetail && (
                <div className="detail-content">
                  <div className="detail-section">
                    <h4 className="section-heading">Metadata &amp; Verification</h4>
                    <table className="meta-table">
                      <tbody>
                        <tr>
                          <td className="meta-label">Filename</td>
                          <td className="meta-value">{docDetail.filename}</td>
                        </tr>
                        {docDetail.title && (
                          <tr>
                            <td className="meta-label">Title</td>
                            <td className="meta-value">{docDetail.title}</td>
                          </tr>
                        )}
                        <tr>
                          <td className="meta-label">Format</td>
                          <td className="meta-value">{docDetail.file_type.toUpperCase()}</td>
                        </tr>
                        <tr>
                          <td className="meta-label">Content SHA-256</td>
                          <td className="meta-value font-mono break-all">
                            {docDetail.content_hash}
                          </td>
                        </tr>
                        <tr>
                          <td className="meta-label">Last Updated</td>
                          <td className="meta-value">
                            {new Date(docDetail.updated_at).toLocaleString()}
                          </td>
                        </tr>
                        <tr>
                          <td className="meta-label">Total Chunks</td>
                          <td className="meta-value">{docDetail.chunk_count}</td>
                        </tr>
                        <tr>
                          <td className="meta-label">Total Chunk Tokens</td>
                          <td className="meta-value font-mono">
                            {docDetail.total_chunk_tokens.toLocaleString()} (sum w/ overlap)
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="detail-section">
                    <div className="section-header-split">
                      <h4 className="section-heading">
                        Sections ({docDetail.sections.length})
                      </h4>
                      <button
                        type="button"
                        className="btn-action-primary"
                        onClick={() => onInspectChunks(docDetail.id)}
                      >
                        Inspect All Chunks →
                      </button>
                    </div>

                    <div className="sections-list">
                      {docDetail.sections.map((sec) => (
                        <div key={sec.id} className="section-card">
                          <div className="section-card-meta">
                            <span className="badge-index">Section #{sec.section_index}</span>
                            {sec.page_number && (
                              <span className="badge-page">Page {sec.page_number}</span>
                            )}
                            {sec.section_title && (
                              <span className="badge-title">{sec.section_title}</span>
                            )}
                            <span className="char-count font-mono">
                              {sec.char_length.toLocaleString()} chars
                            </span>
                          </div>
                          <div className="section-preview font-mono">
                            "{sec.text_preview}
                            {sec.char_length > sec.text_preview.length ? '...' : ''}"
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
