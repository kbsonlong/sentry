from sentry import tsdb
from sentry.tsdb.base import TSDBModel
from sentry.types.issues import GroupCategory

ISSUE_TSDB_GROUP_MODELS = {
    GroupCategory.ERROR: tsdb.models.group,
    GroupCategory.PERFORMANCE: tsdb.models.group_performance,
    GroupCategory.PROFILE: tsdb.models.group,
}
ISSUE_TSDB_USER_GROUP_MODELS = {
    GroupCategory.ERROR: tsdb.models.users_affected_by_group,
    GroupCategory.PERFORMANCE: tsdb.models.users_affected_by_perf_group,
    GroupCategory.PROFILE: tsdb.models.users_affected_by_group,
}


def get_issue_tsdb_group_model(issue_category: GroupCategory) -> TSDBModel:
    return ISSUE_TSDB_GROUP_MODELS.get(issue_category, tsdb.models.group_generic)


def get_issue_tsdb_user_group_model(issue_category: GroupCategory) -> TSDBModel:
    return ISSUE_TSDB_USER_GROUP_MODELS.get(
        issue_category, tsdb.models.users_affected_by_generic_group
    )
