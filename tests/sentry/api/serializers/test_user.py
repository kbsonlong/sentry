from sentry.api.serializers import serialize
from sentry.api.serializers.models.user import DetailedSelfUserSerializer, DetailedUserSerializer
from sentry.models import Authenticator, AuthIdentity, AuthProvider, UserEmail, UserPermission
from sentry.models.authenticator import available_authenticators
from sentry.testutils import TestCase
from sentry.testutils.servermode import control_silo_test


@control_silo_test
class UserSerializerTest(TestCase):
    def test_simple(self):
        user = self.create_user()

        result = serialize(user)
        assert result["id"] == str(user.id)
        assert result["has2fa"] is False

        Authenticator.objects.create(
            type=available_authenticators(ignore_backup=True)[0].type, user=user
        )

        result = serialize(user)
        assert result["id"] == str(user.id)
        assert result["has2fa"] is True
        assert len(result["emails"]) == 1
        assert result["emails"][0]["email"] == user.email
        assert result["emails"][0]["is_verified"]
        assert result["isSuperuser"] is False
        assert result["experiments"] == {}

    def test_no_useremail(self):
        user = self.create_user()

        UserEmail.objects.all().delete()
        assert UserEmail.objects.all().count() == 0

        result = serialize(user)
        assert len(result["emails"]) == 0

    def test_is_superuser(self):
        """Test that the user is a superuser"""
        user = self.create_user(is_superuser=True)

        result = serialize(user)
        assert result["isSuperuser"] is True


@control_silo_test
class DetailedUserSerializerTest(TestCase):
    def test_simple(self):
        user = self.create_user()
        UserPermission.objects.create(user=user, permission="foo")

        org = self.create_organization(owner=user)

        auth_provider = AuthProvider.objects.create(organization=org, provider="dummy")
        auth_identity = AuthIdentity.objects.create(
            auth_provider=auth_provider, ident=user.email, user=user
        )
        auth = Authenticator.objects.create(
            type=available_authenticators(ignore_backup=True)[0].type, user=user
        )

        result = serialize(user, user, DetailedUserSerializer())
        assert result["id"] == str(user.id)
        assert result["has2fa"] is True
        assert len(result["emails"]) == 1
        assert result["emails"][0]["email"] == user.email
        assert result["emails"][0]["is_verified"]
        assert "identities" in result
        assert len(result["identities"]) == 1
        assert result["identities"][0]["id"] == str(auth_identity.id)
        assert result["identities"][0]["name"] == auth_identity.ident
        assert "authenticators" in result
        assert len(result["authenticators"]) == 1
        assert result["authenticators"][0]["id"] == str(auth.id)
        assert result["canReset2fa"] is True

        self.create_organization(owner=user)
        result = serialize(user, user, DetailedUserSerializer())
        assert result["canReset2fa"] is False


@control_silo_test
class DetailedSelfUserSerializerTest(TestCase):
    def test_simple(self):
        user = self.create_user()
        UserPermission.objects.create(user=user, permission="foo")

        org = self.create_organization(owner=user)

        auth_provider = AuthProvider.objects.create(organization=org, provider="dummy")
        auth_identity = AuthIdentity.objects.create(
            auth_provider=auth_provider, ident=user.email, user=user
        )
        auth = Authenticator.objects.create(
            type=available_authenticators(ignore_backup=True)[0].type, user=user
        )

        result = serialize(user, user, DetailedSelfUserSerializer())
        assert result["id"] == str(user.id)
        assert result["has2fa"] is True
        assert len(result["emails"]) == 1
        assert result["emails"][0]["email"] == user.email
        assert result["emails"][0]["is_verified"]
        assert "identities" in result
        assert len(result["identities"]) == 1
        assert result["identities"][0]["id"] == str(auth_identity.id)
        assert result["identities"][0]["name"] == auth_identity.ident
        assert "authenticators" in result
        assert len(result["authenticators"]) == 1
        assert result["authenticators"][0]["id"] == str(auth.id)
        assert result["permissions"] == ["foo"]
