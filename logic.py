import csv
import os
from datetime import date, timedelta

from django.utils import timezone
from django.conf import settings
from django.template.defaultfilters import strip_tags

from submission import models as sm
from metrics import models as mm
from core.files import serve_temp_file
from utils.function_cache import cache


def get_first_day(dt, d_years=0, d_months=0):
    # d_years, d_months are "deltas" to apply to dt
    y, m = dt.year + d_years, dt.month + d_months
    a, m = divmod(m - 1, 12)
    return date(y+a, m + 1, 1)


def get_last_day(dt):
    return get_first_day(dt, 0, 1) + timedelta(-1)


def get_start_and_end_date(request):
    d = date.today()
    start_date = request.GET.get('start_date', get_first_day(d))
    last_date = request.GET.get('end_date', get_last_day(d))

    return start_date, last_date


def get_articles(journal, start_date, end_date):
    dt = timezone.now()

    if journal:
        articles = sm.Article.objects.filter(
            date_published__lte=dt,
            journal=journal
        ).select_related('section')
    else:
        articles = sm.Article.objects.filter(
            date_published__lte=dt,
        ).select_related('section')

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


def export_article_csv(articles, data):
    all_rows = list()

    info_header_row = [
        'Articles',
        'Submissions',
        'Published Articles',
        'Rejected Articles',
        'Views',
        'Downloads',
    ]
    all_rows.append(info_header_row)

    row = [
        data[0].get('articles').count(),
        data[0].get('submissions').count(),
        data[0].get('published_articles').count(),
        data[0].get('rejected_articles').count(),
        data[0].get('views').count(),
        data[0].get('downloads').count(),
    ]
    all_rows.append(row)

    main_header_row = [
        'Title',
        'Section',
        'Date Submitted',
        'Date Accepted',
        'Date Published',
        'Views',
        'Downloads',
    ]
    all_rows.append(main_header_row)

    for article in articles:
        row = [
            strip_tags(article.title),
            article.section.name if article.section else 'No Section',
            article.date_submitted,
            article.date_accepted,
            article.date_published,
            article.views.count(),
            article.downloads.count(),
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


def acessses_by_country(journal):
    unique_country_codes = mm.ArticleAccess.objects.all().values_list(
        'country',
        flat=True
    ).distinct()

    print(unique_country_codes)


@cache(300)
def get_most_viewed_article(metrics):
    from django.db.models import Count

    return metrics.values('article__title').annotate(
        total=Count('article')).order_by('-total')[:1]


@cache(300)
def press_journal_report_data(journals, start_date, end_date):
    data = []

    for journal in journals:
        articles = sm.Article.objects.filter(journal=journal)

        submissions = articles.exclude(
            stage=sm.STAGE_PUBLISHED,
        ).filter(
            date_submitted__gte=start_date,
            date_submitted__lte=end_date,
        )

        published_articles = articles.filter(
            stage=sm.STAGE_PUBLISHED,
            date_published__gte=start_date,
            date_published__lte=end_date,
        )

        rejected_articles = articles.filter(
            stage=sm.STAGE_REJECTED,
            date_published__gte=start_date,
            date_published__lte=end_date,
        )

        metrics = mm.ArticleAccess.objects.filter(
            article__journal=journal,
            accessed__gte=start_date,
            accessed__lte=end_date,
        )

        most_viewed_article = get_most_viewed_article(metrics)

        views = metrics.filter(type='view')
        downloads = metrics.filter(type='download')

        data.append({
            'journal': journal,
            'articles': articles,
            'published_articles': published_articles,
            'submissions': submissions,
            'rejected_articles': rejected_articles,
            'views': views,
            'downloads': downloads,
            'most_viewed_article': most_viewed_article,
            'users': journal.journal_users(),
        })

    return data


def export_press_csv(data_dict):
    all_rows = list()
    header_row = [
        'Journal',
        'Submissions',
        'Published Submissions',
        'Rejected Submissions',
        'Number of Users',
        'Views',
        'Downloads',
        'Most Accessed Article',
    ]
    all_rows.append(header_row)

    for data in data_dict:

        most_viewed_article_string = '{title} ({count})'.format(
            title=data['most_viewed_article'][0]['article__title']  if data['most_viewed_article'] else '',
            count=data['most_viewed_article'][0]['total'] if data['most_viewed_article'] else ''
        )

        row = [
            data.get('journal').name,
            data.get('submissions').count(),
            data.get('published_articles').count(),
            data.get('rejected_articles').count(),
            len(data.get('users')),
            data.get('views').count(),
            data.get('downloads').count(),
            most_viewed_article_string,
        ]
        all_rows.append(row)

    return export_csv(all_rows)
