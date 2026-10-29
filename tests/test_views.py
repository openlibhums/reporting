__copyright__ = "Copyright 2017 Birkbeck, University of London"
__author__ = "Andy Byers"
__license__ = "AGPL v3"
__maintainer__ = "Birkbeck Centre for Technology and Publishing"

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from unittest import mock

from django.http import Http404, QueryDict
from django.test import TestCase
from django.utils import timezone

from repository import install as repo_install
from submission import models as sm_models
from security.decorators import editor_or_manager
from utils.install import update_settings
from utils.testing import helpers
from plugins.reporting import forms
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


class TestWorkflowReportDateRange(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.press = helpers.create_press()
        cls.press.save()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        update_settings()
        reporting_plugin_settings.install()

        cls.editor = helpers.create_editor(
            cls.journal_one,
            email="reporting_workflow_editor@janeway.systems",
        )
        cls.published = {}
        for year, month in ((2024, 12), (2025, 3), (2026, 2), (2026, 7)):
            cls.published[(year, month)] = sm_models.Article.objects.create(
                journal=cls.journal_one,
                title=f"Published {year}-{month:02d}",
                stage=sm_models.STAGE_PUBLISHED,
                date_published=timezone.make_aware(
                    timezone.datetime(year, month, 15, 12),
                ),
            )

    def articles_for(self, start_month, end_month):
        request = helpers.get_request(
            user=self.editor,
            press=self.press,
            journal=self.journal_one,
        )
        request.GET = QueryDict(
            f"start_month={start_month}&end_month={end_month}",
        )
        with mock.patch.object(views, "render") as render:
            views.report_workflow(request)
        context = render.call_args.args[2]
        return set(context['article_list'])

    def test_range_across_years_includes_the_end_year(self):
        self.assertEqual(
            self.articles_for('2025-01', '2026-12'),
            {
                self.published[(2025, 3)],
                self.published[(2026, 2)],
                self.published[(2026, 7)],
            },
        )

    def test_start_month_after_end_month(self):
        self.assertEqual(
            self.articles_for('2024-09', '2026-03'),
            {
                self.published[(2024, 12)],
                self.published[(2025, 3)],
                self.published[(2026, 2)],
            },
        )

    def test_range_is_inclusive_of_whole_months(self):
        self.assertEqual(
            self.articles_for('2026-02', '2026-02'),
            {self.published[(2026, 2)]},
        )


class TestReportingJournalScope(TestCase):
    """An editor of one journal must not see another journal's reports."""

    @classmethod
    def setUpTestData(cls):
        cls.press = helpers.create_press()
        cls.press.save()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        update_settings()
        reporting_plugin_settings.install()

        cls.editor = helpers.create_editor(
            cls.journal_one,
            email="reporting_scope_editor@janeway.systems",
        )
        cls.staff = helpers.create_user(
            "reporting_scope_staff@janeway.systems",
            is_staff=True,
            is_active=True,
        )
        cls.article_two = helpers.create_article(cls.journal_two)

    def editor_request(self):
        return helpers.get_request(
            user=self.editor,
            press=self.press,
            journal=self.journal_one,
        )

    def test_editor_gets_own_journal(self):
        request = self.editor_request()
        self.assertEqual(views.report_journal(request), self.journal_one)
        self.assertEqual(
            views.report_journal(request, str(self.journal_one.pk)),
            self.journal_one,
        )

    def test_editor_cannot_pick_another_journal(self):
        with self.assertRaises(Http404):
            views.report_journal(self.editor_request(), self.journal_two.pk)

    def test_staff_can_pick_any_journal_or_the_press(self):
        request = helpers.get_request(
            user=self.staff,
            press=self.press,
            journal=self.journal_one,
        )
        self.assertEqual(
            views.report_journal(request, self.journal_two.pk),
            self.journal_two,
        )
        self.assertIsNone(views.report_journal(request))

    def test_non_staff_on_press_site_gets_nothing(self):
        request = helpers.get_request(user=self.editor, press=self.press)
        with self.assertRaises(Http404):
            views.report_journal(request)

    def test_journal_id_views_refuse_another_journal(self):
        journal_id = self.journal_two.pk
        for name in (
            'report_articles',
            'report_geo',
            'report_journal_citations',
            'report_crossref_dois',
            'report_crossref_dois_crosscheck',
        ):
            view = getattr(views, name)
            with self.subTest(view=name):
                with self.assertRaises(Http404):
                    view(self.editor_request(), journal_id=journal_id)

    def test_citing_works_refuses_another_journals_article(self):
        with self.assertRaises(Http404):
            views.report_article_citing_works(
                self.editor_request(),
                journal_id=self.journal_one.pk,
                article_id=self.article_two.pk,
            )

    def test_journal_picker_only_offers_own_journal(self):
        form = forms.ArticleMetricsForm(
            user=self.editor,
            journal=self.journal_one,
        )
        self.assertEqual(
            list(form.fields['journal'].queryset),
            [self.journal_one],
        )
        form = forms.ArticleMetricsForm(
            {'journal': self.journal_two.pk},
            user=self.editor,
            journal=self.journal_one,
        )
        self.assertFalse(form.is_valid())
