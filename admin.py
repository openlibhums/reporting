from django.contrib import admin

from plugins.reporting.models import *


class JournalReportRecipientAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user', 'journal',)
    list_filter = ('journal',)
    raw_id_fields = ('user',)


class JournalReportReceiptAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'sent_on')


class JournalReportStatsAdmin(admin.ModelAdmin):
    list_display = ('article', 'date', 'views', 'downloads', 'citations')
    list_filter = ('article',)
    raw_id_fields = ('article',)


admin_list = [
    (JournalReportRecipient, JournalReportRecipientAdmin),
    (JournalReportReceipt, JournalReportReceiptAdmin),
    (JournalReportStats, JournalReportStatsAdmin),
]

[admin.site.register(*t) for t in admin_list]