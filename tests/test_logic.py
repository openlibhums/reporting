from io import StringIO

from django.test import TestCase

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


