import { useSharedMemory } from './SharedMemoryProvider'
import './App.css'

export const App = (): React.JSX.Element => {
  const { data, connected, error, filePath, fps } = useSharedMemory()

  return (
    <div className="app-container">
      <h1>🚀 FlatBuffer IPC Demo - 1080p Streaming</h1>

      <div className={`status-box ${connected ? 'connected' : 'disconnected'}`}>
        Status: {connected ? '✅ Connected' : '❌ Disconnected'}
      </div>

      {error && <div className="error-box">Error: {error}</div>}

      {filePath && (
        <div className="file-path">
          Shared file: <code>{filePath}</code>
        </div>
      )}

      {data && (
        <div className="fps-display">
          <h2>⚡ Streaming Performance</h2>
          <div className="fps-value">{fps.toFixed(1)} FPS</div>
          <div className="fps-detail">
            1920x1080 RGB • {((1920 * 1080 * 3 * fps) / (1024 * 1024)).toFixed(2)} MB/s
          </div>
        </div>
      )}

      {data ? (
        <div className="data-container">
          <h3>📊 Live Data:</h3>
          <div className="data-grid">
            <div className="data-item">
              <span className="label">Frame Number:</span>
              <span className="value">{data.frameNumber}</span>
            </div>
            <div className="data-item">
              <span className="label">Camera ID:</span>
              <span className="value">{data.cameraId}</span>
            </div>
            <div className="data-item">
              <span className="label">Width:</span>
              <span className="value">1920</span>
            </div>
            <div className="data-item">
              <span className="label">Height:</span>
              <span className="value">1080</span>
            </div>
            <div className="data-item full-width">
              <span className="label">Message:</span>
              <span className="value">{data.message}</span>
            </div>
            <div className="data-item full-width">
              <span className="label">Pixel Sample (first 10):</span>
              <span className="value mono">[{data.pixelSample.join(', ')}]</span>
            </div>
          </div>

          <div className="performance-note">
            <strong>🎯 Zero-Copy IPC:</strong> 1080p frames streamed via shared memory
          </div>
        </div>
      ) : (
        <div className="waiting">Waiting for data...</div>
      )}
    </div>
  )
}

export default App
