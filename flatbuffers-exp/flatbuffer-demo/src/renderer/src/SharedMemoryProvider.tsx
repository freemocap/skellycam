/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
import * as flatbuffers from 'flatbuffers'
import { SharedData } from './generated/message_generated'
import {
  SharedMemoryData,
  ServerInfoSchema,
  WebSocketMessageSchema,
  SharedMemoryDataSchema
} from './types'

interface SharedMemoryContextType {
  data: SharedMemoryData | null
  connected: boolean
  error: string | null
  filePath: string | null
  fps: number
}

const SharedMemoryContext = createContext<SharedMemoryContextType>({
  data: null,
  connected: false,
  error: null,
  filePath: null,
  fps: 0
})

export const useSharedMemory = (): SharedMemoryContextType => useContext(SharedMemoryContext)

export const SharedMemoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<SharedMemoryData | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filePath, setFilePath] = useState<string | null>(null)
  const [fps, setFps] = useState(0)

  const ws = useRef<WebSocket | null>(null)
  const frameTimesRef = useRef<number[]>([])
  const lastFrameTimeRef = useRef<number>(0)

  const calculateFps = useCallback((): void => {
    const now = performance.now()

    if (lastFrameTimeRef.current > 0) {
      const frameTime = now - lastFrameTimeRef.current
      frameTimesRef.current.push(frameTime)

      // Keep only last 30 frames
      if (frameTimesRef.current.length > 30) {
        frameTimesRef.current.shift()
      }

      // Calculate FPS
      if (frameTimesRef.current.length >= 2) {
        const avgFrameTime =
          frameTimesRef.current.reduce((a, b) => a + b, 0) / frameTimesRef.current.length
        setFps(1000 / avgFrameTime)
      }
    }

    lastFrameTimeRef.current = now
  }, [])

  const readSharedFile = useCallback((): void => {
    if (!filePath) {
      return
    }

    try {
      // Read the file directly - no existence check (save syscall)
      const fileBuffer = window.electronAPI.readFile(filePath)
      const uint8Array = fileBuffer instanceof Uint8Array ? fileBuffer : new Uint8Array(fileBuffer)

      // Read size as little-endian uint32 (first 4 bytes)
      const dataView = new DataView(uint8Array.buffer, uint8Array.byteOffset, uint8Array.byteLength)
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
        const pixelSample: number[] = []
        for (let i = 0; i < Math.min(10, frame.pixelsLength()); i++) {
          pixelSample.push(frame.pixels(i) ?? 0)
        }

        const newData = {
          sequence: Number(message.sequence()),
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

        // Calculate FPS
        calculateFps()

        // Send acknowledgment immediately
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(
            JSON.stringify({
              type: 'ack',
              sequence: validated.sequence
            })
          )
        }
      }
    } catch (err) {
      console.error('❌ Error reading shared file:', err)
      setError(`Read error: ${err}`)
    }
  }, [filePath, calculateFps])

  useEffect((): (() => void) => {
    const init = async (): Promise<void> => {
      try {
        const response = await fetch('http://localhost:8009/info')
        const rawInfo = await response.json()
        const info = ServerInfoSchema.parse(rawInfo)

        setFilePath(info.file_path)

        ws.current = new WebSocket('ws://localhost:8009/ws')

        ws.current.onopen = (): void => {
          console.log('✅ WebSocket connected')
          setConnected(true)
          setError(null)
        }

        ws.current.onmessage = (event): void => {
          try {
            const rawMsg = JSON.parse(event.data)
            const msg = WebSocketMessageSchema.parse(rawMsg)

            if (msg.type === 'frame_ready') {
              // New frame is ready, read it
              readSharedFile()
            }
          } catch (err) {
            console.error('❌ Error processing message:', err)
          }
        }

        ws.current.onerror = (): void => {
          setError('WebSocket error')
          setConnected(false)
        }

        ws.current.onclose = (): void => {
          console.log('🔌 WebSocket closed')
          setConnected(false)
        }
      } catch (err) {
        setError(`Failed to initialize: ${err}`)
      }
    }

    init()

    return (): void => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [readSharedFile])

  return (
    <SharedMemoryContext.Provider value={{ data, connected, error, filePath, fps }}>
      {children}
    </SharedMemoryContext.Provider>
  )
}
