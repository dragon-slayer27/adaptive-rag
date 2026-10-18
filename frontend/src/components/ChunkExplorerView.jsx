import React, { useState, useEffect, useCallback } from 'react';
import { fetchDocumentChunks } from '../api';

export default function ChunkExplorerView({
  documents,
  selectedDocId,
  setSelectedDocId,
  onNavigateToDocuments,
}) {
  const [chunksData, setChunksData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [copiedChunkId, setCopiedChunkId] = useState(null);

  // If selectedDocId is null but documents exist, auto-select the first document
  useEffect(() => {
    if (!selectedDocId && documents && documents.length > 0) {
      setSelectedDocId(documents[0].id);
    }
  }, [selectedDocId, documents, setSelectedDocId]);

  // Load chunks when selected document, limit, or offset changes
  const loadChunks = useCallback(() => {
    if (!selectedDocId) {
      setChunksData(null);
      return;
    }

    setLoading(true);
    setError(null);

    fetchDocumentChunks(selectedDocId, limit, offset)
      .then((data) => {
        setChunksData(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load chunks for document');
        setLoading(false);
      });
  }, [selectedDocId, limit, offset]);

  useEffect(() => {
    loadChunks();
  }, [loadChunks]);

  // Reset offset when changing document or page size
  const handleDocumentChange = (docId) => {
    setSelectedDocId(docId);
    setOffset(0);
  };

  const handleLimitChange = (newLimit) => {
    setLimit(Number(newLimit));
    setOffset(0);
  };

  const handleCopyText = (chunkId, text) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        setCopiedChunkId(chunkId);
        setTimeout(() => setCopiedChunkId(null), 2000);
      });
    }
  };

  const currentDoc = (documents || []).find((d) => d.id === selectedDocId);
  const total = chunksData?.total ?? 0;
  const items = chunksData?.items ?? [];
  const startItem = total === 0 ? 0 : offset + 1;
  const endItem = Math.min(offset + limit, total);
  const totalPages = Math.ceil(total / limit) || 1;
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="view-container">
      <div className="view-header">
        <div>
          <h2 className="view-title">Chunk Explorer</h2>
          <p className="view-subtitle">
            Inspect generated token chunks, verify boundary slicing, and validate section offsets.
          </p>
        </div>

        {documents && documents.length > 0 && (
          <div className="doc-select-group">
            <label htmlFor="doc-picker" className="doc-picker-label">
              Document:
            </label>
            <select
              id="doc-picker"
              className="select-doc"
              value={selectedDocId || ''}
              onChange={(e) => handleDocumentChange(e.target.value)}
              aria-label="Select document to inspect chunks"
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename} ({doc.chunk_count} chunks)
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {!documents || documents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📂</div>
          <h3 className="empty-title">Corpus is empty</h3>
          <p className="empty-description">
            No documents have been ingested yet. Ingest documents to generate chunks.
          </p>
          <button type="button" className="btn-primary" onClick={onNavigateToDocuments}>
            Go to Knowledge Base
          </button>
        </div>
      ) : (
        <>
          {/* Document Summary Header */}
          {currentDoc && (
            <div className="chunk-doc-banner">
              <div className="doc-banner-info">
                <span className="banner-filename">{currentDoc.filename}</span>
                <span className={`format-badge format-${currentDoc.file_type.toLowerCase()}`}>
                  {currentDoc.file_type.toUpperCase()}
                </span>
                <span className="banner-stat">
                  <strong>{currentDoc.section_count}</strong> sections
                </span>
                <span className="banner-stat">
                  <strong>{currentDoc.chunk_count}</strong> chunks
                </span>
                <span className="banner-stat font-mono">
                  <strong>{currentDoc.total_chunk_tokens.toLocaleString()}</strong> chunk tokens (w/ overlap)
                </span>
              </div>

              {total > 0 && (
                <div className="pagination-bar">
                  <div className="pagination-info">
                    Showing <strong>{startItem}–{endItem}</strong> of <strong>{total}</strong> chunks
                    (Page {currentPage} of {totalPages})
                  </div>

                  <div className="pagination-controls">
                    <label htmlFor="page-size-select" className="sr-only">
                      Chunks per page
                    </label>
                    <select
                      id="page-size-select"
                      className="select-limit"
                      value={limit}
                      onChange={(e) => handleLimitChange(e.target.value)}
                    >
                      <option value={25}>25 / page</option>
                      <option value={50}>50 / page</option>
                      <option value={100}>100 / page</option>
                    </select>

                    <button
                      type="button"
                      className="btn-page"
                      disabled={offset === 0 || loading}
                      onClick={() => setOffset(Math.max(0, offset - limit))}
                      title="Previous page"
                    >
                      ← Prev
                    </button>
                    <button
                      type="button"
                      className="btn-page"
                      disabled={offset + limit >= total || loading}
                      onClick={() => setOffset(offset + limit)}
                      title="Next page"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="alert-box alert-error" role="alert">
              <div>
                <strong>Error loading chunks:</strong> {error}
              </div>
              <button type="button" className="btn-secondary btn-sm" onClick={loadChunks}>
                Retry
              </button>
            </div>
          )}

          {loading ? (
            <div className="loading-state">Loading document chunks...</div>
          ) : currentDoc && currentDoc.chunk_count === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">✂️</div>
              <h3 className="empty-title">Document Not Chunked</h3>
              <p className="empty-description">
                This document has sections stored but has not been chunked yet. Run the chunker from the project root:
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
                          `$env:PYTHONPATH="backend"; python -m app.chunking chunk ${currentDoc.id}`
                        )
                      }
                      title="Copy PowerShell command"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="cli-hint">$env:PYTHONPATH="backend"; python -m app.chunking chunk {currentDoc.id}</pre>
                </div>
                <div className="cli-hint-item">
                  <div className="cli-hint-header">
                    <span className="cli-platform-badge">Linux / macOS (Bash)</span>
                    <button
                      type="button"
                      className="btn-copy-hint"
                      onClick={() =>
                        navigator.clipboard?.writeText(
                          `PYTHONPATH=backend python -m app.chunking chunk ${currentDoc.id}`
                        )
                      }
                      title="Copy Bash command"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="cli-hint">PYTHONPATH=backend python -m app.chunking chunk {currentDoc.id}</pre>
                </div>
              </div>
              <button type="button" className="btn-primary" onClick={loadChunks}>
                Refresh Chunks
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="empty-state">
              <h3 className="empty-title">No chunks on this page</h3>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setOffset(0)}
              >
                Return to First Page
              </button>
            </div>
          ) : (
            <div className="chunks-list">
              {items.map((chunk) => {
                const charSpan = chunk.end_char - chunk.start_char;
                const isCopied = copiedChunkId === chunk.id;

                return (
                  <article key={chunk.id} className="chunk-card">
                    <div className="chunk-card-header">
                      <div className="chunk-badges">
                        <span className="badge-chunk-idx font-mono">
                          Chunk #{chunk.chunk_index}
                        </span>
                        <span className="badge-tokens font-mono" title="Evaluated BPE token count">
                          {chunk.token_count} tokens
                        </span>
                        <span className="badge-sec">Section #{chunk.section_index}</span>
                        {chunk.page_number && (
                          <span className="badge-page">Page {chunk.page_number}</span>
                        )}
                        {chunk.section_title && (
                          <span className="badge-title" title={chunk.section_title}>
                            {chunk.section_title}
                          </span>
                        )}
                      </div>

                      <div className="chunk-card-actions">
                        <button
                          type="button"
                          className="btn-copy"
                          onClick={() => handleCopyText(chunk.id, chunk.text)}
                          title="Copy verbatim chunk text"
                        >
                          {isCopied ? '✓ Copied' : 'Copy Text'}
                        </button>
                      </div>
                    </div>

                    <div className="chunk-offset-indicator">
                      <span className="offset-label">Section Character Span:</span>
                      <span className="offset-coords font-mono">
                        [{chunk.start_char} : {chunk.end_char})
                      </span>
                      <span className="offset-length font-mono">({charSpan} chars)</span>
                      <span className="offset-note">
                        (relative to parent section text, not full document)
                      </span>
                    </div>

                    <div className="chunk-text-box">
                      <pre className="chunk-text font-mono">{chunk.text}</pre>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
