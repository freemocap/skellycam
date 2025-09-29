/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
import * as flatbuffers from 'flatbuffers'
import { SharedData } from './generated/message_generated'
import {
  SharedMemoryContextType,
  SharedMemoryData,
  ServerInfoSchema,
  WebSocketMessageSchema,
  SharedMemoryDataSchema
} from './types'

const SharedMemoryContext = createContext<SharedMemoryContextType>({
  data: null,
  connected: false,
  error: null,
  filePath: null
})

export const useSharedMemory = (): SharedMemoryContextType => useContext(SharedMemoryContext)

export const SharedMemoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<SharedMemoryData | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filePath, setFilePath] = useState<string | null>(null)

  const ws = useRef<WebSocket | null>(null)

  const readSharedFile = useCallback((): void => {
    if (!filePath) {
      console.log('🔍 [readSharedFile] No file path set yet, skipping read')
      return
    }

    console.log('📖 [readSharedFile] Starting to read shared file:', filePath)

    try {
      // Check if file exists
      if (!window.electronAPI.fileExists(filePath)) {
        console.warn('⚠️ [readSharedFile] File does not exist yet:', filePath)
        return
      }
      console.log('✅ [readSharedFile] File exists, reading contents...')

      // Read the file
      const fileBuffer = window.electronAPI.readFile(filePath)
      console.log('📦 [readSharedFile] Raw file buffer received:', {
        type: fileBuffer.constructor.name,
        length: fileBuffer.length || fileBuffer.byteLength,
        isUint8Array: fileBuffer instanceof Uint8Array,
        isArrayBuffer: fileBuffer instanceof ArrayBuffer
      })

      // Convert to Uint8Array if needed
      const uint8Array = fileBuffer instanceof Uint8Array ? fileBuffer : new Uint8Array(fileBuffer)
      console.log('🔄 [readSharedFile] Converted to Uint8Array:', {
        length: uint8Array.length,
        first16Bytes: Array.from(uint8Array.slice(0, 16))
      })

      // Read size as little-endian uint32 (first 4 bytes)
      const dataView = new DataView(uint8Array.buffer, uint8Array.byteOffset, uint8Array.byteLength)
      const size = dataView.getUint32(0, true) // true = little endian
      console.log('📏 [readSharedFile] Size prefix read:', {
        sizeBytes: size,
        totalFileBytes: uint8Array.length,
        availableDataBytes: uint8Array.length - 4
      })

      if (size === 0 || size > uint8Array.length - 4) {
        console.warn('⚠️ [readSharedFile] Invalid size detected:', {
          size,
          maxValidSize: uint8Array.length - 4,
          reason: size === 0 ? 'size is zero' : 'size exceeds buffer'
        })
        return
      }
      console.log('✅ [readSharedFile] Size validation passed')

      // Extract the FlatBuffer data (skip first 4 bytes which contain the size)
      const dataBuffer = uint8Array.subarray(4, 4 + size)
      console.log('🎯 [readSharedFile] Extracted FlatBuffer data:', {
        dataLength: dataBuffer.length,
        first16Bytes: Array.from(dataBuffer.slice(0, 16))
      })

      // Parse FlatBuffer
      const buf = new flatbuffers.ByteBuffer(dataBuffer)
      console.log('🔧 [readSharedFile] Created FlatBuffers ByteBuffer, getting root...')

      const message = SharedData.SharedMessage.getRootAsSharedMessage(buf)
      console.log('📨 [readSharedFile] Parsed SharedMessage:', {
        magic: '0x' + message.magic().toString(16),
        sequence: Number(message.sequence()),
        hasFrame: message.frame() !== null,
        hasStatus: message.status() !== null
      })

      // Verify magic number
      if (message.magic() !== 0xdeadbeef) {
        console.warn('⚠️ [readSharedFile] Invalid magic number:', {
          expected: '0xdeadbeef',
          actual: '0x' + message.magic().toString(16)
        })
        return
      }
      console.log('✅ [readSharedFile] Magic number verified')

      const frame = message.frame()
      const status = message.status()

      if (frame && status) {
        console.log('🎥 [readSharedFile] Frame data:', {
          cameraId: frame.cameraId(),
          frameNumber: frame.frameNumber(),
          timestamp: frame.timestamp(),
          width: frame.width(),
          height: frame.height(),
          pixelsLength: frame.pixelsLength()
        })

        console.log('📊 [readSharedFile] Status data:', {
          fps: status.fps(),
          cpuUsage: status.cpuUsage(),
          activeCameras: status.activeCameras(),
          message: status.message()
        })

        const pixelSample: number[] = []
        for (let i = 0; i < Math.min(10, frame.pixelsLength()); i++) {
          pixelSample.push(frame.pixels(i) ?? 0)
        }
        console.log('🎨 [readSharedFile] Pixel sample (first 10):', pixelSample)

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

        console.log('🔍 [readSharedFile] Validating data with Zod schema...')
        const validated = SharedMemoryDataSchema.parse(newData)
        console.log('✅ [readSharedFile] Data validated successfully:', validated)

        setData(validated)
        console.log('🎉 [readSharedFile] State updated with new data!')
      } else {
        console.warn('⚠️ [readSharedFile] Missing frame or status:', {
          hasFrame: frame !== null,
          hasStatus: status !== null
        })
      }
    } catch (err) {
      console.error('❌ [readSharedFile] Error reading shared file:', err)
      console.error('📍 [readSharedFile] Error stack:', (err as Error).stack)
      setError(`Read error: ${err}`)
    }
  }, [filePath])

  useEffect((): (() => void) => {
    console.log('🚀 [SharedMemoryProvider] Initializing...')

    const init = async (): Promise<void> => {
      try {
        console.log('🌐 [init] Fetching server info from http://localhost:8009/info')
        const response = await fetch('http://localhost:8009/info')
        console.log('📡 [init] Server response status:', response.status)

        const rawInfo = await response.json()
        console.log('📄 [init] Raw server info received:', rawInfo)

        const info = ServerInfoSchema.parse(rawInfo)
        console.log('✅ [init] Server info validated:', info)

        setFilePath(info.file_path)
        console.log('📁 [init] File path set to:', info.file_path)

        console.log('🔌 [init] Connecting to WebSocket at ws://localhost:8009/ws')
        ws.current = new WebSocket('ws://localhost:8009/ws')

        ws.current.onopen = (): void => {
          console.log('✅ [WebSocket] Connection opened successfully!')
          setConnected(true)
          setError(null)
        }

        ws.current.onmessage = (event): void => {
          console.log('📩 [WebSocket] Message received:', event.data)
          try {
            const rawMsg = JSON.parse(event.data)
            console.log('📦 [WebSocket] Parsed message:', rawMsg)

            const msg = WebSocketMessageSchema.parse(rawMsg)
            console.log('✅ [WebSocket] Message validated:', msg)

            if (msg.type === 'frame_update') {
              console.log(
                '🎬 [WebSocket] Frame update notification received, triggering file read...'
              )
              readSharedFile()
            } else {
              console.log('ℹ️ [WebSocket] Unknown message type:', msg.type)
            }
          } catch (err) {
            console.error('❌ [WebSocket] Error processing message:', err)
            console.error('📍 [WebSocket] Error details:', (err as Error).stack)
          }
        }

        ws.current.onerror = (err): void => {
          console.error('❌ [WebSocket] Error occurred:', err)
          setError('WebSocket error')
          setConnected(false)
        }

        ws.current.onclose = (): void => {
          console.log('🔌 [WebSocket] Connection closed')
          setConnected(false)
        }
      } catch (err) {
        const errorMsg = `Failed to initialize: ${err}`
        console.error('❌ [init] Initialization failed:', err)
        console.error('📍 [init] Error details:', (err as Error).stack)
        setError(errorMsg)
      }
    }

    init()

    return (): void => {
      console.log('🧹 [SharedMemoryProvider] Cleaning up, closing WebSocket...')
      if (ws.current) {
        ws.current.close()
        console.log('✅ [SharedMemoryProvider] WebSocket closed')
      }
    }
  }, [readSharedFile])

  console.log('🎨 [SharedMemoryProvider] Rendering with state:', {
    hasData: data !== null,
    connected,
    hasError: error !== null,
    filePath
  })

  return (
    <SharedMemoryContext.Provider value={{ data, connected, error, filePath }}>
      {children}
    </SharedMemoryContext.Provider>
  )
}
