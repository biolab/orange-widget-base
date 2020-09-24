import unittest
import warnings
from collections import namedtuple
from enum import IntEnum
from typing import Dict, List, Set
from unittest.mock import Mock

import orangewidget.settings
from orangewidget.settings import Setting, SettingProvider, _apply_setting, \
    get_origin
from orangewidget.tests.base import WidgetTest
from orangewidget.widget import OWBaseWidget, OWComponent

SHOW_ZOOM_TOOLBAR = "show_zoom_toolbar"
SHOW_GRAPH = "show_graph"
GRAPH = "graph"
ZOOM_TOOLBAR = "zoom_toolbar"
SHOW_LABELS = "show_labels"
SHOW_X_AXIS = "show_x_axis"
SHOW_Y_AXIS = "show_y_axis"
ALLOW_ZOOMING = "allow_zooming"
A_LIST = "a_list"
A_SET = "a_set"
A_DICT = "a_dict"


class SortBy(IntEnum):
    NO_SORTING, INCREASING, DECREASING = range(3)


coords = namedtuple("coords", ("x", "y"))


def remove_base_settings(settings):
    class HoneyPot(OWBaseWidget):
        name = "honeypot"

    for name in HoneyPot.settingsHandler.provider.settings:
        settings.pop(name)


class SettingProviderTestCase(WidgetTest):
    def setUp(self):
        global default_provider
        default_provider = Widget.settingsHandler.provider

    def tearDown(self):
        default_provider.settings[SHOW_GRAPH].default = True
        default_provider.settings[SHOW_ZOOM_TOOLBAR].default = True
        default_provider.providers[GRAPH].settings[SHOW_LABELS].default = True
        default_provider.providers[GRAPH].settings[SHOW_X_AXIS].default = True
        default_provider.providers[GRAPH].settings[SHOW_Y_AXIS].default = True
        default_provider.providers[ZOOM_TOOLBAR].settings[ALLOW_ZOOMING].default = True

    def test_registers_all_settings(self):
        self.assertDefaultSettingsEqual(default_provider, {
            GRAPH: {
                SHOW_LABELS: True,
                SHOW_X_AXIS: True,
                SHOW_Y_AXIS: True,
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: True,
            },
            SHOW_ZOOM_TOOLBAR: True,
            SHOW_GRAPH: True,
        })

    def test_initialize_sets_defaults(self):
        widget = Widget()

        self.assertEqual(widget.show_graph, True)
        self.assertEqual(widget.show_zoom_toolbar, True)
        self.assertEqual(widget.graph.a_list, [])
        self.assertEqual(widget.graph.a_set, {1, 2, 3})
        self.assertEqual(widget.graph.a_dict, {1: 2, 3: 4})
        self.assertEqual(widget.graph.show_labels, True)
        self.assertEqual(widget.graph.show_x_axis, True)
        self.assertEqual(widget.graph.show_y_axis, True)
        self.assertEqual(widget.zoom_toolbar.allow_zooming, True)

    def test_initialize_with_data_sets_values_from_data(self):
        widget = Widget()
        default_provider.initialize(widget, {
            SHOW_GRAPH: False,
            GRAPH: {
                SHOW_Y_AXIS: False
            }
        })

        self.assertEqual(widget.show_graph, False)
        self.assertEqual(widget.show_zoom_toolbar, True)
        self.assertEqual(widget.graph.show_labels, True)
        self.assertEqual(widget.graph.show_x_axis, True)
        self.assertEqual(widget.graph.show_y_axis, False)
        self.assertEqual(widget.zoom_toolbar.allow_zooming, True)

    def test_initialize_with_data_stores_initial_values_until_instance_is_connected(self):
        widget = Widget.__new__(Widget)

        default_provider.initialize(widget, {
            SHOW_GRAPH: False,
            GRAPH: {
                SHOW_Y_AXIS: False
            }
        })

        self.assertFalse(hasattr(widget.graph, SHOW_Y_AXIS))
        widget.graph = Graph(widget)
        self.assertEqual(widget.graph.show_y_axis, False)

    def test_get_provider(self):
        self.assertEqual(default_provider.get_provider(BaseWidget), None)
        self.assertEqual(default_provider.get_provider(Widget),
                         default_provider)
        self.assertEqual(default_provider.get_provider(BaseGraph), None)
        self.assertEqual(default_provider.get_provider(Graph),
                         default_provider.providers[GRAPH])
        self.assertEqual(default_provider.get_provider(ExtendedGraph),
                         default_provider.providers[GRAPH])
        self.assertEqual(default_provider.get_provider(ZoomToolbar),
                         default_provider.providers[ZOOM_TOOLBAR])

    def test_pack_settings(self):
        widget = Widget()

        widget.show_graph = False
        widget.graph.show_y_axis = False

        packed_settings = default_provider.pack(widget)
        remove_base_settings(packed_settings)

        self.assertEqual(packed_settings, {
            SHOW_GRAPH: False,
            SHOW_ZOOM_TOOLBAR: True,
            GRAPH: {
                SHOW_LABELS: True,
                SHOW_X_AXIS: True,
                SHOW_Y_AXIS: False,
                A_LIST: [],
                A_SET: {1, 2, 3},
                A_DICT: {1: 2, 3: 4}
            },
            ZOOM_TOOLBAR: {
                ALLOW_ZOOMING: True,
            },
        })

    def test_unpack_settings(self):
        widget = Widget()
        default_provider.unpack(widget, {
            SHOW_GRAPH: False,
            GRAPH: {
                SHOW_Y_AXIS: False,
            },

        })

        self.assertEqual(widget.show_graph, False)
        self.assertEqual(widget.show_zoom_toolbar, True)
        self.assertEqual(widget.graph.show_labels, True)
        self.assertEqual(widget.graph.show_x_axis, True)
        self.assertEqual(widget.graph.show_y_axis, False)
        self.assertEqual(widget.zoom_toolbar.allow_zooming, True)

    def test_mutables_are_unpacked_in_place(self):
        widget = Widget()
        a_list = widget.graph.a_list
        a_set = widget.graph.a_set
        a_dict = widget.graph.a_dict
        default_provider.unpack(widget, {
            GRAPH: {
                A_LIST: [1, 2, 3],
                A_SET: {4, 5},
                A_DICT: {6: 7}
            },
        })
        self.assertIs(a_list, widget.graph.a_list)
        self.assertEqual(a_list, [1, 2, 3])
        self.assertIs(a_set, widget.graph.a_set)
        self.assertEqual(a_set, {4, 5})
        self.assertIs(a_dict, widget.graph.a_dict)
        self.assertEqual(a_dict, {6: 7})

    def test_traverse_settings_works_without_instance_or_data(self):
        settings = {}

        for setting, data, _ in default_provider.traverse_settings():
            settings[setting.name] = None
        remove_base_settings(settings)

        self.assertEqual(set(settings), {
            SHOW_ZOOM_TOOLBAR, SHOW_GRAPH,
            SHOW_LABELS, SHOW_X_AXIS, SHOW_Y_AXIS, A_LIST, A_SET, A_DICT,
            ALLOW_ZOOMING})

    def test_traverse_settings_selects_correct_data(self):
        settings = {}
        graph_data = {SHOW_LABELS: 3, SHOW_X_AXIS: 4, SHOW_Y_AXIS: 5,
                      A_LIST: [], A_SET: {1, 2, 3}, A_DICT: {1: 2, 3: 4}}
        zoom_data = {ALLOW_ZOOMING: 6}
        all_data = {SHOW_GRAPH: 1,
                    SHOW_ZOOM_TOOLBAR: 2,
                    GRAPH: graph_data,
                    ZOOM_TOOLBAR: zoom_data}

        for setting, data, _ in default_provider.traverse_settings(all_data):
            settings[setting.name] = data
        settings.pop("savedWidgetGeometry")
        settings.pop("controlAreaVisible")

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: all_data,
                SHOW_ZOOM_TOOLBAR: all_data,
                SHOW_LABELS: graph_data,
                SHOW_X_AXIS: graph_data,
                SHOW_Y_AXIS: graph_data,
                A_LIST: graph_data,
                A_SET: graph_data,
                A_DICT: graph_data,
                ALLOW_ZOOMING: zoom_data,
            }
        )

    def test_traverse_settings_with_partial_data(self):
        settings = {}
        graph_data = {SHOW_LABELS: 3, SHOW_X_AXIS: 4}
        all_data = {SHOW_GRAPH: 1, SHOW_ZOOM_TOOLBAR: 2, GRAPH: graph_data}

        for setting, data, _ in default_provider.traverse_settings(all_data):
            settings[setting.name] = data
        remove_base_settings(settings)

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: all_data,
                SHOW_ZOOM_TOOLBAR: all_data,
                SHOW_LABELS: graph_data,
                SHOW_X_AXIS: graph_data,
                SHOW_Y_AXIS: graph_data,
                A_LIST: graph_data,
                A_SET: graph_data,
                A_DICT: graph_data,
                ALLOW_ZOOMING: {},
            }
        )

    def test_traverse_settings_selects_correct_instance(self):
        settings = {}
        widget = Widget()

        for setting, _, instance in \
                default_provider.traverse_settings(instance=widget):
            settings[setting.name] = instance
        remove_base_settings(settings)

        self.assertEqual(
            {
                SHOW_GRAPH: widget,
                SHOW_ZOOM_TOOLBAR: widget,
                SHOW_LABELS: widget.graph,
                SHOW_X_AXIS: widget.graph,
                SHOW_Y_AXIS: widget.graph,
                A_LIST: widget.graph,
                A_SET: widget.graph,
                A_DICT: widget.graph,
                ALLOW_ZOOMING: widget.zoom_toolbar,
            },
            settings
        )

    def test_traverse_settings_with_partial_instance(self):
        settings = {}
        widget = Widget()
        widget.graph = None

        for setting, _, instance in \
                default_provider.traverse_settings(instance=widget):
            settings[setting.name] = instance
        remove_base_settings(settings)

        self.assertEqual(
            settings,
            {
                SHOW_GRAPH: widget,
                SHOW_ZOOM_TOOLBAR: widget,
                SHOW_LABELS: None,
                SHOW_X_AXIS: None,
                SHOW_Y_AXIS: None,
                A_LIST: None,
                A_SET: None,
                A_DICT: None,
                ALLOW_ZOOMING: widget.zoom_toolbar,
            }
        )

    def test_settings_detect_types(self):
        class Widget:
            a_bool = Setting(True)
            a_list = Setting([])
            a_dict: Dict[str, int] = Setting(None)
            sorting = Setting(SortBy.INCREASING)
            sorting2: SortBy = Setting(None)
            xy = Setting(coords(0, 0))
            xy2: coords = Setting(None)

        provider = SettingProvider(Widget)
        self.assertIs(provider.settings["a_bool"].type, bool)
        self.assertIs(provider.settings["a_list"].type, list)
        self.assertIs(get_origin(provider.settings["a_dict"].type), dict)
        self.assertIs(provider.settings["sorting"].type, SortBy)
        self.assertIs(provider.settings["sorting2"].type, SortBy)
        self.assertIs(provider.settings["xy"].type, coords)
        self.assertIs(provider.settings["xy2"].type, coords)


        with self.assertWarns(UserWarning):
            class Widget2(OWBaseWidget):
                name = "foo"
                an_unknown = Setting(None)

        self.assertIsNone(
            Widget2.settingsHandler.provider.settings["an_unknown"].type)

    def assertDefaultSettingsEqual(self, provider, defaults):
        for name, value in defaults.items():
            if isinstance(value, dict):
                self.assertIn(name, provider.providers)
                self.assertDefaultSettingsEqual(provider.providers[name], value)
            else:
                self.assertEqual(provider.settings[name].default, value)


class TestUtils(unittest.TestCase):
    def test_apply_settings_type_warnings(self):
        inst = Mock()

        # Warn about wrong type, but set it, don't interfere
        with self.assertWarns(UserWarning):
            _apply_setting(Setting(2, name="a"), inst, 5.4)
        self.assertEqual(inst.a, 5.4)

        # Warn about non-nullable set to None, but don't interfere
        with self.assertWarns(UserWarning):
            _apply_setting(Setting(2, name="b"), inst, None)
            self.assertIsNone(inst.b)

        with warnings.catch_warnings() as w:
            warnings.simplefilter("always")

            _apply_setting(Setting(2, name="b", nullable=True), inst, None)
            self.assertIsNone(inst.b)
            self.assertFalse(w)


def initialize_settings(instance):
    """This is usually done in Widget's new,
    but we avoid all that complications for tests."""
    provider = default_provider.get_provider(instance.__class__)
    if provider:
        provider.initialize(instance)

default_provider = None
""":type: SettingProvider"""


class BaseGraph(OWComponent):
    show_labels = Setting(True)


class Graph(BaseGraph):
    show_x_axis = Setting(True)
    show_y_axis = Setting(True)
    a_list: List[int] = Setting([])
    a_set: Set[int] = Setting({1, 2, 3})
    a_dict: Dict[int, int] = Setting({1: 2, 3: 4})


class ExtendedGraph(Graph):
    pass


class ZoomToolbar:
    allow_zooming = Setting(True)

    def __init__(self):
        initialize_settings(self)


class BaseWidget(OWBaseWidget, openclass=True):
    show_graph = Setting(True)

    graph = SettingProvider(Graph)

    def __init__(self):
        super().__init__()
        self.graph = Graph(self)


class Widget(BaseWidget):
    name = "foo"

    show_zoom_toolbar = Setting(True)

    zoom_toolbar = SettingProvider(ZoomToolbar)

    def __init__(self):
        super().__init__()
        initialize_settings(self)

        self.zoom_toolbar = ZoomToolbar()


if __name__ == '__main__':
    unittest.main(verbosity=2)
