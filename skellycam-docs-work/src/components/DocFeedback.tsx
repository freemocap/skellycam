import React, { useState } from 'react';

const containerStyle: React.CSSProperties = {
  marginTop: '2.5rem',
  paddingTop: '1.5rem',
  borderTop: '1px solid var(--ifm-toc-border-color)',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.75rem',
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.75rem',
  flexWrap: 'wrap',
};

const labelStyle: React.CSSProperties = {
  fontSize: '0.85rem',
  color: 'var(--ifm-color-emphasis-600)',
};

const buttonBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.3rem',
  padding: '0.3rem 0.75rem',
  borderRadius: '6px',
  border: '1px solid var(--ifm-toc-border-color)',
  background: 'transparent',
  cursor: 'pointer',
  fontSize: '0.82rem',
  color: 'var(--ifm-color-emphasis-700)',
  transition: 'all 0.15s ease',
};

const selectedStyle: React.CSSProperties = {
  borderColor: 'var(--ifm-color-primary)',
  background: 'var(--ifm-color-primary-contrast-background)',
  color: 'var(--ifm-color-primary)',
};

const thankYouStyle: React.CSSProperties = {
  fontSize: '0.8rem',
  color: 'var(--ifm-color-primary)',
  fontStyle: 'italic',
};

const linkStyle: React.CSSProperties = {
  fontSize: '0.82rem',
  color: 'var(--ifm-color-emphasis-600)',
  textDecoration: 'none',
};

interface DocFeedbackProps {
  /** Relative path of the doc file, e.g. "docs/architecture.md" */
  slug?: string;
}

export default function DocFeedback({ slug }: DocFeedbackProps): React.ReactElement {
  const [vote, setVote] = useState<'up' | 'down' | null>(null);

  const discussionUrl = slug
    ? `https://github.com/freemocap/skellycam/discussions/new?category=documentation&title=Feedback on ${encodeURIComponent(slug)}`
    : 'https://github.com/freemocap/skellycam/discussions/new?category=documentation';

  const issueUrl = slug
    ? `https://github.com/freemocap/skellycam/issues/new?labels=documentation&title=Docs issue: ${encodeURIComponent(slug)}`
    : 'https://github.com/freemocap/skellycam/issues/new?labels=documentation';

  return (
    <div style={containerStyle}>
      <div style={rowStyle}>
        <span style={labelStyle}>Was this page helpful?</span>
        <button
          type="button"
          style={vote === 'up' ? { ...buttonBase, ...selectedStyle } : buttonBase}
          onClick={() => setVote('up')}
          aria-label="Yes, this page was helpful"
        >
          👍 Yes
        </button>
        <button
          type="button"
          style={vote === 'down' ? { ...buttonBase, ...selectedStyle } : buttonBase}
          onClick={() => setVote('down')}
          aria-label="No, this page was not helpful"
        >
          👎 No
        </button>
        {vote && <span style={thankYouStyle}>Thanks for your feedback!</span>}
      </div>
      <div style={rowStyle}>
        <a href={discussionUrl} style={linkStyle} target="_blank" rel="noopener noreferrer">
          💬 Leave a comment
        </a>
        <span style={{ ...labelStyle, opacity: 0.4 }}>·</span>
        <a href={issueUrl} style={linkStyle} target="_blank" rel="noopener noreferrer">
          🐛 Report an issue
        </a>
      </div>
    </div>
  );
}
