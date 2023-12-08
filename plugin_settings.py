from utils import models
from utils import plugins

PLUGIN_NAME = 'reporting'
DESCRIPTION = 'This is a plugin for reporting on articles in Janeway.'
AUTHOR = 'Andy Byers'
VERSION = '1.2'
SHORT_NAME = 'reporting'
DISPLAY_NAME = 'reporting'
MANAGER_URL = 'reporting_index'
JANEWAY_VERSION = "1.5.1"


class ReportingPlugin(plugins.Plugin):
    plugin_name = PLUGIN_NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    author = AUTHOR
    short_name = SHORT_NAME
    version = VERSION
    janeway_version = JANEWAY_VERSION
    manager_url = MANAGER_URL


def install():
    ReportingPlugin.install()


def hook_registry():
    return {}
