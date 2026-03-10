import type {CoreFeature} from '@site/src/data/core-features';
import TodoList from '@site/src/components/TodoList';

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
    <div className="sk-feature-header">
      <div className="sk-feature-header-summary">
        <span className="sk-feature-header-icon">{feature.icon}</span>
        <div className="sk-feature-header-text">{feature.summary}</div>
      </div>
      {feature.todos.length > 0 && (
        <TodoList items={feature.todos} />
      )}
    </div>
  );
}
