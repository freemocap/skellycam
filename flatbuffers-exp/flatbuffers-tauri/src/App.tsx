import React, { useState, useEffect, useCallback } from 'react'
import { invoke } from '@tauri-apps/api/core'
import './App.css'

interface ServerInfo {
  file_path: string
  size: number
  width: number
  height: number
  channels: number
}

interface PerformanceStats {
  rustReadFps: number
  rustDecodeFps: number
  rustFrameCount: number
}

export const App = (): React.JSX.Element => {
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null)
  const [isStreaming, setIsStreaming] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<PerformanceStats | null>(null)

  // Fetch server info on mount
  useEffect((): void => {
    const fetchInfo = async (): Promise<void> => {
      try {
        const response = await fetch('http://localhost:8009/info')
        const info = await response.json()
        setServerInfo(info)
      } catch (err) {
        setError(`Failed to fetch server info: ${err}`)
      }
    }
    fetchInfo()
  }, [])

  // Poll performance stats while streaming
  useEffect((): (() => void) | void => {
    if (!isStreaming) return

    const interval = setInterval(async (): Promise<void> => {
      try {
        const perfStats = await invoke<PerformanceStats>('get_performance_stats')
        setStats(perfStats)
      } catch (err) {
        console.error('Error fetching stats:', err)
      }
    }, 100) // Update every 100ms

    return (): void => clearInterval(interval)
  }, [isStreaming])

  const handleStartStreaming = useCallback(async (): Promise<void> => {
    if (!serverInfo) return

    try {
      // Start Python server
      await fetch('http://localhost:8009/start', { method: 'POST' })

      // Start Rust frame reader (1ms poll)
      await invoke('start_frame_reader', {
        path: serverInfo.file_path,
        pollRateMs: 1,
      })

      setIsStreaming(true)
      setError(null)
    } catch (err) {
      setError(`Failed to start: ${err}`)
    }
  }, [serverInfo])

  const handleStopStreaming = useCallback(async (): Promise<void> => {
    try {
      await fetch('http://localhost:8009/stop', { method: 'POST' })
      await invoke('stop_frame_reader')
      setIsStreaming(false)
    } catch (err) {
      setError(`Failed to stop: ${err}`)
    }
  }, [])

  const frameSizeMB = serverInfo
    ? (serverInfo.width * serverInfo.height * serverInfo.channels) / (1024 * 1024)
    : 0

  return (
    <div className="app-container">
      <h1>Rust Frame Reader Performance</h1>

      <div className="controls">
        <button
          onClick={isStreaming ? handleStopStreaming : handleStartStreaming}
          className={isStreaming ? 'stop-button' : 'start-button'}
          disabled={!serverInfo}
        >
          {isStreaming ? 'Stop' : 'Start'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {serverInfo && (
        <div className="server-info">
          Frame: {serverInfo.width}x{serverInfo.height} RGB ({frameSizeMB.toFixed(2)} MB)
          <br />
          File: <code>{serverInfo.file_path}</code>
        </div>
      )}

      {isStreaming && stats ? (
        <div className="performance-display">
          <div className="main-metric">
            <div className="metric-label">RUST READ PERFORMANCE</div>
            <div className="metric-value-large">{stats.rustReadFps.toFixed(1)}</div>
            <div className="metric-unit">FPS</div>
          </div>

          <div className="secondary-metrics">
            <div className="metric-item">
              <span className="label">Decode FPS:</span>
              <span className="value">{stats.rustDecodeFps.toFixed(1)}</span>
            </div>
            <div className="metric-item">
              <span className="label">Bandwidth:</span>
              <span className="value">{(stats.rustReadFps * frameSizeMB).toFixed(1)} MB/s</span>
            </div>
            <div className="metric-item">
              <span className="label">Total Frames:</span>
              <span className="value">{stats.rustFrameCount.toLocaleString()}</span>
            </div>
            <div className="metric-item">
              <span className="label">Avg Latency:</span>
              <span className="value">
                {stats.rustReadFps > 0 ? (1000 / stats.rustReadFps).toFixed(2) : 'N/A'} ms
              </span>
            </div>
          </div>

          <div className="performance-status">
            {stats.rustReadFps > 200 ? (
              <span className="status-excellent">✅ Excellent Performance</span>
            ) : stats.rustReadFps > 100 ? (
              <span className="status-good">✅ Good Performance</span>
            ) : (
              <span className="status-low">⚠️ Low Performance</span>
            )}
          </div>
        </div>
      ) : (
        <div className="waiting">
          {isStreaming ? 'Waiting for frames...' : 'Click "Start" to begin'}
        </div>
      )}
    </div>
  )
}

export default App