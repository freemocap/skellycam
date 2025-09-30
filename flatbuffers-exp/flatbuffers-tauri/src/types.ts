import { z } from 'zod'

export interface SharedMemoryData {
  sequence: number
  cameraId: number
  frameNumber: number
  timestamp: number
  fps: number
  cpuUsage: number
  message: string
  pixelSample: number[]
}

export interface FrameData {
  buffer: number[]
  mainReadFps: number
  mainReadFrameCount: number
  mainTotalBytesRead: number
}

export const ServerInfoSchema = z.object({
  file_path: z.string(),
  size: z.number(),
  width: z.number().optional(),
  height: z.number().optional()
})

export const SharedMemoryDataSchema = z.object({
  sequence: z.number(),
  cameraId: z.number(),
  frameNumber: z.number(),
  timestamp: z.number(),
  fps: z.number(),
  cpuUsage: z.number(),
  message: z.string(),
  pixelSample: z.array(z.number())
})

export type ServerInfo = z.infer<typeof ServerInfoSchema>