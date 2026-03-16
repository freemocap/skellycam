import { IndexPage } from '@freemocap/skellydocs';
import config from '../../content.config';

const REPO = 'skellycam';

export default function Home() {
  return <IndexPage config={config} />;
}
