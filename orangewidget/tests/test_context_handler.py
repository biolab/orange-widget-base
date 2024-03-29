import pickle
from copy import copy, deepcopy
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch, call
from AnyQt.QtCore import pyqtSignal as Signal, QObject
from orangewidget.settings import (
    ContextHandler, ContextSetting, Context, Setting, SettingsPrinter,
    VERSION_KEY, IncompatibleContext, SettingProvider)
from orangewidget.tests.base import override_default_settings

__author__ = 'anze'


class Component:
    int_setting = Setting(42)
    context_setting = ContextSetting("global")
    schema_only_context_setting = ContextSetting("only", schema_only=True)


class SimpleWidget(QObject):
    settings_version = 1

    setting = Setting(42)
    schema_only_setting = Setting(None, schema_only=True)

    context_setting = ContextSetting(42)
    schema_only_context_setting = ContextSetting(None, schema_only=True)
    settingsAboutToBePacked = Signal()

    component = SettingProvider(Component)

    migrate_settings = Mock()
    migrate_context = Mock()

    storeSpecificSettings = Mock()

    def __init__(self):
        super().__init__()
        self.component = Component()


class DummyContext(Context):
    id = 0

    def __init__(self, version=None):
        super().__init__()
        DummyContext.id += 1
        self.id = DummyContext.id
        if version:
            self.values[VERSION_KEY] = version

    def __repr__(self):
        return "Context(id={})".format(self.id)
    __str__ = __repr__

    def __eq__(self, other):
        if not isinstance(other, DummyContext):
            return False
        return self.id == other.id


def create_defaults_file(contexts):
    b = BytesIO()
    pickle.dump({"x": 5}, b)
    pickle.dump(contexts, b)
    b.seek(0)
    return b


class TestContextHandler(TestCase):
    def test_read_defaults(self):
        contexts = [DummyContext() for _ in range(3)]

        handler = ContextHandler()
        handler.widget_class = SimpleWidget
        handler.provider = SettingProvider(handler.widget_class)

        # Old settings without version
        migrate_context = Mock()
        with patch.object(SimpleWidget, "migrate_context", migrate_context):
            handler.read_defaults_file(create_defaults_file(contexts))
        self.assertSequenceEqual(handler.global_contexts, contexts)
        migrate_context.assert_has_calls([call(c, 0) for c in contexts])

        # Settings with version
        contexts = [DummyContext(version=i) for i in range(1, 4)]
        migrate_context.reset_mock()
        with patch.object(SimpleWidget, "migrate_context", migrate_context):
            handler.read_defaults_file(create_defaults_file(contexts))
        self.assertSequenceEqual(handler.global_contexts, contexts)
        migrate_context.assert_has_calls([call(c, c.values[VERSION_KEY]) for c in contexts])

    def test_read_defaults_ensures_no_schema_only(self):
        handler = ContextHandler()
        handler.widget_class = SimpleWidget
        handler.provider = SettingProvider(SimpleWidget)

        def migrate_settings(settings, _):
            settings["setting"] = 5
            settings["schema_only_setting"] = True

        def migrate_context(context, _):
            context.values["context_setting"] = 5
            context.values["schema_only_context_setting"] = True

        with patch.object(SimpleWidget, "migrate_settings", migrate_settings), \
             patch.object(SimpleWidget, "migrate_context", migrate_context), \
             override_default_settings(SimpleWidget, {"value": 42},
                                       [DummyContext()], handler=ContextHandler):
            handler.read_defaults()
            self.assertEqual(handler.defaults, {'value': 42, 'setting': 5})
            self.assertEqual(handler.global_contexts[0].values, {'context_setting': 5})

    def test_initialize(self):
        handler = ContextHandler()
        handler.provider = Mock()
        handler.widget_class = SimpleWidget

        # Context settings from data
        widget = SimpleWidget()
        context_settings = [DummyContext()]
        handler.initialize(widget, {'context_settings': context_settings})
        self.assertTrue(hasattr(widget, 'context_settings'))
        self.assertEqual(widget.context_settings, context_settings)

        # Default (global) context settings
        widget = SimpleWidget()
        handler.initialize(widget)
        self.assertTrue(hasattr(widget, 'context_settings'))
        self.assertEqual(widget.context_settings, handler.global_contexts)

    def test_initialize_migrates_contexts(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)

        widget = SimpleWidget()

        # Old settings without version
        contexts = [DummyContext() for _ in range(3)]
        migrate_context = Mock()
        with patch.object(SimpleWidget, "migrate_context", migrate_context):
            handler.initialize(widget, dict(context_settings=contexts))
        migrate_context.assert_has_calls([call(c, 0) for c in contexts])

        # Settings with version
        contexts = [DummyContext(version=i) for i in range(1, 4)]
        migrate_context = Mock()
        with patch.object(SimpleWidget, "migrate_context", migrate_context):
            handler.initialize(widget, dict(context_settings=deepcopy(contexts)))
        migrate_context.assert_has_calls([call(c, c.values[VERSION_KEY]) for c in contexts])

    def test_migrates_settings_removes_incompatible(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)

        widget = SimpleWidget()

        contexts = [Context(foo=i) for i in (13, 13, 0, 1, 13, 2, 13)]

        def migrate_context(context, _):
            if context.foo == 13:
                raise IncompatibleContext()

        with patch.object(SimpleWidget, "migrate_context", migrate_context):
            handler.initialize(widget, dict(context_settings=contexts))
            contexts = widget.context_settings
            self.assertEqual(len(contexts), 3)
            self.assertTrue(
                all(context.foo == i
                    for i, context in enumerate(contexts)))

    def test_fast_save(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)

        widget = SimpleWidget()
        handler.initialize(widget)

        context = widget.current_context = handler.new_context()
        handler.fast_save(widget, 'context_setting', 55)
        self.assertEqual(context.values['context_setting'], 55)
        self.assertEqual(handler.known_settings['context_setting'].default,
                         SimpleWidget.context_setting.default)

    def test_find_or_create_context(self):
        widget = SimpleWidget()
        handler = ContextHandler()
        handler.match = lambda context, i: (context.i == i) * 2
        handler.clone_context = lambda context, i: copy(context)

        c1, c2, c3, c4, c5, c6, c7, c8, c9 = (Context(i=i)
                                              for i in range(1, 10))

        # finding a perfect match in global_contexts should copy it to
        # the front of context_settings (and leave globals as-is)
        widget.context_settings = [c2, c5]
        handler.global_contexts = [c3, c7]
        context, new = handler.find_or_create_context(widget, 7)
        self.assertEqual(context.i, 7)
        self.assertEqual([c.i for c in widget.context_settings], [7, 2, 5])
        self.assertEqual([c.i for c in handler.global_contexts], [3, 7])

        # finding a perfect match in context_settings should move it to
        # the front of the list
        widget.context_settings = [c2, c5]
        handler.global_contexts = [c3, c7]
        context, new = handler.find_or_create_context(widget, 5)
        self.assertEqual(context.i, 5)
        self.assertEqual([c.i for c in widget.context_settings], [5, 2])
        self.assertEqual([c.i for c in handler.global_contexts], [3, 7])

    def test_pack_settings_stores_version(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)

        widget = SimpleWidget()
        handler.initialize(widget)
        widget.context_setting = [DummyContext() for _ in range(3)]

        settings = handler.pack_data(widget)
        self.assertIn("context_settings", settings)
        for c in settings["context_settings"]:
            self.assertIn(VERSION_KEY, c.values)

    def test_write_defaults_stores_version(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)
        widget = SimpleWidget()
        widget.current_context = None
        widget.context_settings = [DummyContext() for _ in range(3)]
        handler.update_defaults(widget)

        f = BytesIO()
        f.close = lambda: None
        with patch("builtins.open", Mock(return_value=f)):
            handler.write_defaults()
            f.seek(0)
            pickle.load(f)  # settings
            contexts = pickle.load(f)
            for c in contexts:
                self.assertEqual(c.values.get("__version__", 0xBAD), 1)

    def test_close_context(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)
        widget = SimpleWidget()
        widget.storeSpecificSettings = Mock()
        handler.initialize(widget)
        widget.schema_only_setting = 0xD06F00D
        widget.current_context = handler.new_context()
        handler.close_context(widget)
        self.assertEqual(widget.schema_only_setting, 0xD06F00D)

    def test_about_pack_settings_signal(self):
        handler = ContextHandler()
        handler.bind(SimpleWidget)
        widget = SimpleWidget()
        handler.initialize(widget)
        fn = Mock()
        widget.settingsAboutToBePacked.connect(fn)
        handler.pack_data(widget)
        self.assertEqual(1, fn.call_count)
        handler.update_defaults(widget)
        self.assertEqual(2, fn.call_count)

    def test_schema_only_settings(self):
        handler = ContextHandler()
        with override_default_settings(SimpleWidget, handler=ContextHandler):
            handler.bind(SimpleWidget)

        # fast_save should not update defaults
        widget = SimpleWidget()
        handler.initialize(widget)
        context = widget.current_context = handler.new_context()
        widget.context_settings.append(context)
        handler.fast_save(widget, 'schema_only_context_setting', 5)
        self.assertEqual(
            handler.known_settings['schema_only_context_setting'].default, None)
        handler.fast_save(widget, 'component.schema_only_context_setting', 5)
        self.assertEqual(
            handler.known_settings['component.schema_only_context_setting'].default, "only")

        # update_defaults should not update defaults
        widget.schema_only_context_setting = 5
        handler.update_defaults(widget)
        self.assertEqual(
            handler.known_settings['schema_only_context_setting'].default, None)
        widget.component.schema_only_setting = 5
        self.assertEqual(
            handler.known_settings['component.schema_only_context_setting'].default, "only")

        # close_context should pack setting
        widget.schema_only_context_setting = 5
        widget.component.context_setting = 5
        widget.component.schema_only_context_setting = 5
        handler.close_context(widget)
        global_values = handler.global_contexts[0].values
        self.assertTrue('context_setting' in global_values)
        self.assertFalse('schema_only_context_setting' in global_values)
        self.assertTrue('context_setting' in global_values["component"])
        self.assertFalse('schema_only_context_setting' in global_values["component"])


class TestSettingsPrinter(TestCase):
    def test_formats_contexts(self):
        settings = dict(key1=1, key2=2,
                        context_settings=[
                            Context(param1=1, param2=2,
                                    values=dict(value1=1,
                                                value2=2)),
                            Context(param1=3, param2=4,
                                    values=dict(value1=5,
                                                value2=6))
                        ])
        pp = SettingsPrinter()

        output = pp.pformat(settings)
        # parameter of all contexts should be visible in the output
        self.assertIn("param1=1", output)
        self.assertIn("param2=2", output)
        self.assertIn("param1=3", output)
        self.assertIn("param2=4", output)


class TestContext(TestCase):
    def test_context_eq(self):
        context1 = Context(x=12, y=["a", "list"])
        context2 = Context(x=12, y=["a", "list"])
        context3 = Context(x=13, y=["a", "list"])
        self.assertTrue(context1 == context2)
        self.assertFalse(context2 == context3)

        self.assertRaises(TypeError, hash, context1)
