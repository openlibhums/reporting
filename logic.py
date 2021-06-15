import csv
import os
import uuid
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import datetime
from datetime import datetime
from dateutil.rrule import rrule, MONTHLY

from bs4 import BeautifulSoup

from django.utils import timezone
from django.conf import settings
from django.template.defaultfilters import strip_tags
from django.db.models import (
    DurationField,
    ExpressionWrapper,
    F,
    Min,
    Count,
    Avg
)
from django.template.loader import render_to_string

from submission import models as sm
from core.files import serve_temp_file, get_temp_file_path_from_name
from utils.function_cache import cache
from journal import models as jm
from review import models as rm
from metrics import models as mm


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


def get_first_month_year():
    return '{year}-{month}'.format(year=timezone.now().year, month='01')


def get_current_month_year():
    return '{year}-{month}'.format(
        year=timezone.now().year,
        month=timezone.now().strftime('%m'),
    )


def get_start_and_end_months(request):
    start_month = request.GET.get(
        'start_month', get_first_month_year()
    )

    end_month = request.GET.get(
        'end_month', get_current_month_year()
    )

    start_month_y, start_month_m = start_month.split('-')
    end_month_y, end_month_m = end_month.split('-')

    date_parts = {
        'start_month_m': start_month_m,
        'start_month_y': start_month_y,
        'end_month_m': end_month_m,
        'end_month_y': end_month_y,
        'start_unsplit': start_month,
        'end_unsplit': end_month,
    }

    return start_month, end_month, date_parts


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


def get_articles_with_counts(journal, start_date, end_date):
    if journal:
        articles = sm.Article.objects.filter(
            date_published__lte=end_date,
            journal=journal
        ).select_related('section')
    else:
        articles = sm.Article.objects.filter(
            date_published__lte=end_date,
        ).select_related('section')

    for article in articles:
        article.views = mm.ArticleAccess.objects.filter(
            article=article,
            accessed__gte=start_date,
            accessed__lte=end_date,
            type='view'
        ).count()
        article.downloads = mm.ArticleAccess.objects.filter(
            article=article,
            accessed__gte=start_date,
            accessed__lte=end_date,
            type='download'
        ).count()
        article.citations = mm.ArticleLink.objects.filter(
            article=article
        ).count()

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


def export_journal_level_citations(journals):
    all_rows = list()
    header_row = [
        'Journal',
        'Total Citations',
    ]
    all_rows.append(header_row)

    for journal in journals:
        all_rows.append(
            [
                journal.name,
                journal.citation_count
            ]
        )

    return export_csv(all_rows)


def export_article_level_citations(articles):
    all_rows = list()
    header_row = [
        'Title',
        'Publication Date',
        'Total Citations',
    ]
    all_rows.append(header_row)

    for article in articles:
        all_rows.append(
            [
                article.title,
                article.date_published,
                article.citation_count,
            ]
        )

    return export_csv(all_rows)


def export_citing_articles(article):
    all_rows = list()
    header_row = [
        'Title',
        'Journal',
        'Year',
        'DOI',
    ]
    all_rows.append(header_row)

    for citing_work in article.articlelink_set.all():
        all_rows.append(
            [
                citing_work.article_title,
                citing_work.journal_title,
                citing_work.year,
                citing_work.doi,
            ]
        )

    return export_csv(all_rows)


def average(lst):
    if lst:
        return round(sum(lst) / len(lst), 2)
    else:
        return 0


def acessses_by_country(journal, start_date, end_date):
    metrics = mm.ArticleAccess.objects.filter(
        article__stage=sm.STAGE_PUBLISHED,
        accessed__gte=start_date,
        accessed__lte=end_date,
    ).values(
        'country__name'
    ).annotate(
        country_count=Count('country')
    )

    if journal:
        metrics = metrics.filter(
            article__journal=journal,
        )

    return metrics


def export_country_csv(metrics):
    all_rows = [['Country', 'Count']]
    for row in metrics:
        all_rows.append(
            [row.get('country__name'), row.get('country_count')]
        )
    return export_csv(all_rows)


@cache(300)
def get_most_viewed_article(metrics, count=1):
    from django.db.models import Count

    return metrics.values('article__title').annotate(
        total=Count('article')).order_by('-total')[:count]


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
            date_declined__gte=start_date,
            date_declined__lte=end_date,
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
            title=data['most_viewed_article'][0]['article__title'] if data['most_viewed_article'] else '',
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


@cache(600)
def journal_usage_by_month_data(date_parts):
    journals = jm.Journal.objects.filter(is_remote=False)
    metrics = mm.ArticleAccess.objects.all()

    start_str = '{}-01'.format(date_parts.get('start_unsplit'))
    end_str = '{}-27'.format(date_parts.get('end_unsplit'))

    start = datetime.strptime(start_str, '%Y-%m-%d').date()
    end = datetime.strptime(end_str, '%Y-%m-%d').date()

    dates = [start]

    while start < end:
        start += relativedelta(months=1)
        if start < end:
            dates.append(start)

    data = []

    for journal in journals:
        journal_metrics = metrics.filter(article__journal=journal)
        journal_data = {'journal': journal, 'all_metrics': journal_metrics}

        date_metrics_list = []

        for d in dates:
            date_metrics = journal_metrics.filter(
                accessed__month=d.month,
                accessed__year=d.year,
            )
            date_metrics_list.append(date_metrics.count())

        journal_data['date_metrics'] = date_metrics_list

        data.append(journal_data)

    return data, dates


def export_usage_by_month(data, dates):
    all_rows = list()
    header_row = [
        'Journal',
    ]

    for date in dates:
        header_row.append(date)

    all_rows.append(header_row)

    for d in data:
        row = [
            d.get('journal').name,
        ]

        for dm in d.get('date_metrics'):
            row.append(dm)

        all_rows.append(row)

    return export_csv(all_rows)


@cache(60)
def peer_review_data(articles, start_date, end_date):
    data = []

    for article in articles:
        reviews = rm.ReviewAssignment.objects.filter(
            article=article,
            date_accepted__isnull=False,
            date_complete__isnull=False,
            date_requested__gte=start_date,
            date_requested__lte=end_date,
        )

        for review in reviews:
            review.request_to_accept = review.date_accepted - review.date_requested
            review.accept_to_complete = review.date_complete - review.date_accepted

        data.append(
            {'article': article, 'reviews': reviews}
        )

    return data


def export_review_data(data):
    all_rows = list()

    headers = [
        'Reviewer',
        'Journal',
        'Date Requested',
        'Date Accepted',
        'Date Due',
        'Date Complete',
        'Time to Acceptance',
        'Time to Completion',
    ]

    all_rows.append(headers)

    for data_point in data:
        for review in data_point.get('reviews'):
            row = [
                review.reviewer.full_name(),
                strip_tags(data_point.get('article').title),
                review.date_requested,
                review.date_accepted,
                review.date_due,
                review.date_complete,
                review.request_to_accept,
                review.accept_to_complete,
            ]

            all_rows.append(row)

    return export_csv(all_rows)


def current_year():
    return date.today().year


def earliest_citation_year():
    try:
        check = mm.ArticleLink.objects.filter().values_list(
            'pk'
        ).annotate(
            Min('year')
        ).order_by(
            'year'
        )[0]
        return check[1]
    except IndexError:
        return current_year()


def get_year(request):
    return request.GET.get('year', current_year())


@cache(600)
def citation_data(year):
    articles = sm.Article.objects.filter(
        articlelink__year=year,
    )

    return articles


def get_journal_citations(journal):
    counter = 0
    articles = sm.Article.objects.filter(
        articlelink__year__isnull=False,
        journal=journal
    ).distinct()
    for article in articles:
        counter = counter + article.citation_count

    journal.citation_count = counter

    return articles


@cache(600)
def get_book_data(date_parts):
    """
    Checks if the books plugin logic module can be loaded or returns an empty dict.
    """

    try:
        from plugins.books import models as book_models, logic as book_logic
        books = book_models.Book.objects.all()
        return book_logic.book_metrics_by_month(books, date_parts)
    except ImportError as e:
        print(e)
        return [], [], '', ''


def get_months_between_date_parts(date_parts):
    start_dt = datetime(year=int(date_parts.get('start_month_y')), month=int(date_parts.get('start_month_m')), day=1)
    end_dt = datetime(year=int(date_parts.get('end_month_y')), month=int(date_parts.get('end_month_m')), day=1)

    return [dt for dt in rrule(MONTHLY, dtstart=start_dt, until=end_dt)]


def get_months_to_jan(date_parts):
    start_dt = datetime(int(date_parts.get('end_month_y')), 1, 1)
    end_dt = datetime(int(date_parts.get('end_month_y')), int(date_parts.get('end_month_m')), 1)

    return [dt for dt in rrule(MONTHLY, dtstart=start_dt, until=end_dt)]


@cache(600)
def get_average_review_time(journal, start, end):
    f_review_delta = ExpressionWrapper(
        F('date_complete') - F('date_requested'),
        output_field=DurationField(),
    )
    average_time_to_complete = rm.ReviewAssignment.objects.filter(
        article__journal=journal,
        date_requested__gte=start,
        date_requested__lte=end,
        date_complete__gte=start,
        date_complete__lte=end,
    ).annotate(
        editorial_delta=f_review_delta
    ).aggregate(
        Avg('editorial_delta')
    )

    return average_time_to_complete.get('editorial_delta__avg', 0)


@cache(600)
def get_board_report_journal_date(date_parts, all_metrics):
    journals = jm.Journal.objects.all()
    start_str = '{}-01'.format(date_parts.get('start_unsplit'))
    end_str = '{}-27'.format(date_parts.get('end_unsplit'))

    start = datetime.strptime(start_str, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')

    start = timezone.make_aware(start)
    end = timezone.make_aware(end)

    current_year = date_parts.get('end_month_y')
    previous_year = str(int(current_year) - 1)

    months_between_dates = len(get_months_between_date_parts(date_parts))
    months_to_jan = len(get_months_to_jan(date_parts))

    data = []
    for journal in journals:
        journal_metrics = all_metrics.filter(
            article__journal=journal,
        )
        articles = sm.Article.objects.filter(
            journal=journal,
        )
        submissions = articles.exclude(
            stage=sm.STAGE_PUBLISHED,
        ).filter(
            date_submitted__gte=start,
            date_submitted__lte=end,
        )
        published_articles = articles.filter(
            stage=sm.STAGE_PUBLISHED,
            date_published__gte=start,
            date_published__lte=end,
        )
        authors = sm.FrozenAuthor.objects.filter(
            article__in=articles,
        ).count()
        review_average = get_average_review_time(
            journal,
            start,
            end,
        )

        journal_data = {
            'journal': journal,
            'views': {},
            'downloads': {},
            'accesses': {},
            'total_accesses': journal_metrics.count(),
            'articles': {}
        }

        journal_data['views']['total'] = journal_metrics.filter(type='view').count()
        journal_data['views']['period'] = journal_metrics.filter(
            type='view',
            article__stage=sm.STAGE_PUBLISHED,
            accessed__year__gte=date_parts.get('start_month_y'),
            accessed__month__gte=date_parts.get('start_month_m'),
            accessed__year__lte=date_parts.get('end_month_y'),
            accessed__month__lte=date_parts.get('end_month_m'),
        ).count()
        journal_data['views']['period_average'] = round(journal_data['views']['period'] / months_between_dates, 2)
        journal_data['views']['year'] = journal_metrics.filter(
            type='view',
            article__stage=sm.STAGE_PUBLISHED,
            accessed__year=current_year,
        ).count()
        journal_data['views']['year_average'] = round(journal_data['views']['year'] / months_to_jan, 2)

        journal_data['downloads']['total'] = journal_metrics.filter(type='download').count()
        journal_data['downloads']['period'] = journal_metrics.filter(
            type='download',
            article__stage=sm.STAGE_PUBLISHED,
            accessed__year__gte=date_parts.get('start_month_y'),
            accessed__month__gte=date_parts.get('start_month_m'),
            accessed__year__lte=date_parts.get('end_month_y'),
            accessed__month__lte=date_parts.get('end_month_m'),
        ).count()
        journal_data['downloads']['period_average'] = round(journal_data['downloads']['period'] / months_between_dates, 2)
        journal_data['downloads']['year'] = journal_metrics.filter(
            type='download',
            article__stage=sm.STAGE_PUBLISHED,
            accessed__year=current_year,
        ).count()
        journal_data['downloads']['year_average'] = round(journal_data['downloads']['year'] / months_to_jan, 2)

        journal_data['accesses']['total'] = journal_data['views']['total'] + journal_data['downloads']['total']
        journal_data['accesses']['period'] = journal_data['views']['period'] + journal_data['downloads']['period']
        journal_data['accesses']['period_average'] = round(journal_data['accesses']['total'] / months_between_dates, 2)
        journal_data['accesses']['year'] = journal_data['views']['year'] + journal_data['downloads']['year']

        journal_data['articles']['all'] = articles
        journal_data['articles']['submissions'] = submissions.count()
        journal_data['articles']['publications'] = published_articles.count()
        journal_data['articles']['authors'] = authors
        journal_data['review_average'] = review_average.days if review_average else 'N/a'

        data.append(journal_data)

    return data


@cache(600)
def most_accessed_articles(date_parts, all_metrics):
    top_viewed_articles = all_metrics.filter(
        accessed__year__gte=date_parts.get('start_month_y'),
        accessed__month__gte=date_parts.get('start_month_m'),
        accessed__year__lte=date_parts.get('end_month_y'),
        accessed__month__lte=date_parts.get('end_month_m'),
    ).values('article').annotate(
        total=Count('article')).order_by('-total')[:10]

    articles = []
    for article in top_viewed_articles:
        article = sm.Article.objects.get(
            pk=article.get('article'),
        )
        article_metrics = all_metrics.filter(
            article=article,
            accessed__year__gte=date_parts.get('start_month_y'),
            accessed__month__gte=date_parts.get('start_month_m'),
            accessed__year__lte=date_parts.get('end_month_y'),
            accessed__month__lte=date_parts.get('end_month_m'),
        )
        article.accesses = article_metrics.count()
        article.views = article_metrics.filter(type='view').count()
        article.downloads = article_metrics.filter(type='download').count()
        article.citations = mm.ArticleLink.objects.filter(article=article).count()
        articles.append(article)

    return articles


def html_table_to_csv(html):
    filename = '{0}.csv'.format(uuid.uuid4())
    filepath = get_temp_file_path_from_name(
        filename,
    )
    soup = BeautifulSoup(str(html), 'lxml')
    with open(filepath, "w", encoding="utf-8") as f:
        wr = csv.writer(f)
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = [cell.string for cell in row.findChildren(['th', 'td'])]
                wr.writerow(cells)
            wr.writerow([])

    f.close()
    return filepath, filename


def export_board_report_csv(
        request,
        book_data,
        journal_data,
        most_accessed_articles,
        start_month,
        end_month,
        book_dates,
        current_year,
        previous_year,
):
    elements = [
        'header.html',
        'books.html',
        'journals.html',
        'articles.html',
    ]

    context = {
        'request': request,
        'start_month': start_month,
        'end_month': end_month,
        'book_data': book_data,
        'journal_data': journal_data,
        'most_accessed_articles': most_accessed_articles,
        'book_dates': book_dates,
        'current_year': current_year,
        'previous_year': previous_year,
    }

    html = ''
    for element in elements:
        html = html + render_to_string(
            'reporting/elements/{element}'.format(element=element),
            context,
        )
    csv_filepath, csv_filename = html_table_to_csv(html)
    return serve_temp_file(csv_filepath, csv_filename)
