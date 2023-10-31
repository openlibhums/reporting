from django import template

register = template.Library()


@register.filter()
def display_timedelta(timedelta):
    """
    Converts a timedelta object for a neat display.
    """
    seconds = timedelta.total_seconds()
    days_display, hours_display = '', ''

    # 86400 seconds = 24 hours
    if seconds > 86400:
        days = seconds // 86400
        days_display = "{} days".format(int(days))
        seconds = seconds - days * 86400

    # 3600 seconds = 1 hour
    if seconds > 3600:
        hours = seconds // 3600
        hours_display = " {} hours".format(int(hours))

    return "{days} {hours}".format(
        days=days_display,
        hours=hours_display,
    )