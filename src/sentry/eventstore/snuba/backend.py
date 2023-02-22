import logging
import random
from copy import deepcopy
from datetime import datetime, timedelta

import sentry_sdk
from django.utils import timezone

from sentry.eventstore.base import EventStorage
from sentry.eventstore.models import Event
from sentry.models.group import Group
from sentry.snuba.dataset import Dataset
from sentry.snuba.events import Columns
from sentry.utils import snuba
from sentry.utils.validators import normalize_event_id

EVENT_ID = Columns.EVENT_ID.value.alias
PROJECT_ID = Columns.PROJECT_ID.value.alias
TIMESTAMP = Columns.TIMESTAMP.value.alias

DESC_ORDERING = [f"-{TIMESTAMP}", f"-{EVENT_ID}"]
ASC_ORDERING = [TIMESTAMP, EVENT_ID]
DEFAULT_LIMIT = 100
DEFAULT_OFFSET = 0

NODESTORE_LIMIT = 100

logger = logging.getLogger(__name__)


def get_before_event_condition(event):
    return [
        [TIMESTAMP, "<=", event.datetime],
        [[TIMESTAMP, "<", event.datetime], [EVENT_ID, "<", event.event_id]],
    ]


def get_after_event_condition(event):
    return [
        [TIMESTAMP, ">=", event.datetime],
        [[TIMESTAMP, ">", event.datetime], [EVENT_ID, ">", event.event_id]],
    ]


class SnubaEventStorage(EventStorage):
    """
    Eventstore backend backed by Snuba
    """

    def get_events(
        self,
        filter,
        orderby=None,
        limit=DEFAULT_LIMIT,
        offset=DEFAULT_OFFSET,
        referrer="eventstore.get_events",
        dataset=snuba.Dataset.Events,
    ):
        """
        Get events from Snuba, with node data loaded.
        """
        with sentry_sdk.start_span(op="eventstore.snuba.get_events"):
            return self.__get_events(
                filter,
                orderby=orderby,
                limit=limit,
                offset=offset,
                referrer=referrer,
                should_bind_nodes=True,
                dataset=dataset,
            )

    def get_unfetched_events(
        self,
        filter,
        orderby=None,
        limit=DEFAULT_LIMIT,
        offset=DEFAULT_OFFSET,
        referrer="eventstore.get_unfetched_events",
        dataset=snuba.Dataset.Events,
    ):
        """
        Get events from Snuba, without node data loaded.
        """
        return self.__get_events(
            filter,
            orderby=orderby,
            limit=limit,
            offset=offset,
            referrer=referrer,
            should_bind_nodes=False,
            dataset=dataset,
        )

    def __get_events(
        self,
        filter,
        orderby=None,
        limit=DEFAULT_LIMIT,
        offset=DEFAULT_OFFSET,
        referrer=None,
        should_bind_nodes=False,
        dataset=snuba.Dataset.Events,
    ):
        assert filter, "You must provide a filter"
        cols = self.__get_columns(dataset)
        orderby = orderby or DESC_ORDERING

        # This is an optimization for the Group.filter_by_event_id query where we
        # have a single event ID and want to check all accessible projects for a
        # direct hit. In this case it's usually faster to go to nodestore first.
        if (
            filter.event_ids
            and filter.project_ids
            and len(filter.event_ids) * len(filter.project_ids) < min(limit, NODESTORE_LIMIT)
            and offset == 0
            and should_bind_nodes
        ):
            event_list = [
                Event(project_id=project_id, event_id=event_id)
                for event_id in filter.event_ids
                for project_id in filter.project_ids
            ]
            self.bind_nodes(event_list)

            nodestore_events = [event for event in event_list if len(event.data)]

            if nodestore_events:
                event_ids = {event.event_id for event in nodestore_events}
                project_ids = {event.project_id for event in nodestore_events}
                start = min(event.datetime for event in nodestore_events)
                end = max(event.datetime for event in nodestore_events) + timedelta(seconds=1)

                result = snuba.aliased_query(
                    selected_columns=cols,
                    start=start,
                    end=end,
                    conditions=filter.conditions,
                    filter_keys={"project_id": project_ids, "event_id": event_ids},
                    orderby=orderby,
                    limit=len(nodestore_events),
                    offset=DEFAULT_OFFSET,
                    referrer=referrer,
                    dataset=dataset,
                )

                if "error" not in result:
                    events = [self.__make_event(evt) for evt in result["data"]]

                    # Bind previously fetched node data
                    nodestore_dict = {
                        (e.event_id, e.project_id): e.data.data for e in nodestore_events
                    }
                    for event in events:
                        node_data = nodestore_dict[(event.event_id, event.project_id)]
                        event.data.bind_data(node_data)
                    return events

            return []

        result = snuba.aliased_query(
            selected_columns=cols,
            start=filter.start,
            end=filter.end,
            conditions=filter.conditions,
            filter_keys=filter.filter_keys,
            orderby=orderby,
            limit=limit,
            offset=offset,
            referrer=referrer,
            dataset=dataset,
        )

        if "error" not in result:
            events = [self.__make_event(evt) for evt in result["data"]]
            if should_bind_nodes:
                self.bind_nodes(events)
            return events

        return []

    def get_event_by_id(self, project_id, event_id, group_id=None):
        """
        Get an event given a project ID and event ID
        Returns None if an event cannot be found
        """

        event_id = normalize_event_id(event_id)

        if not event_id:
            return None

        event = Event(project_id=project_id, event_id=event_id)

        # Return None if there was no data in nodestore
        if len(event.data) == 0:
            return None

        if group_id is not None:
            # Set passed group_id if not a transaction
            if event.get_event_type() == "transaction":
                logger.warning("eventstore.passed-group-id-for-transaction")
                return event.for_group(Group.objects.get(id=group_id))
            else:
                event.group_id = group_id

        elif event.get_event_type() != "transaction":
            # Load group_id from Snuba if not a transaction
            raw_query_kwargs = {}
            if event.datetime > timezone.now() - timedelta(hours=1):
                # XXX: This is a hack to bust the snuba cache. We want to avoid the case where
                # we cache an empty result, since this can result in us failing to fetch new events
                # in some cases.
                raw_query_kwargs["conditions"] = [
                    ["timestamp", ">", datetime.fromtimestamp(random.randint(0, 1000000000))]
                ]
            dataset = (
                Dataset.IssuePlatform if event.get_event_type() == "generic" else Dataset.Events
            )
            try:
                result = snuba.raw_query(
                    dataset=dataset,
                    selected_columns=self.__get_columns(dataset),
                    start=event.datetime,
                    end=event.datetime + timedelta(seconds=1),
                    filter_keys={"project_id": [project_id], "event_id": [event_id]},
                    limit=1,
                    referrer="eventstore.get_event_by_id_nodestore",
                    **raw_query_kwargs,
                )
            except snuba.QueryOutsideRetentionError:
                # this can happen due to races.  We silently want to hide
                # this from callers.
                return None

            # Return None if the event from Nodestore was not yet written to Snuba
            if len(result["data"]) != 1:
                logger.warning(
                    "eventstore.missing-snuba-event",
                    extra={
                        "project_id": project_id,
                        "event_id": event_id,
                        "group_id": group_id,
                        "event_datetime": event.datetime,
                        "event_timestamp": event.timestamp,
                        "nodestore_insert": event.data.get("nodestore_insert"),
                        "received": event.data.get("received"),
                        "len_data": len(result["data"]),
                    },
                )
                return None

            event.group_id = result["data"][0]["group_id"]
            # Inject the snuba data here to make sure any snuba columns are available
            event._snuba_data = result["data"][0]

        return event

    def _get_dataset_for_event(self, event):
        if event.get_event_type() == "transaction":
            return snuba.Dataset.Transactions
        elif event.get_event_type() == "generic":
            return snuba.Dataset.IssuePlatform
        else:
            return snuba.Dataset.Discover

    def get_next_event_id(self, event, filter):
        """
        Returns (project_id, event_id) of a next event given a current event
        and any filters/conditions. Returns None if no next event is found.
        """
        assert filter, "You must provide a filter"

        if not event:
            return None

        filter = deepcopy(filter)
        filter.conditions = filter.conditions or []
        filter.conditions.extend(get_after_event_condition(event))
        filter.start = event.datetime
        dataset = self._get_dataset_for_event(event)
        return self.__get_event_id_from_filter(filter=filter, orderby=ASC_ORDERING, dataset=dataset)

    def get_prev_event_id(self, event, filter):
        """
        Returns (project_id, event_id) of a previous event given a current event
        and a filter. Returns None if no previous event is found.
        """
        assert filter, "You must provide a filter"

        if not event:
            return None

        filter = deepcopy(filter)
        filter.conditions = filter.conditions or []
        filter.conditions.extend(get_before_event_condition(event))
        # the previous event can have the same timestamp, add 1 second
        # to the end condition since it uses a less than condition
        filter.end = event.datetime + timedelta(seconds=1)
        dataset = self._get_dataset_for_event(event)
        return self.__get_event_id_from_filter(
            filter=filter, orderby=DESC_ORDERING, dataset=dataset
        )

    def __get_columns(self, dataset: Dataset):
        return [col.value.event_name for col in EventStorage.minimal_columns[dataset]]

    def __get_event_id_from_filter(self, filter=None, orderby=None, dataset=snuba.Dataset.Discover):
        columns = [Columns.EVENT_ID.value.alias, Columns.PROJECT_ID.value.alias]
        try:
            # This query uses the discover dataset to enable
            # getting events across both errors and transactions, which is
            # required when doing pagination in discover
            result = snuba.aliased_query(
                selected_columns=columns,
                conditions=filter.conditions,
                filter_keys=filter.filter_keys,
                start=filter.start,
                end=filter.end,
                limit=1,
                referrer="eventstore.get_next_or_prev_event_id",
                orderby=orderby,
                dataset=dataset,
            )
        except (snuba.QueryOutsideRetentionError, snuba.QueryOutsideGroupActivityError):
            # This can happen when the date conditions for paging
            # and the current event generate impossible conditions.
            return None

        if "error" in result or len(result["data"]) == 0:
            return None

        row = result["data"][0]

        return (str(row["project_id"]), str(row["event_id"]))

    def __make_event(self, snuba_data):
        event_id = snuba_data[Columns.EVENT_ID.value.event_name]
        project_id = snuba_data[Columns.PROJECT_ID.value.event_name]

        return Event(event_id=event_id, project_id=project_id, snuba_data=snuba_data)

    def get_unfetched_transactions(
        self,
        filter,
        orderby=None,
        limit=DEFAULT_LIMIT,
        offset=DEFAULT_OFFSET,
        referrer="eventstore.get_unfetched_transactions",
    ):
        """
        Get transactions from Snuba, without node data loaded.
        """
        assert filter, "You must provide a filter"
        cols = self.__get_columns(snuba.Dataset.Transactions)
        orderby = orderby or DESC_ORDERING

        result = snuba.aliased_query(
            selected_columns=cols,
            start=filter.start,
            end=filter.end,
            conditions=filter.conditions,
            filter_keys=filter.filter_keys,
            orderby=orderby,
            limit=limit,
            offset=offset,
            referrer=referrer,
            dataset=snuba.Dataset.Transactions,
        )

        if "error" not in result:
            events = [self.__make_transaction(evt) for evt in result["data"]]
            return events

        return []

    def __make_transaction(self, snuba_data):
        event_id = snuba_data[Columns.EVENT_ID.value.event_name]
        project_id = snuba_data[Columns.PROJECT_ID.value.event_name]

        return Event(event_id=event_id, project_id=project_id, snuba_data=snuba_data)
