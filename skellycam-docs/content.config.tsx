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
    ctaButtons: [
      { label: 'Get Started', to: '/docs/getting-started/beginner-tutorial', variant: 'primary' },
      { label: 'Download/Install', to: '/download', variant: 'secondary' },
      { label: 'Learn More', to: '/docs/intro', variant: 'secondary' },
    ],
  },

  features: [
    {
      id: 'frame-perfect-sync',
      icon: '🔒',
      title: 'Frame-Perfect Synchronization',
      description:
        'A frame-count-gated capture protocol ensures all cameras stay in lock-step with identical frame counts during both runtime and recording.',
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
        { label: 'Hardware synchronization (external trigger)', url: "https://github.com/freemocap/skellycam/issues/89" },
        { label: 'Target frame rate setting', url: "https://github.com/freemocap/skellycam/issues/90" },
        { label: 'Sub-frame synchronization', url: "https://github.com/freemocap/skellycam/issues/91" },
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
        { label: 'OpenCV VideoCapture backend alternatives', url: "https://github.com/freemocap/skellycam/issues/93" },
        { label: 'Support for non-UVC camera backends', url: "https://github.com/freemocap/skellycam/issues/92" },
        { label: 'Camera capability auto-detection', url: "https://github.com/freemocap/skellycam/issues/94" },
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
        { label: 'Support UDP, ZeroMQ, etc streaming', url: "https://github.com/freemocap/skellycam/issues/95"},
        { label: 'Client library SDKs', url: "https://github.com/freemocap/skellycam/issues/96"},
        { label: 'Remote streaming support', url: "https://github.com/freemocap/skellycam/issues/97"},
        { label: 'Adaptive resolution scaling', url: "https://github.com/freemocap/skellycam/issues/98" },
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
        { label: 'Clean up data model to tidy format', url: "https://github.com/freemocap/skellycam/issues/99" },
      ],
      docPath: 'core/precise-timestamps',
    },
  ],

  guarantees: [
    'All recorded videos have precisely the same frame count — corresponding frames across cameras are from the same temporal time slice',
    'Each multi-frame payload contains one image per camera, guaranteed to be captured at the same time slice',
    'Recording quality is protected from real-time streaming — variations in the live stream never cause blocking, lagging, or frame loss in the recording pipeline',
  ],

  guaranteeIssues: [
    { label: 'Recordings guaranteed to complete on crash (hybrid MP4 codec)', url: "https://github.com/freemocap/skellycam/issues/100" },
  ],

  guaranteesConfig: {
    title: (
      <>
        Skelly<span style={{ color: 'var(--skelly-accent, #ff6b35)' }}>Cam</span> is carefully designed to{' '}
        <span style={{ color: 'var(--skelly-accent, #ff6b35)' }}>guarantee</span>:
      </>
    ),
    items: [
      'All recorded videos have precisely the same frame count — corresponding frames across cameras are from the same temporal time slice',
      'Each multi-frame payload contains one image per camera, guaranteed to be captured at the same time slice',
      'Recording quality is protected from real-time streaming — variations in the live stream never cause blocking, lagging, or frame loss in the recording pipeline',
    ],
    issues: [
      { label: 'Recordings guaranteed to complete on crash (hybrid MP4 codec)', url: "https://github.com/freemocap/skellycam/issues/100" },
    ],
  },

    projectBoardUrl: "https://github.com/orgs/freemocap/projects/34/views/6"
};

export default config;
