import {useState} from 'react';

const REPO = 'https://github.com/freemocap/skellycam';

export type TodoItem = {
  label: string;
  issueNum: number;
};

/**
 * Collapsible "Roadmap" section that links each item to a GitHub issue.
 */
export default function TodoList({items}: {items: TodoItem[]}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sk-todo-section">
      <button
        className="sk-todo-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="sk-todo-chevron" data-open={open}>▸</span>
        <span className="sk-todo-label">Roadmap</span>
        <span className="sk-todo-badge">{items.length}</span>
      </button>
      {open && (
        <ul className="sk-todo-items">
          {items.map((t) => (
            <li key={t.issueNum} className="sk-todo-item">
              <a
                href={`${REPO}/issues/${t.issueNum}`}
                target="_blank"
                rel="noopener noreferrer"
                className="sk-todo-link"
              >
                <span className="sk-todo-icon">◇</span>
                {t.label}
                <span className="sk-todo-arrow">↗</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
