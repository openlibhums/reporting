from utils import models, setting_handler

PLUGIN_NAME = 'reporting'
DESCRIPTION = 'This is a plugin for reporting on articles in Janeway.'
AUTHOR = 'Andy Byers'
VERSION = '1.0'
SHORT_NAME = 'reporting'
DISPLAY_NAME = 'reporting'
MANAGER_URL = 'reporting_index'


def get_self():
    new_plugin, created = models.Plugin.objects.get_or_create(
        name=SHORT_NAME,
        display_name=DISPLAY_NAME,
        version=VERSION,
        enabled=True
    )
    return new_plugin


def install():
    new_plugin, created = models.Plugin.objects.get_or_create(
        name=SHORT_NAME,
        display_name=DISPLAY_NAME,
        version=VERSION,
        enabled=True,
        press_wide=True
    )

    if created:
        print('Plugin {0} installed.'.format(PLUGIN_NAME))
    else:
        print('Plugin {0} is already installed.'.format(PLUGIN_NAME))


def hook_registry():
    return {}
