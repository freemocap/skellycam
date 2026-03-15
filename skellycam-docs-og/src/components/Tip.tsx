import type {ReactNode} from 'react';
import styles from '@site/src/css/theme.module.css';

/**
 * Inline tooltip for progressive disclosure. Renders children with a dotted
 * underline; hovering reveals the `text` explanation.
 */
export default function Tip({text, children}: {text: string; children: ReactNode}) {
  return (
    <span className={styles.tip} data-tip={text}>
      {children}
    </span>
  );
}
