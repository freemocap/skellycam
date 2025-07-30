import {CurrentFramerateSchema} from "@/store/slices/framerateTrackerSlice";
import {z} from 'zod'

export const BaseWebsocketMessageSchema = z.object({
    message_type: z.string(),
});
// Framerate update message schema
export const FramerateUpdateWebsocketMessageSchema = BaseWebsocketMessageSchema.extend({
    message_type: z.literal("framerate_update"),
    camera_group_id: z.string(),
    backend_framerate: CurrentFramerateSchema,
    frontend_framerate: CurrentFramerateSchema,
});
// Add more message schemas as needed
// const OtherMessageTypeSchema = BaseMessageSchema.extend({
//     message_type: z.literal("other_message_type"),
//     // other fields...
// });

// Union of all message types
export const WebSocketMessageSchema = z.discriminatedUnion("message_type", [
    FramerateUpdateWebsocketMessageSchema,
    // Add more message schemas to the union as needed
]);

export type WebSocketMessage = z.infer<typeof WebSocketMessageSchema>;
export type FramerateUpdateWebSocketMessage = z.infer<typeof FramerateUpdateWebsocketMessageSchema>;
