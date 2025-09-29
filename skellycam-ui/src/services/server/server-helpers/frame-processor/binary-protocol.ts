// binary-protocol.ts
/**
 * Binary protocol definition for frame payloads
 * All offsets and sizes are in bytes
 */

// Message type constants
export const MESSAGE_TYPE = {
    PAYLOAD_HEADER: 0,
    FRAME_METADATA: 1,
    PAYLOAD_FOOTER: 2,
} as const;

// Field sizes (in bytes)
const FIELD_SIZES = {
    // Primitive types
    U1: 1,      // unsigned 8-bit
    I4: 4,      // signed 32-bit integer
    I8: 8,      // signed 64-bit integer
    F4: 4,      // 32-bit float
    BOOL: 1,    // boolean

    // String types (numpy dtypes)
    U128: 512,  // 128 unicode chars (4 bytes per char in numpy UTF-32)
    S4: 4,      // 4-byte ASCII string
    S8: 8,      // 8-byte ASCII string
    S32: 32,    // 32-byte ASCII string
} as const;

// Camera config field definitions with offsets
export const CAMERA_CONFIG_FIELDS = {
    camera_id:       { offset: 0,   size: FIELD_SIZES.U128, type: 'unicode' },
    camera_index:    { offset: 512, size: FIELD_SIZES.I4,   type: 'int32' },
    camera_name:     { offset: 516, size: FIELD_SIZES.U128, type: 'unicode' },
    use_this_camera: { offset: 1028, size: FIELD_SIZES.BOOL, type: 'bool' },

    // Align to 4-byte boundary after bool (padding: 3 bytes)
    resolution_height: { offset: 1032, size: FIELD_SIZES.I4, type: 'int32' },
    resolution_width:  { offset: 1036, size: FIELD_SIZES.I4, type: 'int32' },
    color_channels:    { offset: 1040, size: FIELD_SIZES.I4, type: 'int32' },

    pixel_format:   { offset: 1044, size: FIELD_SIZES.S8,  type: 'ascii' },
    exposure_mode:  { offset: 1052, size: FIELD_SIZES.S32, type: 'ascii' },
    exposure:       { offset: 1084, size: FIELD_SIZES.I4,  type: 'int32' },
    framerate:      { offset: 1088, size: FIELD_SIZES.F4,  type: 'float32' },
    rotation:       { offset: 1092, size: FIELD_SIZES.I4,  type: 'int32' },
    capture_fourcc: { offset: 1096, size: FIELD_SIZES.S4,  type: 'ascii' },
    writer_fourcc:  { offset: 1100, size: FIELD_SIZES.S4,  type: 'ascii' },
} as const;

// Calculate total size of camera config (aligned to 4-byte boundary)
export const CAMERA_CONFIG_SIZE = Math.ceil(1104 / 4) * 4; // 1104 bytes

// Payload header structure
export const PAYLOAD_HEADER_FIELDS = {
    message_type:      { offset: 0, size: FIELD_SIZES.U1, type: 'uint8' },
    frame_number:      { offset: 1, size: FIELD_SIZES.I8, type: 'int64' },
    number_of_cameras: { offset: 9, size: FIELD_SIZES.I4, type: 'int32' },
} as const;

export const PAYLOAD_HEADER_SIZE = 13; // Total: 1 + 8 + 4

// Frame header structure (with embedded config)
export const FRAME_HEADER_FIELDS = {
    message_type:      { offset: 0,                              size: FIELD_SIZES.U1,         type: 'uint8' },
    frame_number:      { offset: 1,                              size: FIELD_SIZES.I8,         type: 'int64' },
    camera_config:     { offset: 9,                              size: CAMERA_CONFIG_SIZE,     type: 'config' },
    image_width:       { offset: 9 + CAMERA_CONFIG_SIZE,         size: FIELD_SIZES.I4,         type: 'int32' },
    image_height:      { offset: 9 + CAMERA_CONFIG_SIZE + 4,     size: FIELD_SIZES.I4,         type: 'int32' },
    jpeg_string_length: { offset: 9 + CAMERA_CONFIG_SIZE + 8,    size: FIELD_SIZES.I4,         type: 'int32' },
} as const;

export const FRAME_HEADER_SIZE = 9 + CAMERA_CONFIG_SIZE + 12; // Total header size

// Helper type definitions
export type FieldType = 'uint8' | 'int32' | 'int64' | 'float32' | 'bool' | 'unicode' | 'ascii' | 'config';

export interface FieldDefinition {
    offset: number;
    size: number;
    type: FieldType;
}

// Protocol validation constants
export const PROTOCOL_LIMITS = {
    MAX_CAMERAS: 100,
    MAX_FRAME_SIZE: 10 * 1024 * 1024, // 10MB
    MAX_STRING_LENGTH: 512,
} as const;

// Rotation value mapping
export const ROTATION_VALUES = {
    0: '90',
    1: '180',
    2: '270',
    [-1]: 'None',
} as const;

export type RotationOption = 'None' | '90' | '180' | '270';
