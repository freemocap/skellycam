import { useSharedMemory } from './SharedMemoryProvider'
import './App.css'

export const App = (): React.JSX.Element => {
  const { data, connected, error, filePath } = useSharedMemory()

  return (
    <div className="app-container">
      <h1>🚀 FlatBuffer IPC Demo</h1>

      <div className={`status-box ${connected ? 'connected' : 'disconnected'}`}>
        Status: {connected ? '✅ Connected' : '❌ Disconnected'}
      </div>

      {error && <div className="error-box">Error: {error}</div>}

      {filePath && (
        <div className="file-path">
          Shared file: <code>{filePath}</code>
        </div>
      )}

      {data ? (
        <div className="data-container">
          <h3>📊 Live Data from Python Process:</h3>
          <div className="data-grid">
            <div className="data-item">
              <span className="label">Sequence:</span>
              <span className="value">{data.sequence}</span>
            </div>
            <div className="data-item">
              <span className="label">Camera ID:</span>
              <span className="value">{data.cameraId}</span>
            </div>
            <div className="data-item">
              <span className="label">Frame Number:</span>
              <span className="value">{data.frameNumber}</span>
            </div>
            <div className="data-item">
              <span className="label">Timestamp:</span>
              <span className="value">{new Date(data.timestamp).toLocaleTimeString()}</span>
            </div>
            <div className="data-item">
              <span className="label">FPS:</span>
              <span className="value">{data.fps.toFixed(1)}</span>
            </div>
            <div className="data-item">
              <span className="label">CPU Usage:</span>
              <span className="value">{data.cpuUsage.toFixed(1)}%</span>
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
            <strong>🎯 Cross-Platform Zero-Copy Performance:</strong> Reading directly from Pythons
            shared file!
          </div>
        </div>
      ) : (
        <div className="waiting">Waiting for data...</div>
      )}
    </div>
  )
}

export default App
