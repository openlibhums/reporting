from django.urls import re_path

from plugins.reporting import views

urlpatterns = [
    re_path(r'^$',
        views.index,
        name='reporting_index'),
    re_path(r'^press/$',
        views.press,
        name='reporting_press'),
    re_path(r'^by_month/$',
        views.report_journal_usage_by_month,
        name='reporting_journal_usage_by_month'),
    re_path(r'^articles/(?P<journal_id>\d+)/$',
        views.report_articles,
        name='reporting_articles'),
    re_path(r'^production/$',
        views.report_production,
        name='reporting_production'),
    re_path(r'^review/$',
        views.report_review,
        name='reporting_review'),
    re_path(r'^review/journal/(?P<journal_id>\d+)/$',
        views.report_review,
        name='reporting_review_journal'),
    re_path(r'^geo/$',
        views.report_geo,
        name='reporting_geo'),
    re_path(r'^geo/(?P<journal_id>\d+)/$',
        views.report_geo,
        name='report_geo_journal'),
    re_path(r'^citations/articles/$',
        views.report_citations,
        name='report_citations'),
    re_path(r'^authors/$',
        views.report_authors,
        name='report_authors'),
    re_path(r'^citations/$',
        views.report_all_citations,
        name='report_all_citations'),
    re_path(r'^citations/journal/(?P<journal_id>\d+)/$',
        views.report_journal_citations,
        name='report_journal_citations'),
    re_path(r'^citations/journal/(?P<journal_id>\d+)/article/(?P<article_id>\d+)/$',
        views.report_article_citing_works,
        name='report_article_citing_works'),
    re_path(r'^citations/books/$',
        views.report_book_citations,
        name='report_book_citations'),
    re_path(r'^citations/books/(?P<book_id>\d+)/$',
        views.report_book_citing_works,
        name='report_book_citing_works'),
    re_path(r'^crossref/(?P<journal_id>\d+|)$',
        views.report_crossref_dois,
        name='reporting_crossref_dois'),
    re_path(r'^crossref/(?P<journal_id>\d+|)/crosscheck$',
        views.report_crossref_dois_crosscheck,
        name='reporting_crossref_dois_crosscheck'),
    re_path(r'^licenses/$',
        views.report_licenses,
        name='reporting_license'),
    re_path(r'^workflow/submssion_to_publication/$',
        views.report_workflow,
        name='reporting_workflow'),
    re_path(r'^reviewers/$',
        views.report_reviewers,
        name='report_reviewers'),
    re_path(r'^authors/data/$',
        views.report_authors_data,
        name='report_authors_data'),
    re_path(r'^workflow/stage_averages/$',
        views.report_workflow_stage,
        name='report_workflow_stages'),
    re_path(r'^yearly_stats/$',
        views.report_yearly_stats,
        name='report_yearly_stats'),
    re_path(r'^under-review/$',
        views.report_articles_under_review,
        name='report_articles_under_review'),
    re_path(r'^repository/metrics/$',
        views.report_preprints_metrics,
        name='report_preprints_metrics'),
    re_path(
        r'^api/geo/$',
        views.geographical_data,
        name='api_geographical_data'
    ),
]
