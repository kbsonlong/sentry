# Generated by Django 2.2.28 on 2023-02-23 20:59

from django.db import migrations, models

import sentry.db.models.fields.hybrid_cloud_foreign_key
from sentry.new_migrations.migrations import CheckedMigration


def auditlog_organization_migrations():
    database_operations = [
        migrations.AlterField(
            model_name="auditlogentry",
            name="organization",
            field=sentry.db.models.fields.foreignkey.FlexibleForeignKey(
                to="sentry.Organization", db_constraint=False, db_index=True, null=False
            ),
        ),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="auditlogentry",
            name="organization",
            field=sentry.db.models.fields.hybrid_cloud_foreign_key.HybridCloudForeignKey(
                "sentry.Organization", db_index=True, on_delete="CASCADE"
            ),
        ),
        migrations.RemoveIndex(
            model_name="auditlogentry",
            name="sentry_audi_organiz_588b1e_idx",
        ),
        migrations.RemoveIndex(
            model_name="auditlogentry",
            name="sentry_audi_organiz_c8bd18_idx",
        ),
        migrations.RenameField(
            model_name="auditlogentry",
            old_name="organization",
            new_name="organization_id",
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(
                fields=["organization_id", "datetime"], name="sentry_audi_organiz_c8bd18_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(
                fields=["organization_id", "event", "datetime"],
                name="sentry_audi_organiz_588b1e_idx",
            ),
        ),
    ]

    return database_operations + [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]


def activityuser_migrations():
    database_operations = [
        migrations.AlterField(
            model_name="activity",
            name="user",
            field=sentry.db.models.fields.foreignkey.FlexibleForeignKey(
                to="sentry.User", db_constraint=False, db_index=True, null=True
            ),
        ),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="activity",
            name="user",
            field=sentry.db.models.fields.hybrid_cloud_foreign_key.HybridCloudForeignKey(
                "sentry.User", db_index=True, on_delete="SET_NULL", null=True
            ),
        ),
        migrations.RenameField(
            model_name="activity",
            old_name="user",
            new_name="user_id",
        ),
    ]

    return database_operations + [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]


def apiauthorization_user_migrations():
    database_operations = [
        migrations.AlterField(
            model_name="apiauthorization",
            name="application",
            field=sentry.db.models.fields.foreignkey.FlexibleForeignKey(
                to="sentry.ApiApplication", db_constraint=False, db_index=True, null=True
            ),
        ),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="apiauthorization",
            name="application",
            field=sentry.db.models.fields.hybrid_cloud_foreign_key.HybridCloudForeignKey(
                "sentry.ApiApplication", db_index=True, on_delete="CASCADE", null=True
            ),
        ),
        migrations.RenameField(
            model_name="apiauthorization",
            old_name="application",
            new_name="application_id",
        ),
        migrations.AlterUniqueTogether("apiauthorization", {("user", "application_id")}),
    ]

    return database_operations + [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]


def apigrant_user_migrations():
    database_operations = [
        migrations.AlterField(
            model_name="apigrant",
            name="application",
            field=sentry.db.models.fields.foreignkey.FlexibleForeignKey(
                to="sentry.ApiApplication", db_constraint=False, db_index=True, null=False
            ),
        ),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="apigrant",
            name="application",
            field=sentry.db.models.fields.hybrid_cloud_foreign_key.HybridCloudForeignKey(
                "sentry.ApiApplication", db_index=True, on_delete="CASCADE"
            ),
        ),
        migrations.RenameField(
            model_name="apigrant",
            old_name="application",
            new_name="application_id",
        ),
    ]

    return database_operations + [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]


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

    dependencies = [
        ("sentry", "0360_authenticator_config_type_change"),
    ]

    operations = auditlog_organization_migrations() + activityuser_migrations()
