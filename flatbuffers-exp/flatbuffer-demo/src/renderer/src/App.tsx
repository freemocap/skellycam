import { useSharedMemory } from './SharedMemoryProvider'
import './App.css'

export const App = (): React.JSX.Element => {
  const {
    data,
    error,
    filePath,
    serverInfo,
    mainReadFps,
    mainReadFrameCount,
    mainTotalBytesRead,
    rendererProcessedFps,
    rendererProcessedFrameCount,
    rendererDisplayFps,
    rendererTotalBytesProcessed,
    serverWriteFps,
    isStreaming,
    startStreaming,
    stopStreaming,
    frameSamplingRate,
    setFrameSamplingRate
  } = useSharedMemory()

  const handleToggleStreaming = async (): Promise<void> => {
    if (isStreaming) {
      await stopStreaming()
    } else {
      await startStreaming()
    }
  }

  // Calculate frame size if we have server info
  const frameSizeMB = serverInfo ? (serverInfo.width * serverInfo.height * 3) / (1024 * 1024) : 0

  // Calculate bandwidths
  const serverBandwidthMBps = serverWriteFps * frameSizeMB
  const mainBandwidthMBps = mainReadFps > 0 ? (mainTotalBytesRead / (1024 * 1024)) / (mainReadFrameCount / mainReadFps) : 0
  const rendererBandwidthMBps = rendererProcessedFps > 0 ? (rendererTotalBytesProcessed / (1024 * 1024)) / (rendererProcessedFrameCount / rendererProcessedFps) : 0

  return (
    <div className="app-container">
      <h1>FlatBuffer IPC Benchmark - 4-Stage Pipeline Performance Analysis</h1>

      <div className="controls">
        <button
          onClick={handleToggleStreaming}
          className={isStreaming ? 'stop-button' : 'start-button'}
        >
          {isStreaming ? 'Stop Streaming' : 'Start Streaming'}
        </button>

        <div className="sampling-control">
          <label>
            Display Sampling Rate:
            <select
              value={frameSamplingRate}
              onChange={(e): void => setFrameSamplingRate(Number(e.target.value))}
              disabled={isStreaming}
            >
              <option value={1}>Every frame (max UI load)</option>
              <option value={2}>Every 2nd frame</option>
              <option value={5}>Every 5th frame</option>
              <option value={10}>Every 10th frame</option>
            </select>
          </label>
          <small>Change before starting stream</small>
        </div>
      </div>

      {error && <div className="error-box">Error: {error}</div>}

      {filePath && (
        <div className="file-path">
          Shared Memory File: <code>{filePath}</code>
        </div>
      )}

      {serverInfo && (
        <div className="server-info">
          Frame Spec: {serverInfo.width}x{serverInfo.height} RGB JPEG - {frameSizeMB.toFixed(2)} MB uncompressed
        </div>
      )}

      {/* Four-stage performance pipeline - FULL DIAGNOSTIC VIEW */}
      <div className="pipeline-container">
        <div className="metric-box server-metric">
          <h2>STAGE 1: SERVER</h2>
          <div className="metric-label-top">Python Process</div>
          <div className="metric-value">{serverWriteFps.toFixed(1)} FPS</div>
          <div className="metric-label">Write to mmap</div>
          {data && (
            <>
              <div className="metric-detail">Frame #{data.frameNumber}</div>
              <div className="metric-detail">{serverBandwidthMBps.toFixed(2)} MB/s</div>
              <div className="metric-detail">Latency: {serverWriteFps > 0 ? (1000 / serverWriteFps).toFixed(2) : 'N/A'} ms</div>
            </>
          )}
        </div>

        <div className="arrow">→</div>

        <div className="metric-box main-metric">
          <h2>STAGE 2: MAIN PROCESS</h2>
          <div className="metric-label-top">Electron (Native)</div>
          <div className="metric-value">{mainReadFps.toFixed(1)} FPS</div>
          <div className="metric-label">Read from mmap (1ms poll)</div>
          <div className="metric-detail">Total reads: {mainReadFrameCount}</div>
          <div className="metric-detail">{(mainTotalBytesRead / (1024 * 1024)).toFixed(2)} MB read</div>
          <div className="metric-detail">Latency: {mainReadFps > 0 ? (1000 / mainReadFps).toFixed(2) : 'N/A'} ms</div>
        </div>

        <div className="arrow">→</div>

        <div className="metric-box ipc-metric">
          <h2>STAGE 3: IPC</h2>
          <div className="metric-label-top">Electron IPC</div>
          <div className="metric-value">{rendererProcessedFps.toFixed(1)} FPS</div>
          <div className="metric-label">Main to Renderer transfer</div>
          <div className="metric-detail">Received: {rendererProcessedFrameCount} frames</div>
          <div className="metric-detail">{(rendererTotalBytesProcessed / (1024 * 1024)).toFixed(2)} MB transferred</div>
          <div className="metric-detail">Efficiency: {mainReadFps > 0 ? ((rendererProcessedFps / mainReadFps) * 100).toFixed(1) : '0'}%</div>
        </div>

        <div className="arrow">→</div>

        <div className="metric-box renderer-metric">
          <h2>STAGE 4: DISPLAY</h2>
          <div className="metric-label-top">React UI (60 FPS max)</div>
          <div className="metric-value">{rendererDisplayFps.toFixed(1)} FPS</div>
          <div className="metric-label">DOM updates (sampling: 1/{frameSamplingRate})</div>
          <div className="metric-detail">Browser refresh limit: 60 FPS</div>
          <div className="metric-detail">Utilization: {(rendererDisplayFps / 60 * 100).toFixed(1)}%</div>
          <div className="metric-detail">Latency: {rendererDisplayFps > 0 ? (1000 / rendererDisplayFps).toFixed(2) : 'N/A'} ms</div>
        </div>
      </div>

      {/* Bottleneck analysis - 4 stage pipeline */}
      {isStreaming && mainReadFps > 0 && rendererDisplayFps > 0 && (
        <div className="bottleneck-box">
          <h3>4-Stage Pipeline Bottleneck Analysis</h3>
          <div className="bottleneck-grid">
            <div className="bottleneck-item">
              <span className="label">Stage 1 to 2 (Server to Main):</span>
              <span className={serverWriteFps > mainReadFps ? 'value warning' : 'value good'}>
                {serverWriteFps > mainReadFps
                  ? `Server outpacing by ${(serverWriteFps / mainReadFps).toFixed(2)}x (normal - main reads latest)`
                  : `Main keeping up (${(mainReadFps / serverWriteFps).toFixed(2)}x)`
                }
              </span>
            </div>
            <div className="bottleneck-item">
              <span className="label">Stage 2 to 3 (Main to IPC):</span>
              <span className={mainReadFps > rendererProcessedFps * 2 ? 'value warning' : 'value good'}>
                {mainReadFps > rendererProcessedFps * 2
                  ? `IPC bottleneck: ${((1 - rendererProcessedFps / mainReadFps) * 100).toFixed(1)}% frames dropped`
                  : `IPC efficient (${(rendererProcessedFps / mainReadFps * 100).toFixed(1)}% delivered)`
                }
              </span>
            </div>
            <div className="bottleneck-item">
              <span className="label">Stage 3 to 4 (IPC to Display):</span>
              <span className={rendererProcessedFps > rendererDisplayFps * 1.5 ? 'value info' : 'value good'}>
                {rendererProcessedFps > rendererDisplayFps * 1.5
                  ? `Display sampling (${(rendererDisplayFps / rendererProcessedFps * 100).toFixed(1)}% shown, 1/${frameSamplingRate} sampling)`
                  : `Display keeping up with processing`
                }
              </span>
            </div>
            <div className="bottleneck-item">
              <span className="label">Overall Pipeline Efficiency:</span>
              <span className={serverWriteFps > 0 ? 'value info' : 'value good'}>
                {serverWriteFps > 0
                  ? `End-to-end: ${(rendererDisplayFps / serverWriteFps * 100).toFixed(1)}% (${rendererDisplayFps.toFixed(1)} / ${serverWriteFps.toFixed(1)} FPS)`
                  : 'N/A'
                }
              </span>
            </div>
            <div className="bottleneck-item">
              <span className="label">Browser Refresh Limit:</span>
              <span className={rendererDisplayFps > 55 ? 'value info' : 'value good'}>
                {rendererDisplayFps > 55
                  ? `Near maximum (${rendererDisplayFps.toFixed(1)} / 60 FPS) - excellent!`
                  : `Display: ${rendererDisplayFps.toFixed(1)} / 60 FPS (${(rendererDisplayFps / 60 * 100).toFixed(1)}% utilization)`
                }
              </span>
            </div>
            <div className="bottleneck-item">
              <span className="label">Main Process Read Speed:</span>
              <span className={mainReadFps > 200 ? 'value good' : mainReadFps > 100 ? 'value info' : 'value warning'}>
                {mainReadFps > 200
                  ? `Excellent (${mainReadFps.toFixed(1)} FPS)`
                  : mainReadFps > 100
                    ? `Good (${mainReadFps.toFixed(1)} FPS) - setInterval@1ms is imprecise`
                    : `Low (${mainReadFps.toFixed(1)} FPS) - may need optimization`
                }
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Detailed performance comparison */}
      {data && isStreaming && (
        <div className="comparison-box">
          <h3>Detailed Performance Metrics</h3>
          <div className="comparison-grid">
            <div className="comparison-item">
              <span className="label">Server Write Latency:</span>
              <span className="value">
                {serverWriteFps > 0 ? `${(1000 / serverWriteFps).toFixed(2)} ms` : 'N/A'}
              </span>
            </div>
            <div className="comparison-item">
              <span className="label">Main Process Read Latency:</span>
              <span className="value">
                {mainReadFps > 0 ? `${(1000 / mainReadFps).toFixed(2)} ms` : 'N/A'}
              </span>
            </div>
            <div className="comparison-item">
              <span className="label">IPC Transfer Latency:</span>
              <span className="value">
                {rendererProcessedFps > 0 ? `${(1000 / rendererProcessedFps).toFixed(2)} ms` : 'N/A'}
              </span>
            </div>
            <div className="comparison-item">
              <span className="label">Renderer Display Latency:</span>
              <span className="value">
                {rendererDisplayFps > 0 ? `${(1000 / rendererDisplayFps).toFixed(2)} ms` : 'N/A'}
              </span>
            </div>
            <div className="comparison-item">
              <span className="label">End-to-End Pipeline Efficiency:</span>
              <span className="value">
                {serverWriteFps > 0
                  ? `${(rendererDisplayFps / serverWriteFps * 100).toFixed(1)}%`
                  : 'N/A'
                }
              </span>
            </div>
            <div className="comparison-item">
              <span className="label">Server Bandwidth:</span>
              <span className="value">{serverBandwidthMBps.toFixed(2)} MB/s</span>
            </div>
          </div>
        </div>
      )}

      {/* Live data display */}
      {data && isStreaming ? (
        <div className="data-container">
          <h3>Live Frame Data</h3>
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
              <span className="label">Timestamp:</span>
              <span className="value">{new Date(data.timestamp).toLocaleTimeString()}</span>
            </div>
            <div className="data-item full-width">
              <span className="label">Message:</span>
              <span className="value">{data.message}</span>
            </div>
            <div className="data-item full-width">
              <span className="label">Pixel Sample (first 10 bytes):</span>
              <span className="value mono">[{data.pixelSample.join(', ')}]</span>
            </div>
          </div>

          <div className="performance-note">
            <strong>Pipeline Performance Expectations:</strong>
            <br />
            <strong>Stage 1 - Server:</strong> 100-1000+ FPS (mmap writes are extremely fast)
            <br />
            <strong>Stage 2 - Main Process:</strong> 100-500 FPS (limited by setInterval accuracy at 1ms)
            <br />
            <strong>Stage 3 - IPC:</strong> 50-500 FPS (Electron IPC has overhead for large buffers)
            <br />
            <strong>Stage 4 - Display:</strong> 30-60 FPS (browser refresh rate + React reconciliation)
            <br />
            <br />
            <strong>What's Normal:</strong>
            <br />
            Server outpacing reads by 2-10x: Expected (latest frame only)
            <br />
            Main process reading 100-500 FPS: Good (setInterval @ 1ms is imprecise)
            <br />
            IPC dropping some frames: Expected (React can't keep up)
            <br />
            Display at 30-45 FPS: Excellent for React DOM updates
            <br />
            Display at 55-60 FPS: Outstanding (near browser limit)
            <br />
            <br />
            <strong>To Go Faster:</strong> Use Canvas/WebGL instead of React DOM (can hit full 60 FPS)
          </div>
        </div>
      ) : (
        <div className="waiting">
          {isStreaming ? 'Waiting for data...' : 'Click "Start Streaming" to begin'}
        </div>
      )}
    </div>
  )
}

export default App
