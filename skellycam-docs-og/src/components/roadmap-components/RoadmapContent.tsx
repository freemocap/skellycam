import {useState, useEffect, useMemo, useCallback} from 'react';
import styles from '@site/src/css/theme.module.css';
import {
  GitHubLabel,
  ItemStatus,
  ItemType,
  RoadmapItem,
  SortKey
} from "@site/src/components/roadmap-components/roadmap-types";
import RoadmapEntry from "@site/src/components/roadmap-components/RoadmapEntry";

/* ── Cache types (internal to this module) ── */

type CacheEntry = {
  etag: string;
  timestamp: number;
  items: RoadmapItem[];
};

/* ── Constants ── */

const REPO = 'freemocap/skellycam';
const API_URL = `https://api.github.com/repos/${REPO}/issues?labels=roadmap&state=all&per_page=100`;
const CACHE_KEY = 'sk-roadmap-cache';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes before conditional revalidation

/* ── Helpers ── */

/** Extract first ~2 sentences from a GitHub issue body as plain text. */
function extractExcerpt(body: string | null): string {
  if (!body) return '';
  const plain = body
    .replace(/```[\s\S]*?```/g, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[#*_~`>]/g, '')
    .replace(/\r\n/g, '\n')
    .trim();
  const sentences = plain.split(/(?<=[.!?])\s+/);
  return sentences.slice(0, 2).join(' ').slice(0, 280);
}

/** Parse a raw GitHub API issue into a RoadmapItem. */
function parseItem(raw: Record<string, unknown>): RoadmapItem {
  const labels = (raw.labels as Record<string, unknown>[]).map((l) => ({
    name: l.name as string,
    color: l.color as string,
  }));

  return {
    number: raw.number as number,
    title: raw.title as string,
    excerpt: extractExcerpt(raw.body as string | null),
    type: raw.pull_request ? 'pr' : 'issue',
    status: (raw.state as string) === 'open' ? 'open' : 'closed',
    labels: labels.filter((l) => l.name !== 'roadmap'),
    updatedAt: raw.updated_at as string,
    createdAt: raw.created_at as string,
    url: raw.html_url as string,
  };
}

function readCache(): CacheEntry | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CacheEntry;
  } catch {
    return null;
  }
}

function writeCache(entry: CacheEntry): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(entry));
  } catch {
    // storage full or unavailable — not critical
  }
}

/* ── Fetch with ETag caching ── */

type FetchResult =
  | {status: 'ok'; items: RoadmapItem[]}
  | {status: 'cached'; items: RoadmapItem[]}
  | {status: 'error'; items: RoadmapItem[]; message: string};

async function fetchRoadmapItems(): Promise<FetchResult> {
  const cache = readCache();

  if (cache && Date.now() - cache.timestamp < CACHE_TTL_MS) {
    return {status: 'cached', items: cache.items};
  }

  const headers: Record<string, string> = {
    Accept: 'application/vnd.github.v3+json',
  };
  if (cache?.etag) {
    headers['If-None-Match'] = cache.etag;
  }

  try {
    const response = await fetch(API_URL, {headers});

    if (response.status === 304 && cache) {
      const refreshed: CacheEntry = {...cache, timestamp: Date.now()};
      writeCache(refreshed);
      return {status: 'cached', items: cache.items};
    }

    if (!response.ok) {
      const msg = response.status === 403
        ? 'GitHub rate limit reached. Showing cached data.'
        : `GitHub API returned ${response.status}`;
      return {status: 'error', items: cache?.items ?? [], message: msg};
    }

    const data = (await response.json()) as Record<string, unknown>[];
    const items = data.map(parseItem);
    const etag = response.headers.get('etag') ?? '';

    writeCache({etag, timestamp: Date.now(), items});
    return {status: 'ok', items};
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Network error';
    return {
      status: 'error',
      items: cache?.items ?? [],
      message: `Could not reach GitHub: ${message}`,
    };
  }
}

/* ── Sort comparators ── */

const SORT_FNS: Record<SortKey, (a: RoadmapItem, b: RoadmapItem) => number> = {
  updated: (a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  newest: (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt),
  oldest: (a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt),
};

/* ── Filter UI sub-components ── */

function LabelPill({label, active, onClick}: {label: GitHubLabel; active: boolean; onClick: () => void}) {
  return (
    <button
      className={`${styles.roadmapLabelPill} ${active ? styles.roadmapLabelPillActive : ''}`}
      style={{'--label-color': `#${label.color}`} as React.CSSProperties}
      onClick={onClick}
    >
      <span className={styles.roadmapLabelDot} />
      {label.name}
    </button>
  );
}

/* ── Main component ── */

export default function RoadmapContent() {
  const [items, setItems] = useState<RoadmapItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<ItemType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<ItemStatus | 'all'>('all');
  const [labelFilter, setLabelFilter] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('updated');

  useEffect(() => {
    fetchRoadmapItems().then((result) => {
      setItems(result.items);
      if (result.status === 'error') {
        setError(result.message);
      }
      setLoading(false);
    });
  }, []);

  const handleRetry = useCallback(() => {
    setLoading(true);
    setError(null);
    try { localStorage.removeItem(CACHE_KEY); } catch {}
    fetchRoadmapItems().then((result) => {
      setItems(result.items);
      if (result.status === 'error') {
        setError(result.message);
      }
      setLoading(false);
    });
  }, []);

  const allLabels = useMemo(() => {
    const map = new Map<string, GitHubLabel>();
    for (const item of items) {
      for (const label of item.labels) {
        if (!map.has(label.name)) {
          map.set(label.name, label);
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [items]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items
      .filter((item) => {
        if (typeFilter !== 'all' && item.type !== typeFilter) return false;
        if (statusFilter !== 'all' && item.status !== statusFilter) return false;
        if (labelFilter && !item.labels.some((l) => l.name === labelFilter)) return false;
        if (q && !item.title.toLowerCase().includes(q) && !item.excerpt.toLowerCase().includes(q)) {
          return false;
        }
        return true;
      })
      .sort(SORT_FNS[sort]);
  }, [items, search, typeFilter, statusFilter, labelFilter, sort]);

  return (
    <div className={styles.roadmap}>
      <div className={styles.roadmapHeader}>
        <h1 className={styles.roadmapTitle}>Roadmap</h1>
        <p className={styles.roadmapSubtitle}>
          What we're working on and what's coming next. Each item links to the
          GitHub conversation where the work happens.
        </p>
      </div>

      {error && (
        <div className={styles.roadmapError}>
          <span>{error}</span>
          <button className={styles.roadmapRetry} onClick={handleRetry}>
            Retry
          </button>
        </div>
      )}

      <div className={styles.roadmapFilters}>
        <input
          type="text"
          className={styles.roadmapSearch}
          placeholder="Search roadmap…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className={styles.roadmapFilterRow}>
          <div className={styles.roadmapChipGroup}>
            {(['all', 'issue', 'pr'] as const).map((t) => (
              <button
                key={t}
                className={`${styles.roadmapChip} ${typeFilter === t ? styles.roadmapChipActive : ''}`}
                onClick={() => setTypeFilter(t)}
              >
                {t === 'all' ? 'All types' : t === 'issue' ? 'Issues' : 'PRs'}
              </button>
            ))}
          </div>

          <div className={styles.roadmapChipGroup}>
            {(['all', 'open', 'closed'] as const).map((s) => (
              <button
                key={s}
                className={`${styles.roadmapChip} ${statusFilter === s ? styles.roadmapChipActive : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s === 'all' ? 'All statuses' : s === 'open' ? 'Open' : 'Closed'}
              </button>
            ))}
          </div>

          <select
            className={styles.roadmapSort}
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
          >
            <option value="updated">Recently updated</option>
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
          </select>
        </div>

        {allLabels.length > 0 && (
          <div className={styles.roadmapLabelBar}>
            <button
              className={`${styles.roadmapLabelPill} ${labelFilter === null ? styles.roadmapLabelPillActive : ''}`}
              onClick={() => setLabelFilter(null)}
            >
              All labels
            </button>
            {allLabels.map((l) => (
              <LabelPill
                key={l.name}
                label={l}
                active={labelFilter === l.name}
                onClick={() => setLabelFilter(labelFilter === l.name ? null : l.name)}
              />
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <div className={styles.roadmapLoading}>
          <div className={styles.roadmapSpinner} />
          <span>Loading roadmap from GitHub…</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className={styles.roadmapEmpty}>
          {items.length === 0
            ? 'No roadmap items found. Add a "roadmap" label to GitHub issues to populate this page.'
            : 'No items match the current filters.'}
        </div>
      ) : (
        <>
          <p className={styles.roadmapCount}>
            {filtered.length} {filtered.length === 1 ? 'item' : 'items'}
            {(search || typeFilter !== 'all' || statusFilter !== 'all' || labelFilter) &&
              ` (filtered from ${items.length})`}
          </p>
          <div className={styles.roadmapGrid}>
            {filtered.map((item) => (
              <RoadmapEntry key={item.number} item={item} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
