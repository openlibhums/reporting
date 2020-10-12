from django import forms
from django.forms import ModelChoiceField

from journal import models
from plugins.reporting import logic


class JournalChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class DateInput(forms.DateInput):
    input_type = 'date'


class MonthInput(forms.DateInput):
    input_type = 'month'


class YearInput(forms.DateInput):
    input_type = 'year'


class ArticleMetricsForm(forms.Form):
    journal = JournalChoiceField(
        queryset=models.Journal.objects.all().order_by('code'),
        label="Select a Journal",
        widget=forms.Select(attrs={"onChange": 'this.form.submit()'})
    )


class PeerReviewJournal(forms.Form):
    peer_review_journal = JournalChoiceField(
        queryset=models.Journal.objects.all().order_by('code'),
        label="Select a Journal",
        widget=forms.Select(attrs={"onChange": 'this.form.submit()'})
    )


class DateForm(forms.Form):
    start_date = forms.DateField(widget=DateInput())
    end_date = forms.DateField(widget=DateInput())


class MonthForm(forms.Form):
    start_month = forms.DateField(widget=MonthInput())
    end_month = forms.DateField(widget=MonthInput())


class YearForm(forms.Form):
    year = forms.IntegerField(
        max_value=logic.current_year(),
        min_value=logic.earliest_citation_year(),
    )
    all_time = forms.BooleanField(
        required=False,
        help_text='Ignors the year value.',
    )
