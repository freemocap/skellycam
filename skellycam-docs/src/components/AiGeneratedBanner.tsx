import React from 'react';

const bannerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: '0.5rem',
  padding: '0.6rem 1rem',
  marginBottom: '1.5rem',
  borderRadius: '6px',
  border: '1px solid rgba(167, 139, 250, 0.2)',
  background: 'rgba(167, 139, 250, 0.04)',
  fontSize: '0.78rem',
  lineHeight: '1.45',
  color: 'var(--ifm-color-emphasis-600)',
};

const iconStyle: React.CSSProperties = {
  flexShrink: 0,
  fontSize: '0.9rem',
  marginTop: '1px',
  opacity: 0.7,
};

export default function AiGeneratedBanner(): React.ReactElement {
  return (
    <div style={bannerStyle}>
      <span style={iconStyle}>🤖</span>
      <span>
        <strong>AI-generated documentation</strong> — This page was drafted by
        an AI assistant and may contain inaccuracies. If you spot something
        wrong, please{' '}
        <a href="https://github.com/freemocap/skellycam/issues/new?labels=documentation&template=docs-issue.md">
          open an issue
        </a>{' '}
        or use the <em>Edit this page</em> link below to submit a fix.
      </span>
    </div>
  );
}
