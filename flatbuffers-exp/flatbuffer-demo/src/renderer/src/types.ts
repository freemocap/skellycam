import { z } from 'zod'

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

export type SharedMemoryData = z.infer<typeof SharedMemoryDataSchema>

export const ServerInfoSchema = z.object({
  file_path: z.string(),
  size: z.number()
})

export const WebSocketMessageSchema = z.object({
  type: z.string(),
  sequence: z.number().optional()
})

export interface SharedMemoryContextType {
  data: SharedMemoryData | null
  connected: boolean
  error: string | null
  filePath: string | null
}
