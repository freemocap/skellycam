import type {ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import Layout from '@theme/Layout';

export default function DownloadPage(): ReactNode {
  return (
    <Layout
      title={translate({id: 'download.title', message: 'Download'})}
      description={translate({id: 'download.description', message: 'Download SkellyCam'})}>
      <iframe
        src="/skellycam/download.html"
        style={{
          width: '100%',
          height: 'calc(100vh - 60px)',
          border: 'none',
        }}
        title={translate({id: 'download.iframe.title', message: 'SkellyCam Download'})}
      />
    </Layout>
  );
}
