import React from 'react';
import Layout from '@theme-original/DocItem/Layout';
import type LayoutType from '@theme/DocItem/Layout';
import { useDoc } from '@docusaurus/plugin-content-docs/client';
import AiGeneratedBanner from '@site/src/components/AiGeneratedBanner';
import DocFeedback from '@site/src/components/DocFeedback';

type Props = React.ComponentProps<typeof LayoutType>;

export default function LayoutWrapper(props: Props): React.ReactElement {
  const { metadata } = useDoc();
  const slug = metadata?.editUrl
    ? metadata.editUrl.replace(
        'https://github.com/freemocap/skellycam/tree/development/skellycam-docs/',
        '',
      )
    : metadata?.slug ?? '';

  return (
    <>
      <AiGeneratedBanner />
      <Layout {...props} />
      <DocFeedback slug={slug} />
    </>
  );
}
