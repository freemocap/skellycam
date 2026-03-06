import React, { useState, useCallback } from 'react';
import { SKELLYPINGS_SERVER_URL, DOCS_APP_VERSION } from './telemetry';

// ── Styles ──

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

// ── Anonymous user ID ──

function getAnonymousUserId(): string {
  const STORAGE_KEY = 'skellycam_docs_uid';
  try {
    const existing = localStorage.getItem(STORAGE_KEY);
    if (existing) return existing;
  } catch {
    // localStorage not available (SSR, privacy mode, etc.)
  }

  // crypto.randomUUID() is available in all modern browsers
  const uid =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `anon-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  try {
    localStorage.setItem(STORAGE_KEY, uid);
  } catch {
    // Ignore write failure
  }
  return uid;
}

// ── Telemetry send ──

function sendFeedbackEvent(slug: string, vote: 'up' | 'down'): void {
  const event = {
    event_type: 'docs_feedback',
    app_version: DOCS_APP_VERSION,
    os_platform: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
    user_id: getAnonymousUserId(),
    timestamp: Date.now() / 1000,
    payload: {
      page_slug: slug,
      vote,
      url: typeof window !== 'undefined' ? window.location.href : '',
      referrer: typeof document !== 'undefined' ? document.referrer : '',
    },
  };

  const body = JSON.stringify({ events: [event] });

  // Fire-and-forget — feedback is best-effort, never block the UI
  if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
    // sendBeacon with a Blob lets us set Content-Type without a preflight
    // for same-site requests. For cross-origin it needs CORS, which the
    // server now supports.
    navigator.sendBeacon(
      `${SKELLYPINGS_SERVER_URL}/events`,
      new Blob([body], { type: 'application/json' }),
    );
  } else {
    fetch(`${SKELLYPINGS_SERVER_URL}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {
      // Swallow errors — feedback is non-critical
    });
  }
}

// ── Component ──

interface DocFeedbackProps {
  /** Relative path of the doc file, e.g. "docs/architecture.md" */
  slug?: string;
}

export default function DocFeedback({ slug }: DocFeedbackProps): React.ReactElement {
  const [vote, setVote] = useState<'up' | 'down' | null>(null);

  const handleVote = useCallback(
    (value: 'up' | 'down') => {
      setVote(value);
      sendFeedbackEvent(slug ?? 'unknown', value);
    },
    [slug],
  );

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
          onClick={() => handleVote('up')}
          aria-label="Yes, this page was helpful"
        >
          👍 Yes
        </button>
        <button
          type="button"
          style={vote === 'down' ? { ...buttonBase, ...selectedStyle } : buttonBase}
          onClick={() => handleVote('down')}
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
