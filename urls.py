from django.conf.urls import url

from plugins.reporting import views

urlpatterns = [
    url(r'^$',
        views.index,
        name='reporting_index'),
    url(r'^articles/(?P<journal_id>\d+)/$',
        views.report_articles,
        name='reporting_articles'),
    url(r'^production/$',
        views.report_production,
        name='reporting_production'),
    url(r'^journals/$',
        views.report_journals,
        name='reporting_journals'),
]
