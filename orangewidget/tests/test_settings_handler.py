# pylint: disable=protected-access
from collections import namedtuple
import os
import pickle
from enum import IntEnum
from fractions import Fraction
from numbers import Integral
from tempfile import mkstemp, NamedTemporaryFile

import unittest
from typing import List, Dict, NamedTuple, Optional, Tuple, Set
from unittest.mock import patch, Mock
import warnings

from AnyQt.QtCore import pyqtSignal as Signal

from orangewidget.tests.base import named_file, override_default_settings, \
    WidgetTest
from orangewidget.settings import SettingsHandler, Setting, SettingProvider, \
    VERSION_KEY, rename_setting, Context, get_origin
from orangewidget.widget import OWBaseWidget, OWComponent


coords = NamedTuple("coords", (("x", int), ("y", str)))


class SortBy(IntEnum):
    NO_SORTING, INCREASING, DECREASING = range(3)


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
            xy = coords(0, "foo")

        with warnings.catch_warnings() as w:
            warnings.simplefilter("always")
            handler.create(Widget2)
            self.assertFalse(w)

    def test_settings_detect_types(self):
        class Widget(OWBaseWidget):
            name = "foo"

            a_bool = Setting(True)
            a_dict: Dict[str, int] = Setting(None)
            sorting = Setting(SortBy.INCREASING)
            sorting2: SortBy = Setting(None)
            xy = Setting(coords(0, "bar"))
            xy2: coords = Setting(None)

        provider = Widget.settingsHandler.provider
        self.assertIs(provider.settings["a_bool"].type, bool)
        self.assertEqual(provider.settings["a_dict"].type, Dict[str, int])
        self.assertIs(get_origin(provider.settings["a_dict"].type), dict)
        self.assertIs(provider.settings["sorting"].type, SortBy)
        self.assertIs(provider.settings["sorting2"].type, SortBy)
        self.assertIs(provider.settings["xy"].type, coords)
        self.assertFalse(provider.settings["xy"].nullable)
        self.assertIs(provider.settings["xy2"].type, coords)
        self.assertTrue(provider.settings["xy2"].nullable)

        with self.assertWarns(UserWarning):
            class Widget2(OWBaseWidget):
                name = "foo"
                a_list = Setting([])

        self.assertIsNone(
            Widget2.settingsHandler.provider.settings["a_list"].type)

        with self.assertWarns(UserWarning):
            class Widget3(OWBaseWidget):
                name = "foo"
                an_unknown = Setting(None)

        self.assertIsNone(
            Widget3.settingsHandler.provider.settings["an_unknown"].type)

    @patch("orangewidget.settings.get_type_hints", side_effect=TypeError)
    def test_settings_with_invalid_hints(self, _):
        with self.assertWarns(UserWarning):
            class Widget(OWBaseWidget):
                name = "foo"
                y = Setting(None)
                x = Setting(True)

        self.assertIsNone(Widget.settingsHandler.provider.settings["y"].type)
        self.assertEqual(Widget.settingsHandler.provider.settings["x"].type, bool)

    def test_settings_optional_is_nullable(self):
        class Widget(OWBaseWidget):
            name = "foo"
            u = Setting(42)
            x: int = Setting(42)
            y: Optional[int] = Setting(42)

        self.assertFalse(Widget.settingsHandler.provider.settings["u"].nullable)
        self.assertEqual(Widget.settingsHandler.provider.settings["u"].type, int)

        self.assertFalse(Widget.settingsHandler.provider.settings["x"].nullable)
        self.assertEqual(Widget.settingsHandler.provider.settings["x"].type, int)

        self.assertTrue(Widget.settingsHandler.provider.settings["y"].nullable)
        self.assertEqual(Widget.settingsHandler.provider.settings["y"].type, int)

    def test_is_allowed_type(self):
        iat = SettingsHandler.is_allowed_type
        self.assertTrue(iat(int))
        self.assertTrue(iat(str))
        self.assertTrue(iat(SortBy))
        self.assertTrue(iat(coords))
        self.assertTrue(iat(List[int]))
        self.assertTrue(iat(Set[int]))
        self.assertTrue(iat(Tuple[int]))
        self.assertTrue(iat(Dict[int, str]))
        self.assertTrue(iat(Tuple[int, str, bool]))

        composed = Tuple[Dict[int, Optional[List[int]]], Set[bool]]
        self.assertTrue(iat(composed))

        self.assertFalse(iat(unittest.TestCase))
        self.assertFalse(iat({}))
        self.assertFalse(iat(set()))
        self.assertFalse(iat([]))
        self.assertFalse(iat([42]))
        self.assertFalse(iat(()))
        self.assertFalse(iat((3, 5)))

        # Should return false because json doesn't accept tuples as dict keys
        self.assertFalse(iat(Dict[Tuple[int], int]))

        # Should return false because of `set` without type
        composed = Tuple[Dict[int, Optional[List[set]]], Set[bool]]
        self.assertFalse(iat(composed))

    def test_check_type_nullable(self):
        ct = SettingsHandler.check_type

        self.assertFalse(ct(None, int))
        self.assertFalse(ct(None, Setting(42)))
        self.assertTrue(ct(None, Setting(42, nullable=True)))

        self.assertFalse(ct(None, str))
        self.assertFalse(ct(None, Setting("bar")))
        self.assertTrue(ct(None, Setting("bar", nullable=True)))

        self.assertFalse(ct(None, SortBy))
        self.assertFalse(ct(None, Setting(SortBy.DECREASING)))
        self.assertTrue(ct(None, Setting("bar", nullable=True)))

    def test_check_type_from_setting(self):
        ct = SettingsHandler.check_type

        self.assertTrue(ct(42, Setting(13)))
        self.assertTrue(ct(b"foo", Setting(b"bar")))
        self.assertTrue(ct(SortBy.DECREASING, Setting(SortBy.DECREASING)))

    def test_check_type_simple(self):
        ct = SettingsHandler.check_type

        class IntegralDummy(Integral, float):
            pass

        self.assertTrue(ct(3, int))
        self.assertTrue(ct(IntegralDummy(), int))
        self.assertFalse(ct(3.14, int))
        self.assertFalse(ct((1, 2, 3), int))
        self.assertFalse(ct(unittest.TestCase, int))

        self.assertTrue(ct(3, float))
        self.assertTrue(ct(Fraction(3, 5), float))
        self.assertTrue(ct(3.14, float))
        self.assertFalse(ct((1, 2, 3), float))
        self.assertFalse(ct(unittest.TestCase, float))
        self.assertFalse(ct(None, float))

        self.assertTrue(ct(True, bool))
        self.assertTrue(ct(False, bool))
        self.assertTrue(ct(0, bool))
        self.assertTrue(ct(1, bool))
        self.assertFalse(ct(3, bool))
        self.assertFalse(ct(0.0, bool))
        self.assertFalse(ct((1, 2, 3), bool))
        self.assertFalse(ct(unittest.TestCase, bool))
        self.assertFalse(ct(None, bool))

        self.assertTrue(ct("foo", str))
        self.assertTrue(ct("", str))
        self.assertFalse(ct(3, str))
        self.assertFalse(ct((1, 2, 3), str))
        self.assertFalse(ct(unittest.TestCase, str))

        self.assertTrue(ct(b"foo", bytes))
        self.assertTrue(ct(b"", bytes))
        self.assertFalse(ct(3, bytes))
        self.assertFalse(ct((1, 2, 3), bytes))
        self.assertFalse(ct(unittest.TestCase, bytes))

        class NoYes(IntEnum):
            NO, YES = 0, 1

        self.assertTrue(ct(SortBy.DECREASING, SortBy))
        self.assertFalse(ct(1, SortBy))
        self.assertFalse(ct(NoYes.NO, SortBy))
        self.assertFalse(ct((1, 2, 3), SortBy))
        self.assertFalse(ct(unittest.TestCase, SortBy))

        self.assertTrue(ct(coords(0, "foo"), coords))
        self.assertFalse(ct(coords(0, 13), coords))
        self.assertFalse(ct((0, 1), coords))
        self.assertFalse(ct(unittest.TestCase, coords))

        tifs = Tuple[int, float, str]
        self.assertTrue(ct((1, 2.0, "foo"), tifs))
        self.assertTrue(ct((1, 2, "foo"), tifs))
        self.assertFalse(ct((), tifs))
        self.assertFalse(ct((1, "foo", 2.0), tifs))
        self.assertFalse(ct((1, 2.0), tifs))
        self.assertFalse(ct((1, 2.0, "foo", 3), tifs))

    def test_check_type_homogenous_generics(self):
        ct = SettingsHandler.check_type

        self.assertTrue(ct([1, 2, 3], List[int]))
        self.assertTrue(ct([], List[int]))
        self.assertFalse(ct([1, 2.0, 3], List[int]))
        self.assertFalse(ct((1, 2.0, 3), List[float]))
        self.assertFalse(ct((1, 2, 3), List[int]))
        self.assertFalse(ct(42, List[int]))

        self.assertTrue(ct((1, 2, 3), Tuple[int, ...]))
        self.assertTrue(ct((), Tuple[int, ...]))
        self.assertFalse(ct((1, 2.0, 3), Tuple[int, ...]))
        self.assertFalse(ct([1, 2, 3], Tuple[int, ...]))
        self.assertFalse(ct(42, Tuple[int, ...]))

        self.assertTrue(ct({1, 2, 3}, Set[int]))
        self.assertTrue(ct(set(), Set[int]))
        self.assertFalse(ct({1, 2.0, 3}, Set[int]))
        self.assertFalse(ct([1, 2, 3], Set[int]))
        self.assertFalse(ct(42, Set[int]))

        dios = Dict[int, Optional[str]]
        self.assertTrue(ct({1: None, 2: "bar", 3: None}, dios))
        self.assertTrue(ct({}, dios))
        self.assertFalse(ct({"foo": 13, 2: "bar", 3: None}, dios))
        self.assertFalse(ct({1, 2.0, 3}, dios))
        self.assertFalse(ct(42, dios))

    def test_check_type_complex(self):
        ct = SettingsHandler.check_type
        composed = Tuple[str, Dict[int, Optional[List[set]]], Set[bool]]

        self.assertTrue(ct(("foo", {4: [{1, 2}, {3, 1}], 4: []}, {False, True}), composed))
        self.assertTrue(ct(("foo", {4: [{1, 2}, {3, 1}], 4: []}, set()), composed))
        self.assertTrue(ct(("foo", {}, set()), composed))

    def test_check_type_from_packer(self):
        # Setting `unknown` will trigger a warning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            class Widget(OWBaseWidget):
                name = "foo"
                unknown = Setting(None)
                an_int = Setting(42)

        widget = Widget()
        widget.settingsHandler.pack_data(widget)
        widget.an_int = 42.0
        self.assertWarns(UserWarning, widget.settingsHandler.pack_data, widget)
        widget.an_int = [0] * 100
        self.assertWarns(UserWarning, widget.settingsHandler.pack_data, widget)


class Component(OWComponent):
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
        self.component = Component(self)

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
