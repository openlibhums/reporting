from django.template.loader import render_to_string


def nav_hook(context):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return ''
    user = request.user
    if (
        user.is_staff
        or user.is_editor(request)
        or user.is_journal_manager(request.journal)
        or (request.repository and user in request.repository.managers.all())
    ):
        return render_to_string("reporting/elements/nav.html", request=request)
    return ''
