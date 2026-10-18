import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import CorpusSummaryBar from './components/CorpusSummaryBar';
import KnowledgeBaseView from './components/KnowledgeBaseView';
import ChunkExplorerView from './components/ChunkExplorerView';
import SystemStatusView from './components/SystemStatusView';
import { fetchHealth, fetchCorpusStats, fetchDocuments } from './api';
import './App.css';

export default function App() {
  // Navigation state: default is 'documents' (Knowledge Base)
  const [activeTab, setActiveTab] = useState('documents'); // 'documents' | 'chunks' | 'status'

  // Health and connectivity state
  const [healthStatus, setHealthStatus] = useState('checking'); // 'connected' | 'disconnected' | 'checking'
  const [healthData, setHealthData] = useState(null);
  const [healthError, setHealthError] = useState(null);
  const [latencyMs, setLatencyMs] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);

  // Corpus data state
  const [corpusStats, setCorpusStats] = useState(null);
  const [documents, setDocuments] = useState(null);
  const [corpusLoading, setCorpusLoading] = useState(false);
  const [corpusError, setCorpusError] = useState(null);

  // Chunk inspection selection
  const [selectedDocId, setSelectedDocId] = useState(null);

  // Health probe
  const checkHealth = useCallback(async () => {
    setHealthStatus('checking');
    setHealthError(null);

    try {
      const { data, latencyMs: elapsed } = await fetchHealth();
      setLatencyMs(elapsed);
      setLastChecked(new Date().toLocaleTimeString());
      setHealthData(data);
      setHealthStatus('connected');
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : 'Failed to reach backend');
      setHealthStatus('disconnected');
      setHealthData(null);
      setLastChecked(new Date().toLocaleTimeString());
    }
  }, []);

  // Load corpus stats and documents
  const loadCorpus = useCallback(async () => {
    setCorpusLoading(true);
    setCorpusError(null);

    try {
      const [stats, docs] = await Promise.all([
        fetchCorpusStats(),
        fetchDocuments(),
      ]);
      setCorpusStats(stats);
      setDocuments(docs);
      setCorpusLoading(false);
    } catch (err) {
      setCorpusError(err instanceof Error ? err.message : 'Failed to load corpus data');
      setCorpusLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    checkHealth();
    loadCorpus();
  }, [checkHealth, loadCorpus]);

  // Handle deep navigation from Knowledge Base row to Chunk Explorer
  const handleInspectChunks = (docId) => {
    setSelectedDocId(docId);
    setActiveTab('chunks');
  };

  return (
    <div className="app-shell">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        healthStatus={healthStatus}
        latencyMs={latencyMs}
      />

      <CorpusSummaryBar
        stats={corpusStats}
        loading={corpusLoading}
        onRefresh={() => {
          checkHealth();
          loadCorpus();
        }}
      />

      <main className="app-main">
        {activeTab === 'documents' && (
          <KnowledgeBaseView
            documents={documents}
            loading={corpusLoading}
            error={corpusError}
            onRefresh={loadCorpus}
            onInspectChunks={handleInspectChunks}
          />
        )}

        {activeTab === 'chunks' && (
          <ChunkExplorerView
            documents={documents}
            selectedDocId={selectedDocId}
            setSelectedDocId={setSelectedDocId}
            onNavigateToDocuments={() => setActiveTab('documents')}
          />
        )}

        {activeTab === 'status' && (
          <SystemStatusView
            healthData={healthData}
            healthStatus={healthStatus}
            latencyMs={latencyMs}
            lastChecked={lastChecked}
            error={healthError}
            onCheckHealth={checkHealth}
          />
        )}
      </main>
    </div>
  );
}
