/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
import * as flatbuffers from 'flatbuffers'
import { SharedData } from './generated/message_generated'
import { SharedMemoryData, ServerInfoSchema, SharedMemoryDataSchema } from './types'

interface SharedMemoryContextType {
  data: SharedMemoryData | null
  error: string | null
  filePath: string | null
  serverInfo: {
    width: number
    height: number
    size: number
  } | null
  // Main process metrics (from electron main)
  mainReadFps: number
  mainReadFrameCount: number
  mainTotalBytesRead: number
  // Renderer process metrics (this React app)
  rendererProcessedFps: number
  rendererProcessedFrameCount: number
  rendererDisplayFps: number
  rendererTotalBytesProcessed: number
  // Server-side metrics (from the frame data)
  serverWriteFps: number
  isStreaming: boolean
  startStreaming: () => Promise<void>
  stopStreaming: () => Promise<void>
  // Performance tuning
  frameSamplingRate: number
  setFrameSamplingRate: (rate: number) => void
}

const SharedMemoryContext = createContext<SharedMemoryContextType>({
  data: null,
  error: null,
  filePath: null,
  serverInfo: null,
  mainReadFps: 0,
  mainReadFrameCount: 0,
  mainTotalBytesRead: 0,
  rendererProcessedFps: 0,
  rendererProcessedFrameCount: 0,
  rendererDisplayFps: 0,
  rendererTotalBytesProcessed: 0,
  serverWriteFps: 0,
  isStreaming: false,
  startStreaming: async () => {},
  stopStreaming: async () => {},
  frameSamplingRate: 1,
  setFrameSamplingRate: () => {}
})

export const useSharedMemory = (): SharedMemoryContextType => useContext(SharedMemoryContext)

export const SharedMemoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<SharedMemoryData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filePath, setFilePath] = useState<string | null>(null)
  const [serverInfo, setServerInfo] = useState<{
    width: number
    height: number
    size: number
  } | null>(null)

  // Main process metrics (received from IPC)
  const [mainReadFps, setMainReadFps] = useState(0)
  const [mainReadFrameCount, setMainReadFrameCount] = useState(0)
  const [mainTotalBytesRead, setMainTotalBytesRead] = useState(0)

  // Renderer process metrics (tracked here)
  const [rendererProcessedFps, setRendererProcessedFps] = useState(0)
  const [rendererProcessedFrameCount, setRendererProcessedFrameCount] = useState(0)
  const [rendererDisplayFps, setRendererDisplayFps] = useState(0)
  const [rendererTotalBytesProcessed, setRendererTotalBytesProcessed] = useState(0)

  // Server-side metrics
  const [serverWriteFps, setServerWriteFps] = useState(0)
  const [isStreaming, setIsStreaming] = useState(false)

  // Performance tuning
  const [frameSamplingRate, setFrameSamplingRate] = useState(1) // 1 = process every frame, 2 = every other, etc.

  const lastFrameSequence = useRef<number>(-1)
  const processedFrameTimesRef = useRef<number[]>([])
  const lastProcessedFrameTimeRef = useRef<number>(0)
  const displayFrameTimesRef = useRef<number[]>([])
  const lastDisplayFrameTimeRef = useRef<number>(0)
  const framesSinceLastDisplay = useRef<number>(0)

  const calculateRendererProcessedFps = useCallback((): void => {
    const now = performance.now()

    if (lastProcessedFrameTimeRef.current > 0) {
      const frameTime = now - lastProcessedFrameTimeRef.current
      processedFrameTimesRef.current.push(frameTime)

      if (processedFrameTimesRef.current.length > 100) {
        processedFrameTimesRef.current.shift()
      }

      if (processedFrameTimesRef.current.length >= 2) {
        const avgFrameTime =
          processedFrameTimesRef.current.reduce((a: number, b: number) => a + b, 0) /
          processedFrameTimesRef.current.length
        setRendererProcessedFps(1000 / avgFrameTime)
      }
    }

    lastProcessedFrameTimeRef.current = now
  }, [])

  const calculateRendererDisplayFps = useCallback((): void => {
    const now = performance.now()

    if (lastDisplayFrameTimeRef.current > 0) {
      const frameTime = now - lastDisplayFrameTimeRef.current
      displayFrameTimesRef.current.push(frameTime)

      if (displayFrameTimesRef.current.length > 100) {
        displayFrameTimesRef.current.shift()
      }

      if (displayFrameTimesRef.current.length >= 2) {
        const avgFrameTime =
          displayFrameTimesRef.current.reduce((a: number, b: number) => a + b, 0) /
          displayFrameTimesRef.current.length
        setRendererDisplayFps(1000 / avgFrameTime)
      }
    }

    lastDisplayFrameTimeRef.current = now
  }, [])

  const processFrameData = useCallback(
    (frameData: {
      buffer: Buffer
      mainReadFps: number
      mainReadFrameCount: number
      mainTotalBytesRead: number
    }): void => {
      try {
        // Update main process metrics
        setMainReadFps(frameData.mainReadFps)
        setMainReadFrameCount(frameData.mainReadFrameCount)
        setMainTotalBytesRead(frameData.mainTotalBytesRead)

        // Count processed frames (every frame that comes from main process)
        setRendererProcessedFrameCount((prev) => prev + 1)
        calculateRendererProcessedFps()

        // Apply frame sampling for display updates
        framesSinceLastDisplay.current++
        if (framesSinceLastDisplay.current < frameSamplingRate) {
          return // Skip this frame for display
        }
        framesSinceLastDisplay.current = 0

        const uint8Array = new Uint8Array(frameData.buffer)

        // Read size as little-endian uint32 (first 4 bytes)
        const dataView = new DataView(
          uint8Array.buffer,
          uint8Array.byteOffset,
          uint8Array.byteLength
        )
        const size = dataView.getUint32(0, true)

        if (size === 0 || size > uint8Array.length - 4) {
          return
        }

        // Extract the FlatBuffer data (skip first 4 bytes)
        const dataBuffer = uint8Array.subarray(4, 4 + size)

        // Parse FlatBuffer
        const buf = new flatbuffers.ByteBuffer(dataBuffer)
        const message = SharedData.SharedMessage.getRootAsSharedMessage(buf)

        // Verify magic number
        if (message.magic() !== 0xdeadbeef) {
          return
        }

        const frame = message.frame()
        const status = message.status()

        if (frame && status) {
          const sequence = Number(message.sequence())

          // Check if this is a new frame (avoid processing duplicates)
          if (sequence === lastFrameSequence.current) {
            return
          }
          lastFrameSequence.current = sequence

          const pixelSample: number[] = []
          for (let i = 0; i < Math.min(10, frame.pixelsLength()); i++) {
            pixelSample.push(frame.pixels(i) ?? 0)
          }

          const newData = {
            sequence,
            cameraId: frame.cameraId(),
            frameNumber: frame.frameNumber(),
            timestamp: Number(frame.timestamp()),
            fps: status.fps(),
            cpuUsage: status.cpuUsage(),
            message: status.message() || '',
            pixelSample
          }

          const validated = SharedMemoryDataSchema.parse(newData)
          setData(validated)

          // Update server-side FPS from the frame
          setServerWriteFps(validated.fps)

          // Track display FPS (only when we actually update the UI)
          calculateRendererDisplayFps()

          // Track renderer bytes processed
          setRendererTotalBytesProcessed((prev) => prev + size + 4)
        }
      } catch (err) {
        console.error('❌ Error processing frame:', err)
        setError(`Processing error: ${err}`)
      }
    },
    [calculateRendererProcessedFps, calculateRendererDisplayFps, frameSamplingRate]
  )

  const startStreaming = useCallback(async (): Promise<void> => {
    if (!filePath) {
      setError('No file path available')
      return
    }

    try {
      // Reset metrics
      setRendererProcessedFrameCount(0)
      setRendererTotalBytesProcessed(0)
      processedFrameTimesRef.current = []
      displayFrameTimesRef.current = []
      lastProcessedFrameTimeRef.current = 0
      lastDisplayFrameTimeRef.current = 0
      framesSinceLastDisplay.current = 0

      // Tell server to start
      await fetch('http://localhost:8009/start', { method: 'POST' })

      // Start file reader in main process (1ms poll rate = ~1000 reads/sec max)
      await window.electronAPI.startFileReader(filePath, 1)

      setIsStreaming(true)
      setError(null)

      console.log('✅ Streaming started')
      console.log('📊 Tracking 3 separate FPS metrics:')
      console.log('   1. Server Write FPS (Python process)')
      console.log('   2. Main Process Read FPS (Electron main)')
      console.log('   3. Renderer Display FPS (React UI)')
    } catch (err) {
      setError(`Failed to start streaming: ${err}`)
    }
  }, [filePath])

  const stopStreaming = useCallback(async (): Promise<void> => {
    try {
      // Tell server to stop
      await fetch('http://localhost:8009/stop', { method: 'POST' })

      // Stop file reader
      await window.electronAPI.stopFileReader()

      setIsStreaming(false)

      console.log('🛑 Streaming stopped')
    } catch (err) {
      setError(`Failed to stop streaming: ${err}`)
    }
  }, [])

  useEffect((): (() => void) => {
    const init = async (): Promise<void> => {
      try {
        // Get server info
        const response = await fetch('http://localhost:8009/info')
        const rawInfo = await response.json()
        const info = ServerInfoSchema.parse(rawInfo)

        setFilePath(info.file_path)
        setServerInfo({
          width: info.width || 1280,
          height: info.height || 720,
          size: info.size
        })

        // Set up frame data listener
        window.electronAPI.onFrameData(processFrameData)

        console.log('✅ Initialized, ready to stream')
        console.log('📂 File path:', info.file_path)
      } catch (err) {
        setError(`Failed to initialize: ${err}`)
      }
    }

    init()

    return (): void => {
      window.electronAPI.removeFrameDataListener()
      stopStreaming()
    }
  }, [processFrameData, stopStreaming])

  return (
    <SharedMemoryContext.Provider
      value={{
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
      }}
    >
      {children}
    </SharedMemoryContext.Provider>
  )
}
