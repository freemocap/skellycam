import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';

import styles from './index.module.css';

function HeroSection() {
  return (
    <div className={styles.hero}>
      <div className={styles.heroGlow} />
      <div className={styles.heroContent}>
        <img
          src="/skellycam/img/skellycam-logo.svg"
          alt="SkellyCam"
          className={styles.heroLogo}
        />
        <h1 className={styles.heroTitle}>
          Skelly<span className={styles.accent}>Cam</span>
        </h1>
        <p className={styles.heroTagline}>
          Frame-perfect multi-camera synchronization for USB webcams
        </p>
        <p className={styles.heroDescription}>
          The camera backend for{' '}
          <a href="https://freemocap.org" className={styles.heroLink}>
            FreeMoCap
          </a>
          . Cheap webcams, perfectly synchronized video.
        </p>
        <div className={styles.heroCtas}>
          <Link className={styles.ctaPrimary} to="/docs/">
            Get Started
          </Link>
          <Link className={styles.ctaSecondary} to="/download">
            Download
          </Link>
          <a
            className={styles.ctaGithub}
            href="https://github.com/freemocap/skellycam">
            GitHub →
          </a>
        </div>
      </div>
    </div>
  );
}

const FEATURES: {icon: string; title: string; description: string}[] = [
  {
    icon: '🔒',
    title: 'Frame-Perfect Sync',
    description:
      'A frame-count-gated capture protocol ensures no camera ever gets more than one frame ahead of the others. The OpenCV grab/retrieve split minimizes inter-camera timing spread. All recorded videos have identical frame counts — no drift, no dropped frames.',
  },
  {
    icon: '⚡',
    title: 'Multi-Process Capture',
    description:
      'Each camera runs in its own process with shared-memory ring buffers for zero-copy frame transfer. The CameraOrchestrator gates each camera\'s grab cycle based on relative frame counts, maintaining lock-step progression across the entire group.',
  },
  {
    icon: '📡',
    title: 'Real-Time Streaming',
    description:
      'A compact binary WebSocket protocol streams JPEG-compressed multi-camera frames to the React/Electron frontend with built-in backpressure management and adaptive resolution scaling.',
  },
];

function FeaturesSection() {
  return (
    <div className={styles.features}>
      <div className={styles.featuresGrid}>
        {FEATURES.map((f, i) => (
          <div key={i} className={styles.featureCard}>
            <span className={styles.featureIcon}>{f.icon}</span>
            <h3 className={styles.featureTitle}>{f.title}</h3>
            <p className={styles.featureDescription}>{f.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function GuaranteesSection() {
  return (
    <div className={styles.guarantees}>
      <h2 className={styles.guaranteesTitle}>The guarantees</h2>
      <div className={styles.guaranteesGrid}>
        <div className={styles.guaranteeItem}>
          <span className={styles.guaranteeCheck}>✓</span>
          <span>
            All recorded videos have <strong>the same frame count</strong>
          </span>
        </div>
        <div className={styles.guaranteeItem}>
          <span className={styles.guaranteeCheck}>✓</span>
          <span>
            Each payload contains{' '}
            <strong>exactly one image per camera</strong> per frame event
          </span>
        </div>
        <div className={styles.guaranteeItem}>
          <span className={styles.guaranteeCheck}>✓</span>
          <span>
            Playback is <strong>hard frame-locked</strong> — all videos always
            display the same frame number
          </span>
        </div>
      </div>
    </div>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Home"
      description="Frame-perfect multi-camera synchronization for USB webcams">
      <main className={styles.main}>
        <HeroSection />
        <FeaturesSection />
        <GuaranteesSection />
      </main>
    </Layout>
  );
}
