import type {ReactNode} from 'react';
import Layout from '@theme/Layout';
import RoadmapContent from '@site/src/components/RoadmapContent';
import styles from '@site/src/css/theme.module.css';

export default function Roadmap(): ReactNode {
  return (
    <Layout title="Roadmap" description="SkellyCam development roadmap — what we're working on and what's next">
      <main className={styles.main}>
        <RoadmapContent />
      </main>
    </Layout>
  );
}
