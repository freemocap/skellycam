import { Tip } from '@freemocap/skellydocs';
import type { SkellyDocsConfig } from '@freemocap/skellydocs';

const config: SkellyDocsConfig = {
  hero: {
    title: 'Skelly',
    accentedSuffix: 'Cam',
    subtitle: 'The camera backend for FreeMoCap',
    tagline: 'Frame-perfect multi-camera synchronization for USB webcams',
    logoSrc: '/skellycam/img/skellycam-logo.svg',
    parentProject: {
      name: 'FreeMoCap',
      url: 'https://freemocap.org',
    },
  },

  features: [
    {
      id: 'frame-perfect-sync',
      icon: '🔒',
      title: 'Frame-Perfect Sync',
      description:
        'A frame-count-gated capture protocol ensures all cameras stay in lock-step with identical frame counts.',
      summary: (
        <>
          A{' '}
          <Tip text="Each camera's grab cycle is gated on relative frame counts so no camera ever gets ahead of the others">
            frame-count-gated capture protocol
          </Tip>{' '}
          ensures all cameras stay in lock-step. The OpenCV grab/retrieve split
          minimizes inter-camera timing spread so every recorded video has{' '}
          <strong>identical frame counts</strong> — no drift, no dropped frames.
        </>
      ),
      issues: [
        { label: 'Hardware synchronization (external trigger)', url: "https://github.com/freemocap/skellydocs/issues/1" },
        { label: 'Target frame rate setting', url: "https://github.com/freemocap/skellydocs/issues/2" },
        { label: 'Sub-frame synchronization', url: "https://github.com/freemocap/skellydocs/issues/3" },
      ],
      docPath: 'core/frame-perfect-sync',
    },
    {
      id: 'generic-usb-cameras',
      icon: '🎥',
      title: 'Generic USB Cameras',
      description:
        'Works with any standard UVC-compliant USB webcam. No proprietary hardware needed.',
      summary: (
        <>
          SkellyCam works with <strong>any standard USB webcam</strong>. If your
          camera is{' '}
          <Tip text="USB Video Class — the standard protocol used by virtually all USB webcams, no special drivers needed">
            UVC-compliant
          </Tip>
          , it will work out of the box. No proprietary hardware, no special
          drivers — grab whatever cameras you have and start capturing.
        </>
      ),
      issues: [
        { label: 'OpenCV VideoCapture backend alternatives', url: "https://github.com/freemocap/skellydocs/issues/4" },
        { label: 'Support for non-UVC camera backends', url: "https://github.com/freemocap/skellydocs/issues/5" },
        { label: 'Camera capability auto-detection', url: "https://github.com/freemocap/skellydocs/issues/6" },
      ],
      docPath: 'core/generic-usb-cameras',
    },
    {
      id: 'real-time-streaming',
      icon: '📡',
      title: 'Real-Time Streaming',
      description:
        'WebSocket protocol streams multi-camera frames to the frontend. The API treats a camera group like a single camera.',
      summary: (
        <>
          A compact binary{' '}
          <Tip text="Multi-camera frames are JPEG-compressed and packed into a single binary WebSocket message">
            WebSocket protocol
          </Tip>{' '}
          streams multi-camera frames to the React/Electron frontend with built-in
          backpressure management. The API treats a multi-camera group with the
          same expectations as a singular camera — a consistent frame rate
          delivering <strong>one image per camera per frame</strong>.
        </>
      ),
      issues: [
        { label: 'UDP transport for high-throughput streaming', url: "https://github.com/freemocap/skellydocs/issues/7"},
        { label: 'Python client library', url: "https://github.com/freemocap/skellydocs/issues/8"},
        { label: 'Remote streaming support', url: "https://github.com/freemocap/skellydocs/issues/9"},
        { label: 'Adaptive resolution scaling', url: "https://github.com/freemocap/skellydocs/issues/10" },
      ],
      docPath: 'core/real-time-streaming',
    },
    {
      id: 'precise-timestamps',
      icon: '⏱️',
      title: 'Precise Timestamps',
      description:
        'High-resolution timestamps at every stage of the capture pipeline, stored in human-readable format.',
      summary: (
        <>
          Most USB cameras do <em>not</em> record real timestamps.{' '}
          <Tip text="High-resolution perf_counter_ns timestamps at multiple lifecycle stages: pre-grab, post-grab, pre-retrieve, post-retrieve, copy, record">
            SkellyCam captures precise timestamps
          </Tip>{' '}
          for every camera at every stage of the capture pipeline, plus the
          multi-camera stream — all in <strong>human-readable format</strong> with
          pre-calculated inter-camera synchronization statistics.
        </>
      ),
      issues: [
        { label: 'Clean up data model to tidy format', url: "https://github.com/freemocap/skellydocs/issues/11" },
      ],
      docPath: 'core/precise-timestamps',
    },
  ],

  guarantees: [
    'All recorded videos have precisely the same frame count',
    'Each multi-frame payload contains exactly one image per camera, recorded at the same time slice',
  ],

  guaranteeIssues: [
    { label: 'Recordings guaranteed to complete on crash (hybrid MP4 codec)', url: "https://github.com/freemocap/skellydocs/issues/12" },
  ],
};

export default config;
