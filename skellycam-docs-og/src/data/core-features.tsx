import type {ReactNode} from 'react';
import Tip from '@site/src/components/Tip';
import type {TodoItem} from '@site/src/components/TodoList';

export type CoreFeature = {
  /** Unique key matching the MDX filename (without extension) */
  id: string;
  /** Emoji icon for the card */
  icon: string;
  /** Card title */
  title: string;
  /** Short plain-text description for meta/SEO */
  description: string;
  /** Rich summary rendered on the index page card (may include <Tip> etc.) */
  summary: ReactNode;
  /** Roadmap items linking to GitHub issues */
  todos: TodoItem[];
  /** Path to the doc page relative to /docs/ (matches slug) */
  docPath: string;
};

/**
 * All core feature definitions in display order.
 *
 * Each entry corresponds to:
 *   1. A card on the index page
 *   2. A detail page at docs/core/<id>.mdx
 *
 * To add a feature: add an entry here AND create the matching MDX file.
 */
export const CORE_FEATURES: CoreFeature[] = [
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
    todos: [
      {label: 'Hardware synchronization (external trigger)', issueNum: 1},
      {label: 'Target frame rate setting', issueNum: 2},
      {label: 'Sub-frame synchronization', issueNum: 3},
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
    todos: [
      {label: 'OpenCV VideoCapture backend alternatives', issueNum: 4},
      {label: 'Support for non-UVC camera backends', issueNum: 5},
      {label: 'Camera capability auto-detection', issueNum: 6},
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
    todos: [
      {label: 'UDP transport for high-throughput streaming', issueNum: 7},
      {label: 'Python client library', issueNum: 8},
      {label: 'Remote streaming support', issueNum: 9},
      {label: 'Adaptive resolution scaling', issueNum: 10},
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
    todos: [
      {label: 'Clean up data model to tidy format', issueNum: 11},
    ],
    docPath: 'core/precise-timestamps',
  },
];

/** Lookup a feature by its id. Throws if not found. */
export function getFeatureById(id: string): CoreFeature {
  const feature = CORE_FEATURES.find((f) => f.id === id);
  if (!feature) {
    throw new Error(`Unknown core feature id: "${id}"`);
  }
  return feature;
}
