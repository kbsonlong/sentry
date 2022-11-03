# Generated by Django 2.2.28 on 2022-11-01 02:43

from django.db import migrations

from sentry.new_migrations.migrations import CheckedMigration
from sentry.utils.query import RangeQuerySetWrapperWithProgressBar


def cleanup_pinned_searches(apps, schema_editor):
    SavedSearch = apps.get_model("sentry", "SavedSearch")

    # This marks existing saved searche visibility in two ways:
    #
    # SavedSearch that have a `owner_id` become visibility=`owner_pinned`
    #
    # All other SavedSearch entires are marked as visibility=`organization`.
    # This was the default for all saved searches before allow a visibility to
    # be set.
    for search in RangeQuerySetWrapperWithProgressBar(SavedSearch.objects.all()):
        if search.owner is not None:
            # Explicitly not using the constant from the model, since it may be
            # outdated at the time the migration is run
            search.visibility = "owner_pinned"
        else:
            search.visibility = "organization"

        search.save()


class Migration(CheckedMigration):
    # This flag is used to mark that a migration shouldn't be automatically run in production. For
    # the most part, this should only be used for operations where it's safe to run the migration
    # after your code has deployed. So this should not be used for most operations that alter the
    # schema of a table.
    # Here are some things that make sense to mark as dangerous:
    # - Large data migrations. Typically we want these to be run manually by ops so that they can
    #   be monitored and not block the deploy for a long period of time while they run.
    # - Adding indexes to large tables. Since this can take a long time, we'd generally prefer to
    #   have ops run this and not block the deploy. Note that while adding an index is a schema
    #   change, it's completely safe to run the operation after the code has deployed.
    is_dangerous = False

    # This flag is used to decide whether to run this migration in a transaction or not. Generally
    # we don't want to run in a transaction here, since for long running operations like data
    # back-fills this results in us locking an increasing number of rows until we finally commit.
    atomic = False

    dependencies = [
        ("sentry", "0338_add_saved_search_visibility"),
    ]

    operations = [
        migrations.RunPython(
            cleanup_pinned_searches,
            migrations.RunPython.noop,
            hints={"tables": ["sentry_savedsearch"]},
        ),
    ]