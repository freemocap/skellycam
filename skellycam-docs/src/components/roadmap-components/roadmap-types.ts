/** Type of GitHub item: issue or pull request. */
export type ItemType = 'issue' | 'pr';

/** Open/closed status. */
export type ItemStatus = 'open' | 'closed';

/** A GitHub label with a display color. */
export type GitHubLabel = {
  name: string;
  color: string;
};

/** A single roadmap item parsed from the GitHub API response. */
export type RoadmapItem = {
  number: number;
  title: string;
  excerpt: string;
  type: ItemType;
  status: ItemStatus;
  labels: GitHubLabel[];
  updatedAt: string;
  createdAt: string;
  url: string;
};

/** Sort options for the roadmap list. */
export type SortKey = 'updated' | 'newest' | 'oldest';
