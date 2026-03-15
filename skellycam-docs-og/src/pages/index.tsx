import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import TodoList from '@site/src/components/TodoList';
import {CORE_FEATURES} from '@site/src/data/core-features';
import styles from '@site/src/css/theme.module.css';

const REPO = 'https://github.com/freemocap/skellycam';

/* ── Hero ── */
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
        <p className={styles.heroSubtitle}>
          The camera backend for{' '}
          <a href="https://freemocap.org" className={styles.heroLink}>
            FreeMoCap
          </a>
        </p>
        <p className={styles.heroTagline}>
          Frame-perfect multi-camera synchronization for USB webcams
        </p>
        <div className={styles.heroCtas}>
          <Link className={styles.ctaPrimary} to="/docs/">
            Get Started
          </Link>
          <Link className={styles.ctaSecondary} to="/download">
            Download
          </Link>
          <a
            className={styles.ctaCode}
            href={REPO}
            title="View source on GitHub"
          >
            Code →
          </a>
        </div>
      </div>
    </div>
  );
}

/* ── Feature cards (driven by core-features data) ── */
function FeaturesSection() {
  return (
    <div className={styles.features}>
      <div className={styles.featuresGrid}>
        {CORE_FEATURES.map((f) => (
          <div key={f.id} className={styles.featureCard}>
            <Link to={`/docs/${f.docPath}`} className={styles.featureCardLink}>
              <span className={styles.featureIcon}>{f.icon}</span>
              <h3 className={styles.featureTitle}>{f.title}</h3>
              <div className={styles.featureDescription}>{f.summary}</div>
            </Link>
            {f.todos.length > 0 && <TodoList items={f.todos} />}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Guarantees ── */
function GuaranteesSection() {
  return (
    <div className={styles.guarantees}>
      <h2 className={styles.guaranteesTitle}>
        SkellyCam is carefully designed to{' '}
        <span className={styles.accent}>guarantee</span>:
      </h2>
      <div className={styles.guaranteesGrid}>
        <div className={styles.guaranteeItem}>
          <span className={styles.guaranteeCheck}>✓</span>
          <span>
            All recorded videos have{' '}
            <strong>precisely the same frame count</strong>
          </span>
        </div>
        <div className={styles.guaranteeItem}>
          <span className={styles.guaranteeCheck}>✓</span>
          <span>
            Each multi-frame payload contains{' '}
            <strong>exactly one image per camera</strong>, recorded at the same
            time slice
          </span>
        </div>
      </div>
      <div className={styles.guaranteesRoadmap}>
        <TodoList
          items={[
            {
              label:
                'Recordings guaranteed to complete on crash (hybrid MP4 codec)',
              issueNum: 12,
            },
          ]}
        />
      </div>
    </div>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Home"
      description="Frame-perfect multi-camera synchronization for USB webcams"
    >
      <main className={styles.main}>
        <HeroSection />
        <FeaturesSection />
        <GuaranteesSection />
      </main>
    </Layout>
  );
}
