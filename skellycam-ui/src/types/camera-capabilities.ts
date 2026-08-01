export interface CameraResolution {
  width: number;
  height: number;
}

export interface CameraFrameRate {
  min: number;
  max: number;
  values?: number[];
}

export type CameraPixelFormat = 
  | 'MJPG' 
  | 'YUY2' 
  | 'NV12' 
  | 'RGB24' 
  | 'BGR24' 
  | 'GRAY8' 
  | 'UYVY' 
  | string;

export interface CameraVideoMode {
  resolution: CameraResolution;
  framerates: CameraFrameRate | number[];
  pixelFormat: CameraPixelFormat;
}

export interface CameraDeviceProperties {
  deviceId: string;
  deviceName: string;
  manufacturer?: string;
  model?: string;
  serialNumber?: string;
  location?: string;
}

export interface CameraCapabilities {
  deviceProperties: CameraDeviceProperties;
  videoModes: CameraVideoMode[];
  currentSettings?: {
    resolution: CameraResolution;
    framerate: number;
    pixelFormat: CameraPixelFormat;
  };
  supportedFeatures?: {
    hardwareTrigger: boolean;
    softwareTrigger: boolean;
    autoFocus: boolean;
    manualFocus: boolean;
    autoExposure: boolean;
    manualExposure: boolean;
  };
}
