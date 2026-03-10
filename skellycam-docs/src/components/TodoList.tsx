import {type MouseEvent, useState} from 'react';
import styles from '@site/src/css/theme.module.css';

const REPO = 'https://github.com/freemocap/skellycam';

export type TodoItem = {
  label: string;
  issueNum: number;
};

/**
 * Collapsible "Roadmap" section that links each item to a GitHub issue.
 * Uses divs instead of ul/li to avoid Docusaurus `.markdown` list style conflicts.
 * Stops event propagation so parent Link wrappers don't intercept clicks.
 */
export default function TodoList({items}: {items: TodoItem[]}) {
  const [open, setOpen] = useState(false);

  const handleToggle = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setOpen((v) => !v);
  };

  const handleItemClick = (e: MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <div className={styles.todoSection} onClick={(e: MouseEvent) => e.stopPropagation()}>
      <button
        className={styles.todoToggle}
        onClick={handleToggle}
        aria-expanded={open}
      >
        <span className={styles.todoChevron} data-open={open}>▸</span>
        <span className={styles.todoLabel}>Roadmap</span>
        <span className={styles.todoBadge}>{items.length}</span>
      </button>
      {open && (
        <div className={styles.todoItems}>
          {items.map((t) => (
            <div key={t.issueNum} className={styles.todoItem}>
              <a
                href={`${REPO}/issues/${t.issueNum}`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.todoLink}
                onClick={handleItemClick}
              >
                <span className={styles.todoIcon}>◇</span>
                {t.label}
                <span className={styles.todoArrow}>↗</span>
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
