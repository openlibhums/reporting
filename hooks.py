from django.template.loader import render_to_string


def nav_hook(context):
    return render_to_string("reporting/elements/menu_nav.html")


def repository_manager_nav_hook(context):
    return render_to_string(
        "reporting/elements/repository_manager_nav.html",
    )
