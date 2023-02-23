import logging
from typing import Optional, Sequence, Tuple

from sentry import features, quotas
from sentry.dynamic_sampling.models.adjustment_models import AdjustedModel
from sentry.dynamic_sampling.models.adjustment_models import DSProject as DSProject
from sentry.dynamic_sampling.models.transaction_adjustment_model import adjust_sample_rate
from sentry.dynamic_sampling.prioritise_projects import fetch_projects_with_total_volumes
from sentry.dynamic_sampling.prioritise_transactions import (
    ProjectTransactions,
    fetch_transactions_with_total_volumes,
)
from sentry.dynamic_sampling.rules.helpers.prioritise_project import _generate_cache_key
from sentry.dynamic_sampling.rules.helpers.prioritize_transactions import (
    set_transactions_resampling_rates,
)
from sentry.dynamic_sampling.rules.utils import OrganizationId, ProjectId, get_redis_client_for_ds
from sentry.models import Organization, Project
from sentry.tasks.base import instrumented_task
from sentry.tasks.relay import schedule_invalidate_project_config
from sentry.utils import metrics

CHUNK_SIZE = 1000
MAX_SECONDS = 60
CACHE_KEY_TTL = 24 * 60 * 60 * 1000  # in milliseconds

logger = logging.getLogger(__name__)


@instrumented_task(
    name="sentry.dynamic_sampling.tasks.prioritise_projects",
    queue="dynamicsampling",
    default_retry_delay=5,
    max_retries=5,
    soft_time_limit=2 * 60 * 60,  # 2hours
    time_limit=2 * 60 * 60 + 5,
)  # type: ignore
def prioritise_projects() -> None:
    metrics.incr("sentry.tasks.dynamic_sampling.prioritise_projects.start", sample_rate=1.0)
    with metrics.timer("sentry.tasks.dynamic_sampling.prioritise_projects", sample_rate=1.0):
        for org_id, projects_with_tx_count in fetch_projects_with_total_volumes().items():
            process_projects_sample_rates.delay(org_id, projects_with_tx_count)


@instrumented_task(
    name="sentry.dynamic_sampling.process_projects_sample_rates",
    queue="dynamicsampling",
    default_retry_delay=5,
    max_retries=5,
    soft_time_limit=25 * 60,  # 25 mins
    time_limit=2 * 60 + 5,
)  # type: ignore
def process_projects_sample_rates(
    org_id: OrganizationId, projects_with_tx_count: Sequence[Tuple[ProjectId, int]]
) -> None:
    """
    Takes a single org id and a list of project ids
    """
    organization = Organization.objects.get_from_cache(id=org_id)
    # Check if feature flag is enabled:
    if features.has("organizations:ds-prioritise-by-project-bias", organization):
        with metrics.timer("sentry.tasks.dynamic_sampling.process_projects_sample_rates.core"):
            adjust_sample_rates(org_id, projects_with_tx_count)


def adjust_sample_rates(
    org_id: int, projects_with_tx_count: Sequence[Tuple[ProjectId, int]]
) -> None:
    """
    This function apply model and adjust sample rate per project in org
    and store it in DS redis cluster, then we invalidate project config
    so relay can reread it, and we'll inject it from redis cache.
    """
    projects = []
    project_ids_with_counts = {}
    for project_id, count_per_root in projects_with_tx_count:
        project_ids_with_counts[project_id] = count_per_root

    for project in Project.objects.get_many_from_cache(project_ids_with_counts.keys()):
        sample_rate = quotas.get_blended_sample_rate(project)
        if sample_rate is None:
            continue
        projects.append(
            DSProject(
                id=project.id,
                count_per_root=project_ids_with_counts[project.id],
                blended_sample_rate=sample_rate,
            )
        )

    model = AdjustedModel(projects=projects)
    ds_projects = model.adjust_sample_rates()

    redis_client = get_redis_client_for_ds()
    with redis_client.pipeline(transaction=False) as pipeline:
        for ds_project in ds_projects:
            # hash, key, value
            cache_key = _generate_cache_key(org_id=org_id)
            pipeline.hset(
                cache_key,
                ds_project.id,
                ds_project.new_sample_rate,  # redis stores is as string
            )
            pipeline.pexpire(cache_key, CACHE_KEY_TTL)
            schedule_invalidate_project_config(
                project_id=ds_project.id, trigger="dynamic_sampling_prioritise_project_bias"
            )
        pipeline.execute()


@instrumented_task(
    name="sentry.dynamic_sampling.tasks.prioritise_transactions",
    queue="dynamicsampling",
    default_retry_delay=5,
    max_retries=5,
    soft_time_limit=25 * 60,  # 25 mins
    time_limit=2 * 60 + 5,
)  # type: ignore
def prioritise_transactions() -> None:
    """
    A task that retrieves all relative transaction counts from all projects in all orgs
    and invokes a task for rebalancing transaction sampling rates within each project
    """
    metrics.incr("sentry.tasks.dynamic_sampling.prioritise_transactions.start", sample_rate=1.0)
    current_org: Optional[Organization] = None
    current_org_enabled = False
    with metrics.timer("sentry.tasks.dynamic_sampling.prioritise_transactions", sample_rate=1.0):
        for project_transactions in fetch_transactions_with_total_volumes():
            if not current_org or current_org.id != project_transactions.org_id:
                current_org = Organization.objects.get_from_cache(id=project_transactions.org_id)
                current_org_enabled = features.has(
                    "organizations:ds-prioritise-by-transaction-bias", current_org
                )
            if current_org_enabled:
                process_transaction_biases.delay(project_transactions)


@instrumented_task(
    name="sentry.dynamic_sampling.process_transaction_biases",
    queue="dynamicsampling",
    default_retry_delay=5,
    max_retries=5,
    soft_time_limit=25 * 60,  # 25 mins
    time_limit=2 * 60 + 5,
)  # type: ignore
def process_transaction_biases(project_transactions: ProjectTransactions) -> None:
    """
    A task that given a project relative transaction counts calculates rebalancing
    sampling rates based on the overall desired project sampling rate.
    """
    # TODO RaduW Do we want this to be configurable, is 10 OK ?
    MAX_EXPLICIT_TRANSACTIONS = 10

    org_id = project_transactions.org_id
    project_id = project_transactions.project_id
    transactions = project_transactions.transaction_counts
    project = Project.objects.get_from_cache(id=project_id)
    sample_rate = quotas.get_blended_sample_rate(project)

    if sample_rate is None:
        # no sampling => no rebalancing
        return

    named_rates, global_rate = adjust_sample_rate(
        transactions=transactions,
        rate=sample_rate,
        max_explicit_transactions=MAX_EXPLICIT_TRANSACTIONS,
    )

    set_transactions_resampling_rates(
        org_id=org_id,
        proj_id=project_id,
        named_rates=named_rates,
        default_rate=global_rate,
        ttl_ms=CACHE_KEY_TTL,
    )

    schedule_invalidate_project_config(
        project_id=project_id, trigger="dynamic_sampling_prioritise_transaction_bias"
    )
