from django.db import models


class JournalReportRecipient(models.Model):
    user = models.ForeignKey(
        'core.Account',
        help_text="The user who will receive the report",
    )
    journal = models.ForeignKey(
        'journal.Journal',
        help_text="The journal that the user will receive the report for",
    )


class JournalReportReceipt(models.Model):
    recipient = models.ForeignKey(JournalReportRecipient)
    sent_on = models.DateTimeField(auto_now_add=True)


class JournalReportStats(models.Model):
    article = models.ForeignKey('submission.Article')
    date = models.DateField()
    views = models.PositiveIntegerField()
    downloads = models.PositiveIntegerField()
    citations = models.PositiveIntegerField()
