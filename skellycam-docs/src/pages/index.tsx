import { IndexPage } from '@freemocap/skellydocs';
import config from '../../content.config';

// TODO NOTES: Need to use the new skellydocs Index/config templates to:
// - change the CTA buttons to go to :
// - - Get Started (go to 'beginner tutorial'),
// - - Download/Install (go to download page)
// - -  Learn More (goes to top level docs page)

// Also the Gurarntees at the bottom needs to show "SkellyCAM is carefully designed to guarantee: ..." Right now it just says 'Skelly...'

export default function Home() {
  return <IndexPage config={config} />;
}
