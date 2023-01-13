import * as Sentry from '@sentry/react';
import keyBy from 'lodash/keyBy';

import {t} from 'sentry/locale';
import {
  type EntrySpans,
  type EventTransaction,
  type PlatformType,
  EntryType,
  IssueCategory,
  IssueType,
} from 'sentry/types';

import {type RawSpanType} from '../spans/types';

import {type ResourceLink} from './resources';
import {type TraceContextSpanProxy} from './spanEvidence';

const RESOURCES_DESCRIPTIONS: Record<IssueType, string> = {
  [IssueType.PERFORMANCE_N_PLUS_ONE_DB_QUERIES]: t(
    "N+1 queries are extraneous queries (N) caused by a single, initial query (+1). In the Span Evidence above, we've identified the parent span where the extraneous spans are located and the extraneous spans themselves. To learn more about how to fix N+1 problems, check out these resources:"
  ),
  [IssueType.PERFORMANCE_N_PLUS_ONE_API_CALLS]: t(
    "N+1 API Calls are repeated concurrent calls to fetch a resource type. In the Span Evidence section we've identified the repeated calls. To learn more about how and when to fix N+1 API Calls, check out these resources:"
  ),
  [IssueType.PERFORMANCE_FILE_IO_MAIN_THREAD]: t(
    'File IO operations on your main thread may cause app hangs.'
  ),
  [IssueType.PERFORMANCE_SLOW_SPAN]: t(
    'Slow DB Queries are SELECT query spans that take longer than 1s. A quick method to understand why this may be the case is running an EXPLAIN command on the query itself. To learn more about how to fix slow DB queries, check out these resources:'
  ),
  [IssueType.ERROR]: '',
};

type PlatformSpecificResources = Partial<Record<PlatformType, ResourceLink[]>>;

const DEFAULT_RESOURCE_LINK: Record<IssueType, ResourceLink[]> = {
  [IssueType.PERFORMANCE_N_PLUS_ONE_DB_QUERIES]: [
    {
      text: t('Sentry Docs: N+1 Queries'),
      link: 'https://docs.sentry.io/product/issues/issue-details/performance-issues/n-one-queries/',
    },
  ],
  [IssueType.PERFORMANCE_N_PLUS_ONE_API_CALLS]: [
    {
      text: t('Sentry Docs: N+1 API Calls'),
      link: 'https://docs.sentry.io/product/issues/issue-details/performance-issues/n-one-api-calls/',
    },
  ],
  [IssueType.PERFORMANCE_FILE_IO_MAIN_THREAD]: [],
  [IssueType.PERFORMANCE_SLOW_SPAN]: [],
  [IssueType.ERROR]: [],
};

// TODO: When the Sentry blogpost for N+1s and documentation has been released, add them as resources for all platforms
const RESOURCE_LINKS: Record<IssueType, PlatformSpecificResources> = {
  [IssueType.PERFORMANCE_N_PLUS_ONE_DB_QUERIES]: {
    python: [
      {
        text: t('Finding and Fixing Django N+1 Problems'),
        link: 'https://blog.sentry.io/2020/09/14/finding-and-fixing-django-n-1-problems',
      },
    ],
    'python-django': [
      {
        text: t('Finding and Fixing Django N+1 Problems'),
        link: 'https://blog.sentry.io/2020/09/14/finding-and-fixing-django-n-1-problems',
      },
    ],
  },
  [IssueType.PERFORMANCE_N_PLUS_ONE_API_CALLS]: {},
  [IssueType.PERFORMANCE_FILE_IO_MAIN_THREAD]: {},
  [IssueType.PERFORMANCE_SLOW_SPAN]: {},
  [IssueType.ERROR]: {},
};

export function getResourceDescription(issueType: IssueType): string {
  return RESOURCES_DESCRIPTIONS[issueType];
}

export function getResourceLinks(
  issueType: IssueType,
  platform: PlatformType | undefined
): ResourceLink[] {
  let links: ResourceLink[] = [];
  if (DEFAULT_RESOURCE_LINK[issueType]) {
    links = [...DEFAULT_RESOURCE_LINK[issueType]];
  }
  if (RESOURCE_LINKS[issueType] && platform) {
    const platformLink = RESOURCE_LINKS[issueType][platform];
    if (platformLink) {
      links = [...links, ...platformLink];
    }
  }
  return links;
}

export function getSpanInfoFromTransactionEvent(
  event: Pick<
    EventTransaction,
    'entries' | 'perfProblem' | 'issueCategory' | 'endTimestamp' | 'contexts'
  >
) {
  if (!event.perfProblem) {
    if (
      event.issueCategory === IssueCategory.PERFORMANCE &&
      event.endTimestamp > 1663560000 //  (Sep 19, 2022 onward), Some events could have been missing evidence before EA
    ) {
      Sentry.captureException(new Error('Span Evidence missing for performance issue.'));
    }
    return null;
  }

  // Let's dive into the event to pick off the span evidence data by using the IDs we know
  const spanEntry = event.entries.find((entry: EntrySpans | any): entry is EntrySpans => {
    return entry.type === EntryType.SPANS;
  });

  const spans: Array<RawSpanType | TraceContextSpanProxy> = spanEntry?.data
    ? [...spanEntry.data]
    : [];

  if (event?.contexts?.trace && event?.contexts?.trace?.span_id) {
    // TODO: Fix this conditional and check if span_id is ever actually undefined.
    spans.push(event.contexts.trace as TraceContextSpanProxy);
  }
  const spansById = keyBy(spans, 'span_id');

  const parentSpan = event.perfProblem.parentSpanIds
    ? spansById[event.perfProblem.parentSpanIds[0]]
    : null;

  const offendingSpans = (event?.perfProblem?.offenderSpanIds ?? []).map(
    spanID => spansById[spanID]
  );

  const affectedSpanIds = [...event.perfProblem.offenderSpanIds];
  if (parentSpan !== null) {
    affectedSpanIds.push(parentSpan.span_id);
  }

  return {parentSpan, offendingSpans, affectedSpanIds};
}
