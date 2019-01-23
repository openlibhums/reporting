from django.shortcuts import render, reverse, redirect, get_object_or_404

from plugins.reporting import forms, logic
from journal import models
from production import models as pm
from security.decorators import editor_user_required


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
                        kwargs={'journal_id': journal.pk}
                    )
                )

    context = {
        'journal_report_form': journal_report_form
    }

    return render(request, 'reporting/index.html', context)


@editor_user_required
def report_journals(request):
    """
    Displays views and downloads for each journal.
    :param request: HttpRequest object
    :return: HttpResponse or HttpRedirect
    """
    journals = models.Journal.objects.filter(is_remote=False)
    start_date, end_date = logic.get_start_and_end_date(request)
    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    for journal in journals:
        journal.views, journal.downloads = logic.get_accesses(
            journal,
            start_date,
            end_date
        )

    if request.POST:
        return logic.export_journal_csv(journals)

    template = 'reporting/report_journals.html'
    context = {
        'journals': journals,
        'start_date': start_date,
        'end_date': end_date,
        'date_form': date_form,
    }

    return render(request, template, context)


@editor_user_required
def report_articles(request, journal_id):
    """
    Displays views and downloads for each article in a journal.
    :param request: HttpRequest object
    :param journal_id: int, pk of a Journal object
    :return: HttpResponse or HttpRedirect
    """
    journal = get_object_or_404(models.Journal, pk=journal_id)
    start_date, end_date = logic.get_start_and_end_date(request)
    articles = logic.get_articles(journal, start_date, end_date)

    date_form = forms.DateForm(
        initial={'start_date': start_date, 'end_date': end_date}
    )

    if request.POST:
        return logic.export_article_csv(articles)

    template = 'reporting/report_articles.html'
    context = {
        'journal': journal,
        'articles': articles,
        'start_date': start_date,
        'end_date': end_date,
        'date_form': date_form,
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
