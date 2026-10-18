import React from 'react';
import { API_BASE_URL } from '../api';

export default function SystemStatusView({
  healthData,
  healthStatus,
  latencyMs,
  lastChecked,
  error,
  onCheckHealth,
}) {
  return (
    <div className="view-container">
      <div className="view-header">
        <div>
          <h2 className="view-title">System Diagnostics</h2>
          <p className="view-subtitle">
            Verify backend API connectivity, service health, and network latency.
          </p>
        </div>
      </div>

      <div className="card status-card">
        <div className="status-header">
          <span className="status-label">Backend Connectivity Probe</span>
          <span className={`badge badge-${healthStatus}`}>
            <span className={`indicator indicator-${healthStatus}`} />
            {healthStatus === 'connected' && 'Backend: Connected'}
            {healthStatus === 'disconnected' && 'Backend: Offline'}
            {healthStatus === 'checking' && 'Backend: Checking...'}
          </span>
        </div>

        {error && (
          <div className="alert-box alert-error">
            <strong>Connection Error:</strong> {error}
          </div>
        )}

        <table className="details-table">
          <tbody>
            <tr>
              <td className="label">Target Endpoint</td>
              <td className="value font-mono">{API_BASE_URL}/health</td>
            </tr>
            {healthData && (
              <>
                <tr>
                  <td className="label">Service Name</td>
                  <td className="value">{healthData.service}</td>
                </tr>
                <tr>
                  <td className="label">Service Status</td>
                  <td className="value">{healthData.status}</td>
                </tr>
                <tr>
                  <td className="label">Environment</td>
                  <td className="value">{healthData.environment}</td>
                </tr>
                <tr>
                  <td className="label">Backend Version</td>
                  <td className="value">{healthData.version}</td>
                </tr>
                <tr>
                  <td className="label">Server Timestamp</td>
                  <td className="value font-mono">{healthData.timestamp}</td>
                </tr>
              </>
            )}
            {latencyMs !== null && (
              <tr>
                <td className="label">Roundtrip Latency</td>
                <td className="value font-mono">{latencyMs} ms</td>
              </tr>
            )}
            {lastChecked && (
              <tr>
                <td className="label">Last Checked</td>
                <td className="value">{lastChecked}</td>
              </tr>
            )}
          </tbody>
        </table>

        <div className="button-row">
          <button
            type="button"
            className="btn-primary"
            onClick={onCheckHealth}
            disabled={healthStatus === 'checking'}
          >
            {healthStatus === 'checking' ? 'Testing...' : 'Check Connection'}
          </button>
        </div>
      </div>

      <p className="footer-note">
        Probe verifies HTTP/JSON transport between Vite client and FastAPI backend service.
      </p>
    </div>
  );
}
