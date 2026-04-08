from django.template.loader import render_to_string


def nav_hook(context):
    return render_to_string("reporting/elements/menu_nav.html")
