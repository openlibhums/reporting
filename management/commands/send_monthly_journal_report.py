import csv
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand
from django.utils import timezone, translation
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

from plugins.reporting import models, logic
from submission import models as submission_models
from journal import models as journal_models
from core import files
from utils import setting_handler

HEADERS = [
    'Article Title',
    'Section',
    'Date Submitted',
    'Date Accepted',
    'Date Published',
    'Views',
    'Downloads',
    'Citations',
    'Total Accesses',
]


def get_dates():
    today = timezone.now()
    d = today - relativedelta(months=1)

    first_day = timezone.datetime(d.year, d.month, 1)
    last_day = timezone.datetime(today.year, today.month, 1) - relativedelta(days=1)
    return timezone.make_aware(first_day), timezone.make_aware(last_day)


def send_email(recipient, journal, csv_path):
    from_email = setting_handler.get_setting('general', 'from_address', journal).value
    from_string = "{} <{}>".format(journal.name, from_email)
    subject = 'Journal Monthly Report'
    html = "<p>Please find the monthly report for {} attached.</p>".format(journal.name)

    msg = EmailMultiAlternatives(subject, strip_tags(html), from_string, to=[recipient.user.email])
    msg.attach_alternative(html, "text/html")

    with open(csv_path) as file:
        msg.attach(file.name, file.read(), 'text/csv')

    return msg.send()


class Command(BaseCommand):
    """ Sends out a monthly journal report to recipients."""

    help = "Sends out a monthly journal report to recipients"

    def add_arguments(self, parser):
        parser.add_argument('--journal_code')

    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)
        journal_code = options.get('journal_code')
        journals = journal_models.Journal.objects.all()
        start_date, end_date = get_dates()

        if journal_code:
            journals = journals.filter(code=journal_code)

        if not journals:
            print('No journals found.')
            exit()

        for journal in journals:
            recipients = models.JournalReportRecipient.objects.filter(journal=journal)

            # Generate a CSV for each journal
            csv_file_path = files.get_temp_file_path_from_name('journal_{}.csv'.format(journal.code))
            with open(csv_file_path, "w") as f:
                wr = csv.writer(f, quoting=csv.QUOTE_ALL)
                wr.writerow(HEADERS)

                for article in logic.get_articles_with_counts(journal, start_date, end_date):
                    row = [
                        article.title,
                        article.section.name if article.section else '',
                        article.date_submitted,
                        article.date_accepted,
                        article.date_published,
                        article.views,
                        article.downloads,
                        article.citations,
                        article.views + article.downloads,
                    ]
                    wr.writerow(row)

            if not recipients:
                print('No recipients found for {}'.format(journal.name))
                continue

            for recipient in recipients:
                send_email(recipient, journal, csv_file_path)

            files.unlink_temp_file(csv_file_path)
