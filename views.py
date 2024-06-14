from django.http import HttpResponse
from django.shortcuts import (
    get_object_or_404,
    Http404,
    redirect,
    render,
    reverse,
)
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required

from core import models as core_models
from plugins.reporting import forms, logic
from journal import models
from production import models as pm
from security.decorators import editor_user_required, has_journal
from submission import models as sm
from journal import models as jm
from metrics import models as mm
from review import models as rm
from utils import plugins


@editor_user_required
def index(request):
    """
    Displays a list of reports for a user to select.
    :param request: HttpRequest object
    :return: HttpResponse or HttpRedirect
    """
    journal_report_form = forms.ArticleMetricsForm()

    if request.POST:

        if 'journal' in request.POST:
            journal_report_form = forms.ArticleMetricsForm(request.POST)
            if journal_report_form.is_valid():
                journal = journal_report_form.cleaned_data.get('journal')

                return redirect(
                    reverse(
                        'reporting_articles',
                        kwargs={'journal_id': journal.pk},
                    )
                )

    context = {
        'journal_report_form': journal_report_form,
        'journals': models.Journal.objects.all(),
        'books_plugin_installed': plugins.check_plugin_exists('books'),
    }

    return render(request, 'reporting/index.html', context)


@editor_user_required
def report_articles(request, journal_id):
    """
    Displays views and downloads for each article in a journal.
    :param request: HttpRequest object
    :param journal_id: int, pk of a Journal object
    :return: HttpResponse or HttpRedirect
    """
    # this needs to be a queryset to fetch data.
    journals = models.Journal.objects.filter(id=journal_id)
    if not journals.exists():
        raise Http404

    start_date, end_date = logic.get_start_and_end_date(request)
    journals = logic.press_journal_report_data(
        journals,
        start_date,
        end_date,
    )
    articles = logic.get_articles(journals.first(), start_date, end_date)
    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )
    if request.POST:
        return logic.export_article_csv(articles, journals.first())

    template = 'reporting/report_articles.html'
    context = {
        'journal': journals.first(),
        'articles': articles,
        'start_date': start_date,
        'end_date': end_date,
        'date_form': date_form,
    }

    return render(request, template, context)


@editor_user_required
def report_journal_usage_by_month(request):
    """
    Presents a table of usage information by month between two supplied months.
    :param request: HttpRequest
    :return: HttpResponse
    """
    start_month, end_month, date_parts = logic.get_start_and_end_months(request)

    month_form = forms.MonthForm(
        initial={
            'start_month': start_month, 'end_month': end_month,
        }
    )

    data, dates, max_, min_ = logic.journal_usage_by_month_data(date_parts)

    if request.POST:
        return logic.export_usage_by_month(data, dates)

    template = 'reporting/report_journal_usage_by_month.html'
    context = {
        'month_form': month_form,
        'data': data,
        'dates': dates,
        "maximum": max_,
        "minimum": min_,
    }

    return render(request, template, context)


@editor_user_required
def report_production(request):
    """
    Presents information about lead times for production assignents
    :param request:
    :return:
    """
    start_date, end_date = logic.get_start_and_end_date(request)

    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    production_assignments = pm.TypesetTask.objects.filter(
        completed__isnull=False,
        accepted__isnull=False,
        assigned__gte=start_date,
        assigned__lte=end_date,
    )

    all_acceptance_times = list()
    all_completion_times = list()

    for assignment in production_assignments:
        time_to_acceptance = assignment.accepted - assignment.assigned
        time_to_completion = assignment.completed - assignment.accepted
        assignment.time_to_acceptance = time_to_acceptance.days
        assignment.time_to_completion = time_to_completion

        all_acceptance_times.append(time_to_acceptance.days)
        all_completion_times.append(time_to_completion.days)

    if request.POST:
        return logic.export_production_csv(production_assignments)

    template = 'reporting/report_production.html'
    context = {
        'production_assignments': production_assignments,
        'all_acceptance_times': all_acceptance_times,
        'all_completion_times': all_completion_times,
        'start_date': start_date,
        'end_date': end_date,
        'date_form': date_form,
        'time_to_acceptance': logic.average(all_acceptance_times),
        'time_to_completion': logic.average(all_completion_times)
    }

    return render(request, template, context)


@editor_user_required
def report_geo(request, journal_id=None):
    if journal_id:
        journal = get_object_or_404(models.Journal, pk=journal_id)
    else:
        journal = None

    start_date, end_date = logic.get_start_and_end_date(request)

    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    countries = logic.acessses_by_country(
        journal,
        start_date,
        end_date,
    )

    if request.POST:
        return logic.export_country_csv(countries)

    template = 'reporting/report_geo.html'
    context = {
        'journal': journal,
        'countries': countries,
        'start_date': start_date,
        'end_date': end_date,
        'date_form': date_form,
    }

    return render(request, template, context)


@editor_user_required
def press(request):
    start_date, end_date = logic.get_start_and_end_date(request)
    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    journals = models.Journal.objects.filter(
        is_remote=False,
    ).order_by('code')

    journals = logic.press_journal_report_data(
        journals,
        start_date,
        end_date,
    )

    if request.POST:
        return logic.export_press_csv(journals)

    template = 'reporting/press.html'
    context = {
        'date_form': date_form,
        'journals': journals,
    }

    return render(request, template, context)


@editor_user_required
def report_review(request, journal_id=None):
    start_date, end_date = logic.get_start_and_end_date(request)
    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    if request.journal:
        journal = request.journal
        articles = sm.Article.objects.filter(
            journal=journal,
        )

    elif journal_id:
        journal = get_object_or_404(jm.Journal, pk=journal_id)
        articles = sm.Article.objects.filter(
            journal=journal,
        )
    else:
        journal = None
        articles = sm.Article.objects.all()

    data = logic.peer_review_data(articles, start_date, end_date)
    review_stats = logic.peer_review_stats(start_date, end_date, journal)

    if request.POST:
        return logic.export_review_data(data)

    template = 'reporting/report_review.html'
    context = {
        'journal': journal,
        'date_form': date_form,
        'data': data,
        'review_stats': review_stats,
    }

    return render(request, template, context)


@editor_user_required
def report_citations(request):
    year = logic.get_year(request)
    all_time = request.GET.get('all_time', False)
    date_form = forms.YearForm(
        initial={
            'year': year,
            'all_time': all_time,
        }
    )
    by_year = True
    if request.GET.get('all_time', False) == 'on':
        by_year = False

    all_articles = sm.Article.objects.filter(
        articlelink__year__isnull=False,
    ).distinct()

    if request.journal:
        all_articles = all_articles.filter(journal=request.journal)

    if by_year:
        data = all_articles.filter(articlelink__year=year).distinct()

        for article in data:
            article.citations_in_year = mm.ArticleLink.objects.filter(
                article=article,
                year=year,
            )

    else:
        data = all_articles

    if request.POST:
        return logic.export_article_level_citations(data, by_year)

    template = 'reporting/report_citations.html'
    context = {
        'date_form': date_form,
        'all_articles': all_articles,
        'data': data,
        'all_time': all_time,
    }

    return render(request, template, context)


@editor_user_required
def report_all_citations(request):
    journals = jm.Journal.objects.filter(hide_from_press=False)

    total_counter = 0
    for journal in journals:
        logic.get_journal_citations(journal=journal)
        total_counter = total_counter + journal.citation_count

    if request.POST:
        return logic.export_journal_level_citations(journals)

    template = 'reporting/report_all_citations.html'
    context = {
        'journals': journals,
        'total_counter': total_counter,
    }

    return render(request, template, context)


@editor_user_required
def report_journal_citations(request, journal_id):
    journal = get_object_or_404(jm.Journal, pk=journal_id)
    articles = logic.get_journal_citations(journal)

    if request.POST:
        return logic.export_article_level_citations(articles)

    template = 'reporting/report_journal_citations.html'
    context = {
        'journal': journal,
        'articles': articles,
    }

    return render(request, template, context)


@editor_user_required
def report_article_citing_works(request, journal_id, article_id):
    journal = get_object_or_404(jm.Journal, pk=journal_id)
    article = get_object_or_404(sm.Article, pk=article_id)

    if request.POST:
        return logic.export_citing_articles(article)

    template = 'reporting/report_article_citating_works.html'

    context = {
        'journal': journal,
        'article': article,
        'links': article.articlelink_set.all(),
    }

    return render(request, template, context)


@staff_member_required
def report_book_citations(request):
    # Check if the books plugin exists or not.
    if not plugins.check_plugin_exists('books'):
        raise Http404("The Books plugin is not installed")

    from plugins.books import models as book_models

    all_book_links = mm.BookLink.objects.filter(
        article__isnull=True,
        object_type='book',
    )
    books = book_models.Book.objects.filter(
        date_published__lte=timezone.now()
    )
    for book in books:
        book.links = mm.BookLink.objects.filter(
            doi=book.doi,
            object_type='book',
        )

    if request.POST:
        return logic.export_book_level_citations(books)
    template = 'reporting/report_book_citations.html'
    context = {
        'books': books,
        'all_book_links': all_book_links,
    }
    return render(
        request,
        template,
        context,
    )


@staff_member_required
def report_book_citing_works(request, book_id):
    """
    Displays citing works for a given book.
    """
    # Check if the books plugin exists or not.
    if not plugins.check_plugin_exists('books'):
        raise Http404("The Books plugin is not installed")
    from plugins.books import models as book_models
    book = get_object_or_404(
        book_models.Book,
        pk=book_id,
    )
    links = mm.BookLink.objects.filter(
        doi=book.doi,
        object_type='book',
    )
    if request.POST:
        return logic.export_citing_books(book, links)

    template = 'reporting/report_book_citing_works.html'
    context = {
        'book': book,
        'links': links,
    }
    return render(
        request,
        template,
        context,
    )


@editor_user_required
def report_crossref_dois(request, journal_id=None):
    """ A view that returns a report for Crossref mapping DOIs to URLS in tsv
    :param journal_id: A journal ID to filter the DOI identifiers by
    :return: an HttpResponse
    """
    journal = None
    if journal_id:
        journal = get_object_or_404(jm.Journal, pk=journal_id)

    response = HttpResponse(content_type='text/tsv')
    response['Content-Disposition'] = 'attachment; filename="DOI_urls.tsv"'
    logic.write_doi_tsv_report(to_write=response, journal=journal)
    return response


@editor_user_required
def report_crossref_dois_crosscheck(request, journal_id=None):
    """ A view that returns a report for Crosscheck mapping DOIs to URLS in tsv
    :param journal_id: A journal ID to filter the DOI identifiers by
    :return: an HttpResponse
    """
    journal = None
    if journal_id:
        journal = get_object_or_404(jm.Journal, pk=journal_id)

    response = HttpResponse(content_type='text/tsv')
    response['Content-Disposition'] = 'attachment; filename="DOI_urls.tsv"'
    logic.write_doi_tsv_report(
        to_write=response, journal=journal, crosscheck=True,
    )
    return response


@editor_user_required
def report_licenses(request):
    """
    Displays License information per journal and across all journals
    :param request: HttpRequest object
    :param journal_id: int, pk of a Journal object
    :return: HttpResponse or HttpRedirect
    """
    start_date, end_date = logic.get_start_and_end_date(request)

    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    data = logic.license_report(start_date, end_date)

    template = 'reporting/report_licenses.html'
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'date_form': date_form,
        'data': data,
    }

    return render(request, template, context)


@editor_user_required
def report_workflow(request):
    """
    Shows average times for:
    - Submission to acceptance
    - Acceptance to Publication
    - Submission to Publication
    :return: HttpResponse or HttpRedirect
    """
    start_date, end_date = logic.get_start_and_end_date(request)

    start_month, end_month, date_parts = logic.get_start_and_end_months(
        request)

    article_list = sm.Article.objects.filter(
        date_published__year__gte=date_parts.get('start_month_y'),
        date_published__month__gte=date_parts.get('start_month_m'),
        date_published__year__lte=date_parts.get('start_month_y'),
        date_published__month__lte=date_parts.get('end_month_m'),
    )

    if request.journal:
        article_list = article_list.filter(journal=request.journal)

    averages = logic.get_averages(
        article_list,
    )

    if request.POST:
        return logic.export_workflow_report(article_list, averages)

    month_form = forms.MonthForm(
        initial={
            'start_month': start_month, 'end_month': end_month,
        }
    )

    template = 'reporting/report_workflow.html'
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'month_form': month_form,
        'article_list': article_list,
        'averages': averages,
    }

    return render(request, template, context)


AUTHOR_REPORT_HEADERS = [
        "Author Name", "Author Email", "Author Affiliation",
        "Article ID", "Article Title", "Date Published",
]


@editor_user_required
def report_authors(request):
    start_date, end_date = logic.get_start_and_end_date(request)
    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )
    row_generator = None

    if request.GET:
        accounts = core_models.Account.objects.filter(
            authors__date_published__gte=start_date,
            authors__date_published__lte=end_date,
        )
        if request.journal:
            accounts = accounts.filter(authors__journal=request.journal)

        # This is a fairly expensive report, avoid memoizing entire set
        row_generator = (
            (
                account.full_name(), account.email, account.affiliation(),
                article.id, article.title, article.date_published
            )
            for account in accounts
            for article in account.published_articles()
        )
        if "csv" in request.GET:
            return logic.stream_csv(
                AUTHOR_REPORT_HEADERS, row_generator, "author_report.csv")
    context = {
        "headers": AUTHOR_REPORT_HEADERS,
        "rows": row_generator,
        "date_form": date_form,
    }

    template = 'reporting/report_authors.html'

    return render(request, template, context)


@editor_user_required
def report_reviewers(request):
    """
    Displays information about Peer Reviewers.
    :param request: HttpRequest object
    :return: HttpResponse or HttpRedirect
    """
    reviewers = logic.get_report_reviewers_data(
        journal=request.journal,
    )
    if 'csv' in request.GET:
        headers, iterable = logic.get_reviewers_export(
            reviewers,
        )
        return logic.stream_csv(
            headers,
            iterable,
            filename=f'{request.journal.code}_reviewer_report.csv'
        )
    template = 'reporting/report_reviewers.html'
    context = {
        'reviewers': reviewers,
    }
    return render(
        request,
        template,
        context,
    )


@editor_user_required
def report_authors_data(request):
    """
    Displays information about a Journal's authors.
    :param request: HttpRequest object
    :return: HttpResponse or HttpRedirect
    """
    authors = logic.get_report_author_data(
        journal=request.journal,
    )
    if 'csv' in request.GET:
        headers, iterable = logic.get_report_author_export(
            authors,
        )
        return logic.stream_csv(
            headers,
            iterable,
            f'{request.journal.code}_author_report.csv',
        )
    template = 'reporting/report_authors_data.html'
    context = {
        'authors': authors,
    }
    return render(
        request,
        template,
        context,
    )


@editor_user_required
def report_workflow_stage(request):
    start_month, end_month, date_parts = logic.get_start_and_end_months(
        request,
    )
    month_form = forms.MonthForm(
        initial={
            'start_month': start_month, 'end_month': end_month,
        }
    )
    workflow_times_list = logic.get_workflow_times(
        request.journal,
        date_parts,
    )
    if 'csv' in request.GET:
        headers, iterable = logic.get_workflow_times_export(
            workflow_times_list,
        )
        return logic.stream_csv(
            headers,
            iterable,
            filename=f'{request.journal.code}_workflow_stage_completion.csv',
        )

    context = {
        'month_form': month_form,
        'workflow_times_list': workflow_times_list,
    }

    template = 'reporting/workflow_timings_report.html',
    return render(
        request,
        template,
        context,
    )


@editor_user_required
def report_yearly_stats(request):
    yearly_stats = logic.get_yearly_stats(request.journal)

    if 'csv' in request.GET:
        return logic.stream_csv(
            ['Year', 'Articles Submitted', 'In Review', ' Articles Accepted',
             'Artcicles Rejected', 'Articles Published', 'Articles Archived'],
            logic.yearly_stats_iterable(yearly_stats),
            filename=f'{request.journal.code}_yearly_stats.csv'
        )

    template = 'reporting/report_yearly_stats.html'
    context = {
        'yearly_stats': yearly_stats
    }
    return render(
        request,
        template,
        context,
    )


@has_journal
@editor_user_required
def report_articles_under_review(request):
    review_assignments = rm.ReviewAssignment.objects.filter(
        article__stage=sm.STAGE_UNDER_REVIEW,
        article__journal=request.journal,
    ).select_related(
        'article',
        'article__journal',
        'reviewer',
    )
    if 'csv' in request.GET:
        return logic.stream_csv(
            [
                'Title', 'First Name', 'Last Name', 'Email Address',
                'Reviewer Decision', 'Recommendation', 'Access Code',
                'Due Date', 'Date Complete'
            ],
            logic.articles_under_review_iterable(review_assignments),
            filename=f'{request.journal.code}_articles_under_review.csv'
        )
    template = 'reporting/articles_under_review.html'
    context = {
        'review_assignments': review_assignments,
    }
    return render(
        request,
        template,
        context,
    )
