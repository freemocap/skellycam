import type {ReactNode} from 'react';

/**
 * Inline tooltip for progressive disclosure. Renders children with a dotted
 * underline; hovering reveals the `text` explanation.
 */
export default function Tip({text, children}: {text: string; children: ReactNode}) {
  return (
    <span className="sk-tip" data-tip={text}>
      {children}
    </span>
  );
}
