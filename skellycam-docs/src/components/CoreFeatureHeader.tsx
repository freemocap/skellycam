import type {CoreFeature} from '@site/src/data/core-features';
import TodoList from '@site/src/components/TodoList';
import styles from '@site/src/css/theme.module.css';

/**
 * Header block for core feature doc pages. Renders the feature's summary
 * and roadmap, creating visual consistency with the index page cards.
 *
 * Usage in MDX:
 *   import CoreFeatureHeader from '@site/src/components/CoreFeatureHeader';
 *   import {getFeatureById} from '@site/src/data/core-features';
 *   <CoreFeatureHeader feature={getFeatureById('frame-perfect-sync')} />
 */
export default function CoreFeatureHeader({feature}: {feature: CoreFeature}) {
  return (
    <div className={styles.featureHeader}>
      <div className={styles.featureHeaderSummary}>
        <span className={styles.featureHeaderIcon}>{feature.icon}</span>
        <div className={styles.featureHeaderText}>{feature.summary}</div>
      </div>
      {feature.todos.length > 0 && (
        <TodoList items={feature.todos} />
      )}
    </div>
  );
}
