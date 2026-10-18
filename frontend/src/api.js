/**
 * Centralized API client for AdaptiveRAG Corpus Explorer.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Keep fallback error string if response is not JSON
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function fetchHealth() {
  const startTime = performance.now();
  const data = await request('/health');
  const latencyMs = Math.round(performance.now() - startTime);
  return { data, latencyMs };
}

export async function fetchCorpusStats() {
  return request('/api/stats');
}

export async function fetchDocuments() {
  return request('/api/documents');
}

export async function fetchDocumentDetails(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`);
}

export async function fetchDocumentChunks(documentId, limit = 50, offset = 0) {
  return request(
    `/api/documents/${encodeURIComponent(documentId)}/chunks?limit=${limit}&offset=${offset}`
  );
}

export { API_BASE_URL };
