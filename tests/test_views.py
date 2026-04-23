__copyright__ = "Copyright 2017 Birkbeck, University of London"
__author__ = "Andy Byers"
__license__ = "AGPL v3"
__maintainer__ = "Birkbeck Centre for Technology and Publishing"

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from repository import install as repo_install
from security.decorators import editor_or_manager
from utils.install import update_settings
from utils.testing import helpers
from plugins.reporting import plugin_settings as reporting_plugin_settings
from plugins.reporting import views


class TestReportingAccess(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.press = helpers.create_press()
        cls.press.save()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        update_settings()

        reporting_plugin_settings.install()

        cls.repo_manager = helpers.create_user(
            "reporting_repo_manager@janeway.systems",
        )
        cls.repo_manager.is_active = True
        cls.repo_manager.save()

        cls.editor = helpers.create_editor(
            cls.journal_one,
            email="reporting_editor@janeway.systems",
        )

        cls.repository, cls.subject = helpers.create_repository(
            cls.press,
            [cls.repo_manager],
            [],
        )
        repo_install.load_settings(cls.repository)

    def test_repository_manager_can_access_reporting_index(self):
        request = helpers.get_request(
            user=self.repo_manager,
            press=self.press,
            repository=self.repository,
        )
        check = editor_or_manager(lambda r: True)
        response = check(request)
        self.assertTrue(response)

    def test_editor_can_access_reporting_index(self):
        request = helpers.get_request(
            user=self.editor,
            press=self.press,
            journal=self.journal_one,
        )
        check = editor_or_manager(lambda r: True)
        response = check(request)
        self.assertTrue(response)

    def test_anonymous_user_redirected_from_reporting_index(self):
        request = helpers.get_request(
            user=AnonymousUser(),
            press=self.press,
            journal=self.journal_one,
        )
        check = editor_or_manager(lambda r: True)
        response = check(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_repository_manager_denied_journal_only_report(self):
        request = helpers.get_request(
            user=self.repo_manager,
            press=self.press,
            repository=self.repository,
        )
        with self.assertRaises(PermissionDenied):
            views.report_articles(request, journal_id=self.journal_one.pk)
