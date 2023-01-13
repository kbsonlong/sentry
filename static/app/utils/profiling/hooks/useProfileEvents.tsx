import {useQuery} from '@tanstack/react-query';

import {type ResponseMeta} from 'sentry/api';
import {normalizeDateTimeParams} from 'sentry/components/organizations/pageFilters/parse';
import {t} from 'sentry/locale';
import {type PageFilters} from 'sentry/types';
import {defined} from 'sentry/utils';
import {type DURATION_UNITS, type SIZE_UNITS} from 'sentry/utils/discover/fieldRenderers';
import {type FieldValueType} from 'sentry/utils/fields';
import type RequestError from 'sentry/utils/requestError/requestError';
import useApi from 'sentry/utils/useApi';
import useOrganization from 'sentry/utils/useOrganization';
import usePageFilters from 'sentry/utils/usePageFilters';

type Sort<F> = {
  key: F;
  order: 'asc' | 'desc';
};

interface UseProfileEventsOptions<F> {
  fields: readonly F[];
  referrer: string;
  sort: Sort<F>;
  cursor?: string;
  datetime?: PageFilters['datetime'];
  enabled?: boolean;
  limit?: number;
  query?: string;
}

type Unit = keyof typeof DURATION_UNITS | keyof typeof SIZE_UNITS | null;

type EventsResultsDataRow<F extends string> = {
  [K in F]: string | number | null;
};

type EventsResultsMeta<F extends string> = {
  fields: Partial<{[K in F]: FieldValueType}>;
  units: Partial<{[K in F]: Unit}>;
};

export type EventsResults<F extends string> = {
  data: EventsResultsDataRow<F>[];
  meta: EventsResultsMeta<F>;
};

export function useProfileEvents<F extends string>({
  fields,
  limit,
  referrer,
  query,
  sort,
  cursor,
  enabled = true,
  datetime,
}: UseProfileEventsOptions<F>) {
  const api = useApi();
  const organization = useOrganization();
  const {selection} = usePageFilters();

  const path = `/organizations/${organization.slug}/events/`;
  const endpointOptions = {
    query: {
      dataset: 'profiles',
      referrer,
      project: selection.projects,
      environment: selection.environments,
      ...normalizeDateTimeParams(datetime ?? selection.datetime),
      field: fields,
      per_page: limit,
      query,
      sort: sort.order === 'asc' ? sort.key : `-${sort.key}`,
      cursor,
    },
  };

  const queryKey = [path, endpointOptions];

  const queryFn = () =>
    api.requestPromise(path, {
      method: 'GET',
      includeAllArgs: true,
      query: endpointOptions.query,
    });

  return useQuery<
    [EventsResults<F>, string | undefined, ResponseMeta | undefined],
    RequestError
  >({
    queryKey,
    queryFn,
    refetchOnWindowFocus: false,
    retry: false,
    enabled,
  });
}

export function formatError(error: any): string | null {
  if (!defined(error)) {
    return null;
  }

  const detail = error.responseJSON?.detail;
  if (typeof detail === 'string') {
    return detail;
  }

  const message = detail?.message;
  if (typeof message === 'string') {
    return message;
  }

  return t('An unknown error occurred.');
}

export function formatSort<F extends string>(
  value: string | undefined,
  allowedKeys: readonly F[],
  fallback: Sort<F>
): Sort<F> {
  value = value || '';
  const order: Sort<F>['order'] = value[0] === '-' ? 'desc' : 'asc';
  const key = order === 'asc' ? value : value.substring(1);

  if (!allowedKeys.includes(key as F)) {
    return fallback;
  }

  return {key: key as F, order};
}
