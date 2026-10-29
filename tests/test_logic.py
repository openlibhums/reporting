from datetime import timedelta
from io import StringIO

from django.test import TestCase
from django.utils import timezone

from identifiers import models as id_models
from plugins.reporting import logic
from submission import models as sm_models
from utils.testing import helpers

class TestCrossRefDOIRreport(TestCase):
    def setUp(self):
        self.press = helpers.create_press()
        self.journal_one, self.journal_two = helpers.create_journals()
        self.article_one, _= sm_models.Article.objects.get_or_create(
            journal = self.journal_one,
            title="Test article 1",
            stage=sm_models.STAGE_PUBLISHED,
        )
        self.identifier_one, _ = id_models.Identifier.objects.get_or_create(
            article=self.article_one,
            id_type="doi",
            identifier="10.0001/test"
        )
        self.article_two, _= sm_models.Article.objects.get_or_create(
            journal = self.journal_two,
            title="Test article two",
            stage=sm_models.STAGE_PUBLISHED,
        )
        self.identifier_one, _ = id_models.Identifier.objects.get_or_create(
            article=self.article_two,
            id_type="doi",
            identifier="10.0002/test"
        )


    def test_journal_tsv_report(self):
        # Prepare
        file_like = StringIO()
        # Expect
        expected = 'DOI\tURL\n10.0001/test\thttp://localhost/TST/article/id/1/\n'
        # Do
        logic.write_doi_tsv_report(file_like, journal=self.journal_one)
        file_like.seek(0)
        result = file_like.read()
        # Assert
        self.assertEqual(expected, result)



    def test_press_tsv_report(self):
        # Prepare
        file_like = StringIO()
        # Expect
        expected = 'DOI\tURL\n10.0001/test\thttp://localhost/TST/article/id/3/\n10.0002/test\thttp://localhost/TSA/article/id/4/\n'
        # Do
        logic.write_doi_tsv_report(file_like)
        file_like.seek(0)
        result = file_like.read()
        # Assert
        self.assertEqual(expected, result)


class TestJournalScopedReports(TestCase):
    def setUp(self):
        self.press = helpers.create_press()
        self.journal_one, self.journal_two = helpers.create_journals()
        for journal in (self.journal_one, self.journal_two):
            licence = sm_models.Licence.objects.create(
                journal=journal,
                name="CC BY 4.0",
                short_name="CC BY 4.0",
                url="https://creativecommons.org/licenses/by/4.0/",
            )
            sm_models.Article.objects.create(
                journal=journal,
                license=licence,
                title="Published article",
                stage=sm_models.STAGE_PUBLISHED,
                date_published=timezone.now() - timedelta(days=1),
            )

    def test_license_report_filters_by_journal(self):
        start = timezone.now() - timedelta(days=7)
        end = timezone.now()
        everything = logic.license_report(start, end)
        one = logic.license_report(start, end, journal=self.journal_one)
        self.assertEqual(sum(row['lcount'] for row in one), 1)
        self.assertEqual(sum(row['lcount'] for row in everything), 2)
