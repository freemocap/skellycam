import type {ReactNode} from 'react';
import Layout from '@theme/Layout';

export default function DownloadPage(): ReactNode {
  return (
    <Layout title="Download" description="Download SkellyCam">
      <iframe
        src="/skellycam/download.html"
        style={{
          width: '100%',
          height: 'calc(100vh - 60px)',
          border: 'none',
        }}
        title="SkellyCam Download"
      />
    </Layout>
  );
}
