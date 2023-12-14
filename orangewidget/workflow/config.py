"""
Base (example) Configuration for an Orange Widget based application.
"""
import warnings

import os
import sys
import itertools
from typing import Dict, Any, Optional, Iterable, List

import requests

from AnyQt.QtCore import QStandardPaths, QCoreApplication

from orangecanvas import config
from orangecanvas.utils.pkgmeta import entry_points, EntryPoint


# generated from biolab/orange3-addons repository
OFFICIAL_ADDON_LIST = "https://orange.biolab.si/addons/list"

WIDGETS_ENTRY = "orange.widgets"


class Config(config.Default):
    """
    Basic configuration for running orangewidget based workflow application.
    """
    OrganizationDomain = "biolab.si"
    ApplicationName = "Orange Canvas"
    try:
        from orangewidget.version import short_version as ApplicationVersion
    except ImportError:
        ApplicationVersion = "0.0.0"

    @staticmethod
    def widgets_entry_points():
        """
        Return an `EntryPoint` iterator for all registered 'orange.widgets'
        entry points.
        """
        return entry_points(group=WIDGETS_ENTRY)

    @staticmethod
    def addon_entry_points():
        return Config.widgets_entry_points()

    @staticmethod
    def addon_defaults_list(session=None):
        # type: (Optional[requests.Session]) -> List[Dict[str, Any]]
        """
        Return a list of available add-ons.
        """
        if session is None:
            session = requests.Session()
        return session.get(OFFICIAL_ADDON_LIST).json()

    @staticmethod
    def core_packages():
        # type: () -> List[str]
        """
        Return a list of 'core packages'

        These packages constitute required the application framework. They
        cannot be removes via the 'Add-on/plugins' manager. They however can
        be updated. The package that defines the application's `main()` entry
        point must always be in this list.
        """
        return ["orange-widget-base"]

    @staticmethod
    def examples_entry_points():
        # type: () -> Iterable[EntryPoint]
        """
        Return an iterator over the entry points yielding 'Example Workflows'
        """
        return entry_points(group="orange.widgets.tutorials")

    @staticmethod
    def widget_discovery(*args, **kwargs):
        from .discovery import WidgetDiscovery
        return WidgetDiscovery(*args, **kwargs)

    @staticmethod
    def workflow_constructor(*args, **kwargs):
        from .widgetsscheme import WidgetsScheme
        return WidgetsScheme(*args, **kwargs)


def data_dir_base():
    """
    Return the platform dependent generic application directory.

    This is usually

        - on windows: "%USERPROFILE%\\AppData\\Local\\"
        - on OSX:  "~/Library/Application Support/"
        - other: "~/.local/share/
    """
    return QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)


def data_dir(versioned=True):
    """
    Return the platform dependent application data directory.

    This is ``data_dir_base()``/{NAME}/{VERSION}/ directory if versioned is
    `True` and ``data_dir_base()``/{NAME}/ otherwise, where NAME is
    `QCoreApplication.applicationName()` and VERSION is
    `QCoreApplication.applicationVersion()`.
    """
    base = data_dir_base()
    assert base
    name = QCoreApplication.applicationName()
    version = QCoreApplication.applicationVersion()
    if not name:
        name = "Orange"
    if not version:
        version = "0.0.0"
    if versioned:
        return os.path.join(base, name, version)
    else:
        return os.path.join(base, name)


def cache_dir():
    """Return the application cache directory. If the directory path
    does not yet exists then create it.
    """
    warnings.warn(
        f"'{__name__}.cache_dir' is deprecated.",
        DeprecationWarning, stacklevel=2
    )
    base = QStandardPaths.writableLocation(QStandardPaths.GenericCacheLocation)
    name = QCoreApplication.applicationName()
    version = QCoreApplication.applicationVersion()
    if not name:
        name = "Orange"
    if not version:
        version = "0.0.0"
    path = os.path.join(base, name, version)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def log_dir():
    """
    Return the application log directory.
    """
    warnings.warn(
        f"'{__name__}.log_dir' is deprecated.",
        DeprecationWarning, stacklevel=2
    )
    if sys.platform == "darwin":
        name = QCoreApplication.applicationName() or "Orange"
        logdir = os.path.join(os.path.expanduser("~/Library/Logs"), name)
    else:
        logdir = data_dir()

    try:
        os.makedirs(logdir, exist_ok=True)
    except OSError:
        pass
    return logdir


def widget_settings_dir(versioned=True):
    """
    Return the platform dependent directory where widgets save their settings.

    .. deprecated: 4.0.1
    """
    warnings.warn(
        f"'{__name__}.widget_settings_dir' is deprecated.",
        DeprecationWarning, stacklevel=2
    )
    from orangewidget.settings import widget_settings_dir
    return widget_settings_dir(versioned)


def widgets_entry_points():
    return Config.widgets_entry_points()


def splash_screen():
    return Config.splash_screen()


def application_icon():
    return Config.application_icon()
