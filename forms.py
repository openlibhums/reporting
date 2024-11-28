from dateutil.relativedelta import relativedelta
from dateutil.parser import parse

from django import forms
from django.forms import ModelChoiceField
from django.utils import timezone

from journal import models


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
        widget=forms.Select(attrs={"onChange": 'this.form.submit()'}),
    )


class PeerReviewJournal(forms.Form):
    peer_review_journal = JournalChoiceField(
        queryset=models.Journal.objects.all().order_by('code'),
        label="Select a Journal",
        widget=forms.Select(attrs={"onChange": 'this.form.submit()'}),
    )


class DateForm(forms.Form):
    start_date = forms.DateField(widget=DateInput())
    end_date = forms.DateField(widget=DateInput())


class MonthForm(forms.Form):
    start_month = forms.DateField(widget=MonthInput())
    end_month = forms.DateField(widget=MonthInput())


class YearForm(forms.Form):
    year = forms.IntegerField()
    all_time = forms.BooleanField(
        required=False,
        help_text='Ignores the year value.',
    )


class DateRangeForm(forms.Form):
    start_date = forms.DateTimeField(
        label='Start Date',
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'},
        ),
    )
    end_date = forms.DateTimeField(
        label='End Date',
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'},
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data:
            current_date = timezone.now()
            start_date = current_date.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)

            self.fields['start_date'].initial = start_date.strftime('%Y-%m-%d')
            self.fields['end_date'].initial = end_date.strftime('%Y-%m-%d')
