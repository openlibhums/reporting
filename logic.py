import csv
from io import StringIO
from itertools import chain
import os
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


from django.http import StreamingHttpResponse
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.template.defaultfilters import strip_tags
from django.db.models import (
    DurationField,
    ExpressionWrapper,
    F,
    IntegerField,
    Min,
    Case,
    Count,
    Q,
    Subquery,
    Func,
    When,
    OuterRef
)
from django.db.models.functions import TruncMonth

from submission import models as sm
from core.files import serve_temp_file
from core import models as core_models
from utils.function_cache import cache
from journal import models as jm
from review import models as rm
from metrics import models as mm
from identifiers import models as id_models
from plugins.reporting.templatetags import timedelta as td_tag


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

    f_editorial_delta = ExpressionWrapper(
        F('date_published') - F('date_submitted'),
        output_field=DurationField(),
    )

    articles = sm.Article.objects.filter(
        date_published__lte=dt,
    ).select_related(
        'section'
    ).annotate(editorial_delta=f_editorial_delta)

    if journal:
        articles = articles.filter(journal=journal)

    abstract_page_views = mm.ArticleAccess.objects.filter(
        article=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type__isnull=True,
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    html_views = mm.ArticleAccess.objects.filter(
        article=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type__in={"html", "xml"},
        type="view",
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    pdf_views = mm.ArticleAccess.objects.filter(
        article=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type="pdf",
        type="view",
    ).annotate(
        count=Func(F('id'), function="Count")
    ).values("count")

    pdf_downloads = mm.ArticleAccess.objects.filter(
        article=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type="pdf",
        type="download",
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    other_downloads = mm.ArticleAccess.objects.filter(
        article=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        type="download",
    ).exclude(
        galley_type__in={"pdf"},
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    articles = articles.annotate(
        abstract_views=Subquery(abstract_page_views, output_field=IntegerField()),
        html_views=Subquery(html_views, output_field=IntegerField()),
        pdf_views=Subquery(pdf_views, output_field=IntegerField()),
        pdf_downloads=Subquery(pdf_downloads, output_field=IntegerField()),
        other_downloads=Subquery(other_downloads, output_field=IntegerField()),
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


def export_csv(rows, filename=None):
    if not filename:
        filename = '{0}.csv'.format(timezone.now())
    full_path = os.path.join(settings.BASE_DIR, 'files', 'temp', filename)

    with open(full_path, 'w', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',')
        for row in rows:
            csv_writer.writerow(row)

    return serve_temp_file(
        full_path,
        filename
    )


def stream_csv(headers, iterable, filename=None):
    """ A more performant version of export_csv
    Instead of loading all rows in memory and flushing to a file before serving,
    it serves a StreamingHttpResponse to which we yield each row individually
    :headers: a list or tuple of headers
    :iterable: an iterable that yields lists or tuples of row data
    """
    filename = filename or '{0}.csv'.format(timezone.now())

    def response_streamer():
        """Writes each row to an in-memory file that is yielded immediately"""

        # Headers
        file_like = StringIO()
        csv_writer = csv.writer(file_like)
        csv_writer.writerow(headers)
        yield file_like.getvalue()

        # Rows
        for row in iterable:
            file_like = StringIO()
            csv_writer = csv.writer(file_like)
            csv_writer.writerow(row)
            yield file_like.getvalue()

    response = StreamingHttpResponse(
        response_streamer(),
        content_type="text/csv",

    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


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


def export_article_csv(articles, journal):

    info_header_row = [
        'Articles',
        'Submissions',
        'Published Articles',
        'Rejected Articles',
        'Views',
        'Downloads',
    ]

    journal_row = [
        journal.article_set.count(),
        journal.submitted,
        journal.published,
        journal.rejected,
        journal.total_views,
        journal.total_downloads,
    ]

    main_header_row = [
        'ID',
        'Title',
        'Section',
        'Date Submitted',
        'Date Accepted',
        'Date Published',
        'Days to Publication',
        'Abstract Views',
        'HTML Views',
        'PDF Views',
        'PDF Downloads',
        'Other Downloads',
    ]

    iter_articles = ((
        article.pk,
        strip_tags(article.title),
        article.section.name if article.section else 'No Section',
        article.date_submitted,
        article.date_accepted,
        article.date_published,
        article.editorial_delta.days if article.editorial_delta else '',
        article.abstract_views,
        article.html_views,
        article.pdf_views,
        article.pdf_downloads,
        article.other_downloads,
    ) for article in articles)

    all_rows = chain([journal_row, main_header_row], iter_articles)
    filename = f'articles-report-{journal.code}-{timezone.now()}.csv'

    return stream_csv(info_header_row, all_rows, filename=filename)


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

    return export_csv(all_rows, filename="production_timeline.csv")


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

    return export_csv(all_rows, filename="journal_citations.csv")


def export_article_level_citations(articles, by_year=False):
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
                article.citation_count if not by_year else article.citations_in_year.count(),
            ]
        )

    return export_csv(all_rows, filename="article_citations.csv")


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

    return export_csv(all_rows, filename="article_citing_works.csv")


def export_book_level_citations(books):
    rows = list()
    header_row = [
        'Title',
        'DOI',
        'Publication Date',
        'Citations'
    ]
    rows.append(header_row)

    for book in books:
        rows.append(
            [
                book.title,
                book.doi,
                book.date_published,
                book.links.count(),
            ]
        )
    return export_csv(rows, filename="book_citation_count.csv")


def export_citing_books(book, links):
    rows = list()
    header_row = [
        'Title',
        'DOI',
        'ISBN',
        'e-ISBN'
    ]
    rows.append(header_row)

    for link in links:
        rows.append(
            [
                link.title,
                link.doi,
                link.isbn_print,
                link.isbn_electronic,
            ]
        )
    return export_csv(rows, filename=f"book_{book.pk}_citing_works.csv")


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
    return export_csv(all_rows, filename="access_by_country.csv")


@cache(300)
def get_most_viewed_article(metrics):
    from django.db.models import Count

    return metrics.values('article__title').annotate(
        total=Count('article')).order_by('-total')[:1]


@cache(300)
def press_journal_report_data(journals, start_date, end_date):
    data = []

    submissions_subq = sm.Article.objects.filter(
        journal=OuterRef("id"),
        date_submitted__gte=start_date,
        date_submitted__lte=end_date,
    ).annotate(
        count=Func(F('id'), function="Count")
    # This order by seems pointles (and it is) but it is necessary to address
    # a bug of the ORM with postgres for django < 2.0
    # https://github.com/django/django/commit/daf2bd3efe53cbfc1c9fd00222b8315708023792
    # TODO: django 2.0+ - Remove pointless order by statement that slows query
    ).order_by("count").values("count")

    published_articles_subq = sm.Article.objects.filter(
        journal=OuterRef("id"),
        date_published__gte=start_date,
        date_published__lte=end_date,
    ).annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    rejected_articles_subq = sm.Article.objects.filter(
        journal=OuterRef("id"),
        stage=sm.STAGE_REJECTED,
        date_declined__gte=start_date,
        date_declined__lte=end_date,
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    views_subq = mm.ArticleAccess.objects.filter(
        article__journal=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        type="view",
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    downloads_subq = mm.ArticleAccess.objects.filter(
        article__journal=OuterRef("id"),
        accessed__gte=start_date,
        accessed__lte=end_date,
        type="download",
    ).order_by().annotate(
        count=Func(F('id'), function="Count")
    ).order_by("count").values("count")

    journals = journals.annotate(
        submitted=Subquery(submissions_subq, output_field=IntegerField()),
        published=Subquery(published_articles_subq, output_field=IntegerField()),
        rejected=Subquery(rejected_articles_subq, output_field=IntegerField()),
        total_views=Subquery(views_subq, output_field=IntegerField()),
        total_downloads=Subquery(downloads_subq, output_field=IntegerField()),
    )
    return journals


def export_press_csv(journals):
    header_row = [
        'Journal',
        'Submissions',
        'Published Submissions',
        'Rejected Submissions',
        'Number of Users',
        'Views',
        'Downloads',
    ]


    rows = ((
        journal.name,
        journal.submitted,
        journal.published,
        journal.rejected,
        len(journal.journal_users()),
        journal.total_views,
        journal.total_downloads,
    ) for journal in journals)
    filename = f'press-report-{timezone.now()}.csv'

    return stream_csv(header_row, rows, filename=filename)


@cache(600)
def journal_usage_by_month_data(date_parts):
    """An attempt to make the view above more performant"""
    journals = jm.Journal.objects.filter(is_remote=False, hide_from_press=False)
    journal_id_map = {j.id: j for j in journals}
    data = {}
    metrics = mm.ArticleAccess.objects.all()

    start = timezone.make_aware(timezone.datetime(
        int(date_parts["start_month_y"]),
        int(date_parts["start_month_m"]),
        1
    ))
    end = timezone.make_aware(timezone.datetime(
        int(date_parts["end_month_y"]),
        int(date_parts["end_month_m"]),
        1
        # get first day of next month at 00:00:00
    ) + relativedelta(months=1))


    journal_metrics = metrics.filter(
        article__journal__in=journals,
        type__in=['view', 'download'],
        accessed__gte=start,
        accessed__lt=end,
    ).exclude(
        galley_type__isnull=True,
    ).annotate(
        month=TruncMonth('accessed'),
    ).values(
        # There is no group by in the ORM, this call will translate into:
        # GROUP BY "submission_article"."journal_id",
        #   DATE_TRUNC('month', "metrics_articleaccess"."accessed")
        "article__journal", "month",
    ).annotate(
        # This annotation has to take place after the values above so that it is
        # done over the grouped by clause
        total=Count("id"),
    # This `values` call is turned into the SELECT clause
    ).values("article__journal", "month", "total"
    ).order_by("article__journal", "month")

    dates = [start]
    requested_start = start # preserve original requested start

    while start < end:
        start += relativedelta(months=1)
        if start < end:
            dates.append(start)

    current_journal = None
    maximum = minimum = 0
    for row in journal_metrics:
        journal = journal_id_map[row["article__journal"]]
        data.setdefault(journal, [])
        if journal != current_journal:  # if we have switched to another journal
            # fill gaps if a journal history doesn't have history in the period
            if row["month"] != requested_start:
                delta = relativedelta(row["month"].date(), requested_start.date())
                months_delta = (delta.years * 12) + delta.months
                for _ in range(months_delta):
                    data[journal].append(0)

        month_total = row["total"]
        data[journal].append(month_total)
        if month_total > maximum:
            maximum = month_total
        if month_total < minimum:
            minimum = month_total
        current_journal = journal

    return data, dates, maximum, minimum


@cache(600)
def ajournal_usage_by_month_data(date_parts):
    journals = jm.Journal.objects.filter(is_remote=False, hide_from_press=False)
    data = {}


    start = timezone.datetime(
        int(date_parts["start_month_y"]),
        int(date_parts["start_month_m"]),
        1
    )
    end = timezone.datetime(
        int(date_parts["end_month_y"]),
        # get first day of next month at 00:00:00
        int(date_parts["end_month_m"]) + 1,
        1
    )
    dates = []

    while start < end:
        if start < end:
            # e.g: 2022-01, 2022-02...
            annotation_key = start.strftime("%Y-%m")
            dates.append(annotation_key)
            next_month = start + relativedelta(months=1)

        # Annotate each journal with the metrics for this date range
        journals = journals.annotate(**{
            annotation_key: Subquery(
                build_range_metrics_subq(start, next_month),
                output_field=IntegerField(),
            )
        })
        start = next_month

    for journal in journals:
        # transform the data into tabular format for the template/CSV
        data[journal] = [getattr(journal, date, 0) for date in dates]


    return data, dates


def build_range_metrics_subq(start, end):
    return mm.ArticleAccess.objects.filter(
        article__journal=OuterRef("id"),
        accessed__range=(start, end),
    ).order_by().annotate(
        count=Func(F('id'), function='Count', output_field=IntegerField()),
    ).values('count')


def export_usage_by_month(data, dates):
    all_rows = list()
    header_row = [
        'Journal',
    ]

    for date in dates:
        header_row.append(date)

    all_rows.append(header_row)

    for journal, metrics in data.items():
        row = [
            journal.name,
        ]

        for dm in metrics:
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


@cache(300)
def peer_review_stats(start_date, end_date, journal=None):
    """Returns peer review statistics for the journal in the given period"""
    submitted_articles = sm.Article.objects.filter(
        date_submitted__gte=start_date,
        date_submitted__lte=end_date,
    )
    if journal:
        submitted_articles = submitted_articles.filter(journal=journal)

    completed_reviews = rm.ReviewAssignment.objects.filter(
        article__in=submitted_articles,
        date_complete__isnull=False,
        date_declined__isnull=True,
    )
    stats = {
        "submitted": submitted_articles.count(),
        "accepted": submitted_articles.filter(date_accepted__isnull=False).count(),
        "rejected": submitted_articles.filter(date_declined__isnull=False).count(),
        "completed_reviews": completed_reviews.count()
    }

    return stats


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


def write_doi_tsv_report(to_write, journal=None, crosscheck=False):
    """ Writes a TSV of DOI and pointed URLS to the passed object
    :param to_write: An file-like object that can be written to
    :param journal: An optional Journal object to filter the report by
    :param crosscheck: A bool flag for returning URLs to full-text instead
    :return: The Same file-like object passed as an argument
    """
    writer = csv.writer(to_write, delimiter="\t", lineterminator='\n')
    identifiers = id_models.Identifier.objects.filter(
        article__isnull=False,
        article__stage=sm.STAGE_PUBLISHED,
        id_type="doi",
    )

    if journal:
        identifiers = identifiers.filter(article__journal=journal)
    identifiers = identifiers.order_by("article__journal", "id")

    writer.writerow(["DOI", "URL"])
    for identifier in identifiers:
        article = identifier.article
        if crosscheck and article.pdfs.exists():
            path = reverse('serve_article_pdf',
                kwargs={
                    "identifier_type": "id",
                    "identifier": article.id
                }
            )
            url = article.journal.site_url(path)
        else:
            url = article.url
        writer.writerow((identifier.identifier, url))

        # Supplementary file DOIs
        if not crosscheck:
            for supp_file in core_models.SupplementaryFile.objects.filter(
                file__article_id=article.pk,
                doi__isnull=False,
            ):
                writer.writerow((supp_file.doi, supp_file.url()))

    return to_write


def license_report(start, end):
    articles = sm.Article.objects.filter(
        date_published__lte=end,
        date_published__gte=start,
    ).values('license', 'license__name', 'license__journal__code').annotate(
        lcount=Count('license')
    ).order_by('lcount')

    return articles


def timedelta_average(timedeltas):
    return sum(timedeltas, timedelta(0)) / len(timedeltas)


def get_averages(article_list):
    submission_to_accept_days = list()
    submission_to_publication_days = list()
    accept_to_publication_days = list()

    for article in article_list:

        if article.date_accepted and article.date_submitted:
            article.submission_to_accept = article.date_accepted - article.date_submitted
            submission_to_accept_days.append(article.submission_to_accept)

        if article.date_published and article.date_accepted:
            article.accept_to_publication = article.date_published - article.date_accepted
            accept_to_publication_days.append(article.accept_to_publication)

        if article.date_published and article.date_submitted:
            article.submission_to_publication = article.date_published - article.date_submitted
            submission_to_publication_days.append(article.submission_to_publication)

    return {
        'submission_to_accept_average': timedelta_average(submission_to_accept_days),
        'submission_to_publication_average': timedelta_average(submission_to_publication_days),
        'accept_to_publication_average': timedelta_average(accept_to_publication_days),
    }


def export_workflow_report(article_list, averages):
    all_rows = list()

    average_headers = [
        'Submission to Acceptance Average',
        'Acceptance to Publication Average',
        'Submission to Publication Average',
    ]

    all_rows.append(average_headers)
    all_rows.append(
        [
            td_tag.display_timedelta(
                averages.get('submission_to_accept_average')
            ),
            td_tag.display_timedelta(
                averages.get('accept_to_publication_average')
            ),
            td_tag.display_timedelta(
                averages.get('submission_to_publication_average')
            )
        ]
    )

    article_headers = [
        'ID',
        'Title',
        'DOI',
        'Date Submitted',
        'Date Accepted',
        'Date Published',
        'Submission to Acceptance',
        'Acceptance to Publication',
        'Submission to Publication',
    ]

    all_rows.append(article_headers)

    for article in article_list:
        row = [
            article.pk,
            article.title,
            article.get_doi(),
            article.date_submitted,
            article.date_accepted,
            article.date_published,
            article.submission_to_accept if hasattr(article, 'submission_to_accept') else '',
            article.accept_to_publication if hasattr(article, 'accept_to_publication') else '',
            article.submission_to_publication if hasattr(article, 'submission_to_publication') else '',
        ]

        all_rows.append(row)

    return export_csv(all_rows)