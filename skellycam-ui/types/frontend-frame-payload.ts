class FrameLifespanTimestamps {
    initializedTimestampNs: number;
    preGrabTimestampNs: number;
    postGrabTimestampNs: number;
    preRetrieveTimestampNs: number;
    postRetrieveTimestampNs: number;
    copyToBufferTimestampNs: number;
    copyFromBufferTimestampNs: number;
    startAnnotateImageTimestampNs: number;
    endAnnotateImageTimestampNs: number;
    startCompressToJpegTimestampNs: number;
    endCompressToJpegTimestampNs: number;

    constructor(data: any) {
        this.initializedTimestampNs = data.initializedTimestampNs;
        this.preGrabTimestampNs = data.preGrabTimestampNs;
        this.postGrabTimestampNs = data.postGrabTimestampNs;
        this.preRetrieveTimestampNs = data.preRetrieveTimestampNs;
        this.postRetrieveTimestampNs = data.postRetrieveTimestampNs;
        this.copyToBufferTimestampNs = data.copyToBufferTimestampNs;
        this.copyFromBufferTimestampNs = data.copyFromBufferTimestampNs;
        this.startAnnotateImageTimestampNs = data.startAnnotateImageTimestampNs;
        this.endAnnotateImageTimestampNs = data.endAnnotateImageTimestampNs;
        this.startCompressToJpegTimestampNs = data.startCompressToJpegTimestampNs;
        this.endCompressToJpegTimestampNs = data.endCompressToJpegTimestampNs;
    }
}


class FrameMetadata {
    cameraId: number;
    frameNumber: number;
    frameLifespanTimestampsNs: FrameLifespanTimestamps;

    constructor(data: any) {
        this.cameraId = data.cameraId;
        this.frameNumber = data.frameNumber;
        this.frameLifespanTimestampsNs = new FrameLifespanTimestamps(data.frameLifespanTimestampsNs);
    }
}


class UtcToPerfCounterMapping {
    utcTimeNs: number;
    perfCounterNs: number;

    constructor(data: any) {
        this.utcTimeNs = data.utcTimeNs;
        this.perfCounterNs = data.perfCounterNs;
    }

    convertPerfCounterNsToUnixNs(perfCounterNs: number): number {
        return this.utcTimeNs + (perfCounterNs - this.perfCounterNs);
    }
}


class MultiFrameMetadata {
    frameNumber: number;
    frameMetadataByCamera: { [key: string]: FrameMetadata };
    utcNsToPerfNs: UtcToPerfCounterMapping;
    multiFrameLifespanTimestampsNs: Array<{ [key: string]: number }>;

    constructor(data: any) {
        this.frameNumber = data.frameNumber;
        this.frameMetadataByCamera = {};
        for (const key in data.frameMetadataByCamera) {
            this.frameMetadataByCamera[key] = new FrameMetadata(data.frameMetadataByCamera[key]);
        }
        this.utcNsToPerfNs = new UtcToPerfCounterMapping(data.utcNsToPerfNs);
        this.multiFrameLifespanTimestampsNs = data.multiFrameLifespanTimestampsNs;
    }
}


export class FrontendFramePayload {
    jpegImages: { [key: string]: string | null };
    multiFrameMetadata: MultiFrameMetadata;
    lifespanTimestampsNs: Array<{ [key: string]: number }>;
    utcNsToPerfNs: UtcToPerfCounterMapping;
    multiFrameNumber: number;

    constructor(data: any) {
        this.jpegImages = data.jpegImages;
        this.multiFrameMetadata = new MultiFrameMetadata(data.multiFrameMetadata);
        this.lifespanTimestampsNs = data.lifespanTimestampsNs;
        this.utcNsToPerfNs = new UtcToPerfCounterMapping(data.utcNsToPerfNs);
        this.multiFrameNumber = data.multiFrameNumber;
    }
}