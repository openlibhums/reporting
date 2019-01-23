import csv
import os
from datetime import date, timedelta

from django.utils import timezone
from django.conf import settings
from django.template.defaultfilters import strip_tags

from submission import models as sm
from metrics import models as mm
from core.files import serve_temp_file


def get_first_day(dt, d_years=0, d_months=0):
    # d_years, d_months are "deltas" to apply to dt
    y, m = dt.year + d_years, dt.month + d_months
    a, m = divmod(m-1, 12)
    return date(y+a, m+1, 1)


def get_last_day(dt):
    return get_first_day(dt, 0, 1) + timedelta(-1)


def get_start_and_end_date(request):
    d = date.today()
    start_date = request.GET.get('start_date', get_first_day(d))
    last_date = request.GET.get('end_date', get_last_day(d))

    return start_date, last_date


def get_articles(journal, start_date, end_date):
    dt = timezone.now()

    articles = sm.Article.objects.filter(
        date_published__lte=dt,
        journal=journal
    )

    for article in articles:
        article.views = mm.ArticleAccess.objects.filter(
            article=article,
            accessed__gte=start_date,
            accessed__lte=end_date,
            type='view'
        )
        article.downloads = mm.ArticleAccess.objects.filter(
            article=article,
            accessed__gte=start_date,
            accessed__lte=end_date,
            type='download'
        )

        article.total_views = article.views.count() + \
                              article.historicarticleaccess.views
        article.total_downloads = article.downloads.count() + \
                                  article.historicarticleaccess.downloads

    return articles


def get_accesses(journal, start_date, end_date):
    views = mm.ArticleAccess.objects.filter(
        article__journal=journal,
        type='view',
        accessed__gte=start_date,
        accessed__lte=end_date,
    ).count()

    downloads = mm.ArticleAccess.objects.filter(
        article__journal=journal,
        type='download',
        accessed__gte=start_date,
        accessed__lte=end_date,
    ).count()

    return views, downloads


def export_csv(rows):
    filename = '{0}.csv'.format(timezone.now())
    full_path = os.path.join(settings.BASE_DIR, 'files', 'temp', filename)

    with open(full_path, 'w') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',')
        for row in rows:
            csv_writer.writerow(row)

    return serve_temp_file(
        full_path,
        filename
    )


def export_journal_csv(journals):
    all_rows = list()
    header_row = [
        'Name',
        'Views',
        'Downloads',
    ]
    all_rows.append(header_row)

    for journal in journals:
        row = [
            journal.name,
            journal.views,
            journal.downloads
        ]
        all_rows.append(row)

    return export_csv(all_rows)


def export_article_csv(articles):
    all_rows = list()
    header_row = [
        'Title',
        'Date Published',
        'Views in Time Period',
        'Downloads in Time Period',
        'Historic Views',
        'Historic Downloads',
        'Total Views',
        'Total Downloads',
    ]
    all_rows.append(header_row)

    for article in articles:
        row = [
            strip_tags(article.title),
            article.date_published,
            article.views.count(),
            article.downloads.count(),
            article.historicarticleaccess.views,
            article.historicarticleaccess.downloads,
            article.total_views,
            article.total_downloads
        ]
        all_rows.append(row)

    return export_csv(all_rows)


def export_production_csv(production_assignments):
    all_rows = list()
    header_row = [
        'Title',
        'Journal',
        'Typesetter',
        'Assigned',
        'Accepted',
        'Completed',
        'Time to Acceptance',
        'Time to Completion',
    ]
    all_rows.append(header_row)

    for assignment in production_assignments:
        row = [
            assignment.assignment.article.title,
            assignment.assignment.article.journal.code,
            assignment.typesetter,
            assignment.assigned,
            assignment.accepted,
            assignment.completed,
            assignment.time_to_acceptance,
            assignment.time_to_completion,
        ]
        all_rows.append(row)

    return export_csv(all_rows)


def average(lst):
    if lst:
        return round(sum(lst) / len(lst), 2)
    else:
        return 0
