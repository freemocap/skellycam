import type {RoadmapItem} from '@site/src/data/roadmap-types';
import styles from '@site/src/css/theme.module.css';

/** Issue vs PR badge. */
function TypeIcon({type}: {type: RoadmapItem['type']}) {
  if (type === 'pr') {
    return <span className={styles.roadmapTypeBadgePr} title="Pull Request">PR</span>;
  }
  return <span className={styles.roadmapTypeBadgeIssue} title="Issue">Issue</span>;
}

/** Open/closed status indicator. */
function StatusBadge({status}: {status: RoadmapItem['status']}) {
  const cls = status === 'open' ? styles.roadmapStatusOpen : styles.roadmapStatusClosed;
  return <span className={cls}>{status === 'open' ? '● Open' : '✓ Closed'}</span>;
}

/**
 * A single roadmap entry card. Shows type badge, status, issue number,
 * last-updated date, title, body excerpt, labels, and a link to GitHub.
 *
 * Used by RoadmapContent for the /roadmap page grid, and available for
 * embedding in doc pages or other contexts.
 */
export default function RoadmapEntry({item}: {item: RoadmapItem}) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className={styles.roadmapCard}
    >
      <div className={styles.roadmapCardHeader}>
        <TypeIcon type={item.type} />
        <StatusBadge status={item.status} />
        <span className={styles.roadmapCardNumber}>#{item.number}</span>
        <span className={styles.roadmapCardDate}>
          {new Date(item.updatedAt).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })}
        </span>
      </div>
      <h3 className={styles.roadmapCardTitle}>{item.title}</h3>
      {item.excerpt && (
        <p className={styles.roadmapCardExcerpt}>{item.excerpt}</p>
      )}
      {item.labels.length > 0 && (
        <div className={styles.roadmapCardLabels}>
          {item.labels.map((l) => (
            <span
              key={l.name}
              className={styles.roadmapCardLabel}
              style={{'--label-color': `#${l.color}`} as React.CSSProperties}
            >
              {l.name}
            </span>
          ))}
        </div>
      )}
      <span className={styles.roadmapCardArrow}>View on GitHub →</span>
    </a>
  );
}
