# pylint: disable=protected-access
from collections import namedtuple
import os
import pickle
from enum import IntEnum
from tempfile import mkstemp, NamedTemporaryFile

import unittest
from typing import List
from unittest.mock import patch, Mock
import warnings

from AnyQt.QtCore import pyqtSignal as Signal

from orangewidget.tests.base import named_file, override_default_settings, \
    WidgetTest
from orangewidget.settings import SettingsHandler, Setting, SettingProvider,\
    VERSION_KEY, rename_setting, Context
from orangewidget.widget import OWBaseWidget


class SettingHandlerTestCase(WidgetTest):
    @patch('orangewidget.settings.SettingProvider', create=True)
    def test_create(self, SettingProvider):
        """:type SettingProvider: unittest.mock.Mock"""

        mock_read_defaults = Mock()
        with patch.object(SettingsHandler, 'read_defaults', mock_read_defaults):
            handler = SettingsHandler.create(SimpleWidget)

            self.assertEqual(handler.widget_class, SimpleWidget)
            # create needs to create a SettingProvider which traverses
            # the widget definition and collects all settings and read
            # all settings and for widget class
            SettingProvider.assert_called_once_with(SimpleWidget)
            mock_read_defaults.assert_called_once_with()

    def test_create_uses_template_if_provided(self):
        template = SettingsHandler()
        template.a = 'a'
        template.b = 'b'
        with override_default_settings(SimpleWidget):
            handler = SettingsHandler.create(SimpleWidget, template)
        self.assertEqual(handler.a, 'a')
        self.assertEqual(handler.b, 'b')

        # create should copy the template
        handler.b = 'B'
        self.assertEqual(template.b, 'b')

    def test_read_defaults(self):
        handler = SettingsHandler()
        handler.widget_class = SimpleWidget

        defaults = {'a': 5, 'b': {1: 5}}
        with override_default_settings(SimpleWidget, defaults):
            handler.read_defaults()

        self.assertEqual(handler.defaults, defaults)

    def test_write_defaults(self):
        fd, settings_file = mkstemp(suffix='.ini')

        handler = SettingsHandler()
        handler.widget_class = SimpleWidget
        handler.defaults = {'a': 5, 'b': {1: 5}}
        handler._get_settings_filename = lambda: settings_file
        handler.write_defaults()

        with open(settings_file, 'rb') as f:
            default_settings = pickle.load(f)
        os.close(fd)

        self.assertEqual(default_settings.pop(VERSION_KEY, -0xBAD),
                         handler.widget_class.settings_version,)
        self.assertEqual(default_settings, handler.defaults)

        os.remove(settings_file)

    def test_write_defaults_handles_permission_error(self):
        handler = SettingsHandler()

        with named_file("") as f:
            handler._get_settings_filename = lambda: f

            with patch("orangewidget.settings.log.error") as log, \
                patch('orangewidget.settings.open', create=True,
                       side_effect=PermissionError):
                handler.write_defaults()
                log.assert_called()

    def test_write_defaults_handles_writing_errors(self):
        handler = SettingsHandler()

        for error in (EOFError, IOError, pickle.PicklingError):
            f = NamedTemporaryFile("wt", delete=False)
            f.close()  # so it can be opened on windows
            handler._get_settings_filename = lambda x=f: x.name

            with patch("orangewidget.settings.log.error") as log, \
                    patch.object(handler, "write_defaults_file",
                                 side_effect=error):
                handler.write_defaults()
                log.assert_called()

            # Corrupt setting files should be removed
            self.assertFalse(os.path.exists(f.name))

    def test_initialize_widget(self):
        handler = SettingsHandler()
        handler.defaults = {'default': 42, 'setting': 1}
        handler.provider = provider = Mock()
        handler.widget_class = SimpleWidget
        provider.get_provider.return_value = provider
        widget = SimpleWidget()

        def reset_provider():
            provider.get_provider.return_value = None
            provider.reset_mock()
            provider.get_provider.return_value = provider

        # No data
        handler.initialize(widget)
        provider.initialize.assert_called_once_with(widget, {'default': 42,
                                                             'setting': 1})

        # Dictionary data
        reset_provider()
        handler.initialize(widget, {'setting': 5})
        provider.initialize.assert_called_once_with(widget, {'default': 42,
                                                             'setting': 5})

        # Pickled data
        reset_provider()
        handler.initialize(widget, pickle.dumps({'setting': 5}))
        provider.initialize.assert_called_once_with(widget, {'default': 42,
                                                             'setting': 5})

    def test_initialize_component(self):
        handler = SettingsHandler()
        handler.defaults = {'default': 42}
        provider = Mock()
        handler.widget_class = SimpleWidget
        handler.provider = Mock(get_provider=Mock(return_value=provider))
        widget = SimpleWidget()

        # No data
        handler.initialize(widget)
        provider.initialize.assert_called_once_with(widget, None)

        # Dictionary data
        provider.reset_mock()
        handler.initialize(widget, {'setting': 5})
        provider.initialize.assert_called_once_with(widget, {'setting': 5})

        # Pickled data
        provider.reset_mock()
        handler.initialize(widget, pickle.dumps({'setting': 5}))
        provider.initialize.assert_called_once_with(widget, {'setting': 5})

    @patch('orangewidget.settings.SettingProvider', create=True)
    def test_initialize_with_no_provider(self, SettingProvider):
        """:type SettingProvider: unittest.mock.Mock"""
        handler = SettingsHandler()
        handler.provider = Mock(get_provider=Mock(return_value=None))
        handler.widget_class = SimpleWidget
        provider = Mock()
        SettingProvider.return_value = provider
        widget = SimpleWidget()

        # initializing an undeclared provider should display a warning
        with warnings.catch_warnings(record=True) as w:
            handler.initialize(widget)

            self.assertEqual(1, len(w))

        SettingProvider.assert_called_once_with(SimpleWidget)
        provider.initialize.assert_called_once_with(widget, None)

    def test_schema_only_settings(self):
        handler = SettingsHandler()
        with override_default_settings(SimpleWidget):
            handler.bind(SimpleWidget)

        widget = SimpleWidget()

        # update_defaults should not update defaults
        widget.schema_only_setting = 5
        handler.update_defaults(widget)
        self.assertEqual(
            handler.known_settings['schema_only_setting'].default, None)
        widget.component.schema_only_setting = "foo"
        self.assertEqual(
            handler.known_settings['component.schema_only_setting'].default, "only")

        # pack_data should pack setting
        widget.schema_only_setting = 5
        widget.component.schema_only_setting = "foo"
        data = handler.pack_data(widget)
        self.assertEqual(data['schema_only_setting'], 5)
        self.assertEqual(data['component']['schema_only_setting'], "foo")

    def test_read_defaults_migrates_settings(self):
        handler = SettingsHandler()
        handler.widget_class = SimpleWidget

        migrate_settings = Mock()
        with patch.object(SimpleWidget, "migrate_settings", migrate_settings):
            # Old settings without version
            settings = {"value": 5}
            with override_default_settings(SimpleWidget, settings):
                handler.read_defaults()
            migrate_settings.assert_called_with(settings, 0)

            migrate_settings.reset()
            # Settings with version
            settings_with_version = dict(settings)
            settings_with_version[VERSION_KEY] = 1
            with override_default_settings(SimpleWidget, settings_with_version):
                handler.read_defaults()
            migrate_settings.assert_called_with(settings, 1)

    def test_initialize_migrates_settings(self):
        handler = SettingsHandler()
        with override_default_settings(SimpleWidget):
            handler.bind(SimpleWidget)

        widget = SimpleWidget()

        migrate_settings = Mock()
        with patch.object(SimpleWidget, "migrate_settings", migrate_settings):
            # Old settings without version
            settings = {"value": 5}

            handler.initialize(widget, settings)
            migrate_settings.assert_called_with(settings, 0)

            migrate_settings.reset_mock()
            # Settings with version

            settings_with_version = dict(settings)
            settings_with_version[VERSION_KEY] = 1
            handler.initialize(widget, settings_with_version)
            migrate_settings.assert_called_with(settings, 1)

    def test_pack_settings_stores_version(self):
        handler = SettingsHandler()
        handler.bind(SimpleWidget)

        widget = SimpleWidget()

        settings = handler.pack_data(widget)
        self.assertIn(VERSION_KEY, settings)

    def test_initialize_copies_mutables(self):
        handler = SettingsHandler()
        handler.bind(SimpleWidget)
        handler.defaults = dict(list_setting=[])

        widget = SimpleWidget()
        handler.initialize(widget)

        widget2 = SimpleWidget()
        handler.initialize(widget2)

        self.assertNotEqual(id(widget.list_setting), id(widget2.list_setting))

    def test_about_pack_settings_signal(self):
        widget = SimpleWidget()
        handler = widget.settingsHandler
        fn = Mock()
        widget.settingsAboutToBePacked.connect(fn)
        handler.pack_data(widget)
        self.assertEqual(1, fn.call_count)
        handler.update_defaults(widget)
        self.assertEqual(2, fn.call_count)

    def test_warns_against_unsupported_types(self):
        class Widget:
            func = Setting(abs)
        handler = SettingsHandler()
        with self.assertWarns(UserWarning):
            bound = handler.create(Widget)
        self.assertEqual(bound.known_settings["func"].default, abs)

        class SortBy(IntEnum):
            NO_SORTING, INCREASING, DECREASING = range(3)

        coords = namedtuple("coords", ("x", "y"))

        class Widget2:
            sorting = Setting(SortBy.DECREASING)
            xy = coords(0, 0)

        with warnings.catch_warnings() as w:
            warnings.simplefilter("always")
            handler.create(Widget2)
            self.assertFalse(w)


class Component:
    int_setting = Setting(42)
    schema_only_setting = Setting("only", schema_only=True)


class SimpleWidget(OWBaseWidget, openclass=True):
    name = "Simple widget"
    settings_version = 1

    setting = Setting(42)
    schema_only_setting: int = Setting(None, schema_only=True)
    list_setting: List[int] = Setting([])
    non_setting = 5

    component = SettingProvider(Component)
    settingsAboutToBePacked = Signal()

    def __init__(self):
        super().__init__()
        self.component = Component()

    migrate_settings = Mock()
    migrate_context = Mock()


class SimpleWidgetMk1(SimpleWidget):
    pass


class SimpleWidgetMk2(SimpleWidget):
    pass


class WidgetWithNoProviderDeclared:
    def __init__(self):
        self.undeclared_component = Component()


class MigrationsTestCase(unittest.TestCase):
    def test_rename_settings(self):
        some_settings = dict(foo=42, bar=13)
        rename_setting(some_settings, "foo", "baz")
        self.assertDictEqual(some_settings, dict(baz=42, bar=13))

        self.assertRaises(KeyError, rename_setting, some_settings, "qux", "quux")

        context = Context(values=dict(foo=42, bar=13))
        rename_setting(context, "foo", "baz")
        self.assertDictEqual(context.values, dict(baz=42, bar=13))
