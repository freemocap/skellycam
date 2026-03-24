import Layout from '@theme/Layout';
import DownloadPage from '../components/download/DownloadPage';

// TODO - This page shows up without the header when I go to the link directly, but the header shows up if I click the link to it from the docs home


export default function Download() {
  return (
    <Layout title="Download" description="Download SkellyCam">
      <DownloadPage />
    </Layout>
  );
}
