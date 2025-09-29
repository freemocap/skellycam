import { z } from 'zod'

// Zod schemas for runtime validation
export const ServerInfoSchema = z.object({
  file_path: z.string(),
  size: z.number()
})

export const WebSocketMessageSchema = z.object({
  type: z.literal('frame_update'),
  sequence: z.number(),
  timestamp: z.number()
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

// TypeScript types derived from Zod schemas
export type ServerInfo = z.infer<typeof ServerInfoSchema>
export type WebSocketMessage = z.infer<typeof WebSocketMessageSchema>
export type SharedMemoryData = z.infer<typeof SharedMemoryDataSchema>

// Additional types
export interface SharedMemoryContextType {
  data: SharedMemoryData | null
  connected: boolean
  error: string | null
  filePath: string | null
}
