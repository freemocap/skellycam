import React, { useState, useEffect, useCallback, useRef } from 'react'
import { invoke } from '@tauri-apps/api/core'

interface ServerInfo {
  file_path: string
  capacity: number
  slot_size: number
  total_size: number
  width: number
  height: number
  channels: number
  latest_frame_number: number
}

interface PerformanceStats {
  rustReadFps: number
  rustDecodeFps: number
  rustFrameCount: number
  latestServerFps: number
  latestFrameNumber: number
  serverLatestFrameNumber: number
}

interface FrameBitmap {
  width: number
  height: number
  data: number[]
  frameNumber: number
  timestamp: number
  checksumValid: boolean
}

export default function App(): React.JSX.Element {
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null)
  const [isStreaming, setIsStreaming] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<PerformanceStats | null>(null)
  const [currentFrame, setCurrentFrame] = useState<FrameBitmap | null>(null)
  const [lastServerFrameNumber, setLastServerFrameNumber] = useState<number>(0)

  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Fetch server info on mount
  useEffect((): void => {
    const fetchInfo = async (): Promise<void> => {
      try {
        const response = await fetch('http://localhost:8009/info')
        const info = await response.json()
        console.log('Server info:', info)
        setServerInfo(info)
      } catch (err) {
        setError(`Failed to fetch server info: ${err}`)
      }
    }
    fetchInfo()
  }, [])

  // Draw frame to canvas
  useEffect((): void => {
    if (!currentFrame || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = currentFrame.width
    canvas.height = currentFrame.height

    const imageData = ctx.createImageData(currentFrame.width, currentFrame.height)
    imageData.data.set(new Uint8ClampedArray(currentFrame.data))
    ctx.putImageData(imageData, 0, 0)
  }, [currentFrame])

  // Poll for new frames while streaming
  useEffect((): (() => void) | void => {
    if (!isStreaming) return

    const interval = setInterval(async (): Promise<void> => {
      try {
        // Get latest frame number from buffer
        const latestFrameNumber = await invoke<number>('get_latest_frame_number_from_buffer')

        // Only request new frame if frame number changed
        if (latestFrameNumber !== lastServerFrameNumber && latestFrameNumber > 0) {
          setLastServerFrameNumber(latestFrameNumber)

          // Request the new frame
          const frame = await invoke<FrameBitmap | null>('request_frame', {
            frameNumber: latestFrameNumber
          })

          if (frame) {
            setCurrentFrame(frame)
          }
        }

        // Update stats
        const perfStats = await invoke<PerformanceStats>('get_performance_stats')
        setStats(perfStats)
      } catch (err) {
        console.error('Error fetching frame:', err)
      }
    }, 16) // ~60 FPS polling

    return (): void => clearInterval(interval)
  }, [isStreaming, lastServerFrameNumber])

  const handleStartStreaming = useCallback(async (): Promise<void> => {
    if (!serverInfo) return

    try {
      // Start Python server
      await fetch('http://localhost:8009/start', { method: 'POST' })

      // Start Rust frame reader
      await invoke('start_frame_reader', {
        path: serverInfo.file_path,
        pollRateMs: 1,
      })

      setIsStreaming(true)
      setError(null)
      setLastServerFrameNumber(0)
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

  const requestSpecificFrame = useCallback(async (frameNumber: number): Promise<void> => {
    try {
      const frame = await invoke<FrameBitmap | null>('request_frame', {
        frameNumber: frameNumber
      })

      if (frame) {
        setCurrentFrame(frame)
      } else {
        setError(`Frame ${frameNumber} not available`)
      }
    } catch (err) {
      setError(`Failed to request frame: ${err}`)
    }
  }, [])

  const frameSizeMB = serverInfo
    ? (serverInfo.width * serverInfo.height * serverInfo.channels) / (1024 * 1024)
    : 0

  const lag = stats
    ? stats.serverLatestFrameNumber - stats.latestFrameNumber
    : 0

  return (
    <div style={{
      padding: '2rem',
      maxWidth: '1200px',
      margin: '0 auto',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      minHeight: '100vh',
      color: 'white'
    }}>
      <h1 style={{ marginBottom: '2rem', fontSize: '2rem' }}>
        🎯 Advanced Ring Buffer - On-Demand Frame Requests
      </h1>

      <div style={{ marginBottom: '2rem' }}>
        <button
          onClick={isStreaming ? handleStopStreaming : handleStartStreaming}
          disabled={!serverInfo}
          style={{
            padding: '1rem 2rem',
            fontSize: '1.1rem',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: serverInfo ? 'pointer' : 'not-allowed',
            background: isStreaming
              ? 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
              : 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            color: 'white',
            transition: 'transform 0.1s',
          }}
          onMouseDown={(e): void => {
            e.currentTarget.style.transform = 'scale(0.95)'
          }}
          onMouseUp={(e): void => {
            e.currentTarget.style.transform = 'scale(1)'
          }}
        >
          {isStreaming ? '⏹️ Stop' : '▶️ Start'}
        </button>
      </div>

      {error && (
        <div style={{
          padding: '1rem',
          marginBottom: '1rem',
          background: 'rgba(239, 68, 68, 0.2)',
          border: '2px solid #ef4444',
          borderRadius: '8px',
        }}>
          {error}
        </div>
      )}

      {serverInfo && (
        <div style={{
          padding: '1.5rem',
          marginBottom: '2rem',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '12px',
          backdropFilter: 'blur(10px)',
        }}>
          <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', fontSize: '1.1rem' }}>
            📊 Ring Buffer Configuration
          </div>
          <div style={{ lineHeight: '1.8' }}>
            <div>Frame: {serverInfo.width}x{serverInfo.height} RGB ({frameSizeMB.toFixed(2)} MB)</div>
            <div>Capacity: {serverInfo.capacity} frames</div>
            <div>Total Size: {(serverInfo.total_size / (1024 * 1024)).toFixed(1)} MB</div>
            <details style={{ marginTop: '0.5rem' }}>
              <summary style={{ cursor: 'pointer', opacity: 0.8 }}>
                📁 File Path
              </summary>
              <code style={{
                fontSize: '0.8rem',
                display: 'block',
                marginTop: '0.5rem',
                padding: '0.5rem',
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '4px',
                wordBreak: 'break-all'
              }}>
                {serverInfo.file_path}
              </code>
            </details>
          </div>
        </div>
      )}

      {isStreaming && stats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2rem',
        }}>
          {/* Main Performance Card */}
          <div style={{
            padding: '1.5rem',
            background: 'rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            backdropFilter: 'blur(10px)',
          }}>
            <div style={{
              fontSize: '0.9rem',
              opacity: 0.9,
              marginBottom: '0.5rem',
              fontWeight: '600'
            }}>
              RUST READ PERFORMANCE
            </div>
            <div style={{
              fontSize: '3rem',
              fontWeight: 'bold',
              lineHeight: '1'
            }}>
              {stats.rustReadFps.toFixed(1)}
            </div>
            <div style={{ opacity: 0.8, marginTop: '0.25rem' }}>FPS</div>
          </div>

          {/* Metrics Grid */}
          <div style={{
            padding: '1.5rem',
            background: 'rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            backdropFilter: 'blur(10px)',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '1rem',
          }}>
            <div>
              <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Decode FPS</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                {stats.rustDecodeFps.toFixed(1)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Server FPS</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                {stats.latestServerFps.toFixed(1)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Bandwidth</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                {(stats.rustReadFps * frameSizeMB).toFixed(1)} MB/s
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Total Frames</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                {stats.rustFrameCount.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Frame Tracking Card */}
          <div style={{
            padding: '1.5rem',
            background: 'rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            backdropFilter: 'blur(10px)',
            gridColumn: 'span 2',
          }}>
            <div style={{
              fontSize: '0.9rem',
              opacity: 0.9,
              marginBottom: '1rem',
              fontWeight: '600'
            }}>
              FRAME TRACKING
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '1rem',
            }}>
              <div>
                <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Current Frame</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
                  #{stats.latestFrameNumber}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Latest Available</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
                  #{stats.serverLatestFrameNumber}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>Lag</div>
                <div style={{
                  fontSize: '1.8rem',
                  fontWeight: 'bold',
                  color: lag > 10 ? '#fbbf24' : lag > 50 ? '#ef4444' : '#10b981'
                }}>
                  {lag} frames
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Canvas Display */}
      {currentFrame && (
        <div style={{
          marginTop: '2rem',
          padding: '1.5rem',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '12px',
          backdropFilter: 'blur(10px)',
        }}>
          <div style={{
            marginBottom: '1rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div>
              <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>
                🎬 Live Frame Display
              </div>
              <div style={{ fontSize: '0.9rem', opacity: 0.8, marginTop: '0.25rem' }}>
                Frame #{currentFrame.frameNumber} •
                {currentFrame.checksumValid ? ' ✅ Valid' : ' ⚠️ Invalid Checksum'}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <input
                type="number"
                placeholder="Frame #"
                style={{
                  padding: '0.5rem',
                  borderRadius: '4px',
                  border: 'none',
                  marginRight: '0.5rem',
                  width: '100px'
                }}
                onKeyPress={(e): void => {
                  if (e.key === 'Enter') {
                    const value = parseInt((e.target as HTMLInputElement).value)
                    if (!isNaN(value)) {
                      requestSpecificFrame(value)
                    }
                  }
                }}
              />
              <button
                onClick={(): void => {
                  const input = document.querySelector('input[type="number"]') as HTMLInputElement
                  const value = parseInt(input.value)
                  if (!isNaN(value)) {
                    requestSpecificFrame(value)
                  }
                }}
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '4px',
                  border: 'none',
                  background: '#4facfe',
                  color: 'white',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                Request Frame
              </button>
            </div>
          </div>
          <canvas
            ref={canvasRef}
            style={{
              width: '100%',
              height: 'auto',
              border: '2px solid rgba(255,255,255,0.3)',
              borderRadius: '8px',
            }}
          />
        </div>
      )}

      {!isStreaming && (
        <div style={{
          padding: '3rem',
          textAlign: 'center',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '12px',
          backdropFilter: 'blur(10px)',
          fontSize: '1.2rem',
          opacity: 0.8,
        }}>
          {serverInfo ? 'Click "Start" to begin streaming' : 'Connecting to server...'}
        </div>
      )}

      {/* Status Indicator */}
      {isStreaming && stats && (
        <div style={{
          marginTop: '2rem',
          padding: '1rem',
          textAlign: 'center',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          backdropFilter: 'blur(10px)',
        }}>
          {stats.rustReadFps > 500 ? (
            <span style={{ color: '#10b981', fontWeight: 'bold' }}>
              ✅ Excellent Performance (500+ FPS)
            </span>
          ) : stats.rustReadFps > 200 ? (
            <span style={{ color: '#10b981', fontWeight: 'bold' }}>
              ✅ Good Performance (200+ FPS)
            </span>
          ) : stats.rustReadFps > 100 ? (
            <span style={{ color: '#fbbf24', fontWeight: 'bold' }}>
              ⚡ Decent Performance (100+ FPS)
            </span>
          ) : (
            <span style={{ color: '#ef4444', fontWeight: 'bold' }}>
              ⚠️ Low Performance
            </span>
          )}
          {lag > 50 && (
            <span style={{ color: '#ef4444', fontWeight: 'bold', marginLeft: '1rem' }}>
              • ⚠️ High lag detected!
            </span>
          )}
        </div>
      )}
    </div>
  )
}