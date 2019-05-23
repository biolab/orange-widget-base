"""
Testing framework for OWWidgets
"""
import os
import tempfile

import time
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch
from typing import List, Optional, TypeVar, Type

import sip

from AnyQt.QtCore import Qt
from AnyQt.QtTest import QTest, QSignalSpy
from AnyQt.QtWidgets import (
    QApplication, QComboBox, QSpinBox, QDoubleSpinBox, QSlider
)

from orangewidget.report.owreport import OWReport
from orangewidget.widget import OWWidget

sip.setdestroyonexit(False)

app = None

DEFAULT_TIMEOUT = 5000

# pylint: disable=invalid-name
T = TypeVar("T")


@contextmanager
def named_file(content, encoding=None, suffix=''):
    file = tempfile.NamedTemporaryFile("wt", delete=False,
                                       encoding=encoding, suffix=suffix)
    file.write(content)
    name = file.name
    file.close()
    try:
        yield name
    finally:
        os.remove(name)


class DummySignalManager:
    def __init__(self):
        self.outputs = {}

    def send(self, widget, signal_name, value, id):
        if not isinstance(signal_name, str):
            signal_name = signal_name.name
        self.outputs[(widget, signal_name)] = value


class GuiTest(unittest.TestCase):
    """Base class for tests that require a QApplication instance

    GuiTest ensures that a QApplication exists before tests are run an
    """
    @classmethod
    def setUpClass(cls):
        """Prepare for test execution.

        Ensure that a (single copy of) QApplication has been created
        """
        global app
        if app is None:
            app = QApplication([])


class WidgetTest(GuiTest):
    """Base class for widget tests

    Contains helper methods widget creation and working with signals.

    All widgets should be created by the create_widget method, as this
    will ensure they are created correctly.
    """

    widgets = []  # type: List[OWWidget]

    def __init_subclass__(cls, **kwargs):

        def test_minimum_size(self):
            widget = getattr(self, "widget", None)
            if widget is None:
                self.skipTest("minimum size not tested as .widget was not set")
            self.check_minimum_size(widget)

        if not hasattr(cls, "test_minimum_size"):
            cls.test_minimum_size = test_minimum_size

    @classmethod
    def setUpClass(cls):
        """Prepare environment for test execution

        Construct a dummy signal manager and monkey patch
        OWReport.get_instance to return a manually created instance.
        """
        super().setUpClass()

        cls.widgets = []

        cls.signal_manager = DummySignalManager()

        report = OWReport()
        cls.widgets.append(report)
        OWReport.get_instance = lambda: report
        if not (os.environ.get("TRAVIS") or os.environ.get("APPVEYOR")):
            report.show = Mock()

    def tearDown(self):
        """Process any pending events before the next test is executed."""
        self.process_events()
        super().tearDown()

    def create_widget(self, cls, stored_settings=None, reset_default_settings=True):
        # type: (Type[T], Optional[dict], bool) -> T
        """Create a widget instance using mock signal_manager.

        When used with default parameters, it also overrides settings stored
        on disk with default defined in class.

        After widget is created, QApplication.process_events is called to
        allow any singleShot timers defined in __init__ to execute.

        Parameters
        ----------
        cls : WidgetMetaClass
            Widget class to instantiate
        stored_settings : dict
            Default values for settings
        reset_default_settings : bool
            If set, widget will start with default values for settings,
            if not, values accumulated through the session will be used

        Returns
        -------
        Widget instance : cls
        """
        if reset_default_settings:
            self.reset_default_settings(cls)
        widget = cls.__new__(cls, signal_manager=self.signal_manager,
                             stored_settings=stored_settings)
        widget.__init__()
        self.process_events()
        self.widgets.append(widget)
        return widget

    @staticmethod
    def reset_default_settings(widget):
        """Reset default setting values for widget

        Discards settings read from disk and changes stored by fast_save

        Parameters
        ----------
        widget : OWWidget
            widget to reset settings for
        """
        settings_handler = getattr(widget, "settingsHandler", None)
        if settings_handler:
            # Rebind settings handler to get fresh copies of settings
            # in known_settings
            settings_handler.bind(widget)
            # Reset defaults read from disk
            settings_handler.defaults = {}
            # Reset context settings
            settings_handler.global_contexts = []

    def process_events(self, until: callable = None, timeout=DEFAULT_TIMEOUT):
        """Process Qt events, optionally until `until` returns
        something True-ish.

        Needs to be called manually as QApplication.exec is never called.

        Parameters
        ----------
        until: callable or None
            If callable, the events are processed until the function returns
            something True-ish.
        timeout: int
            If until condition is not satisfied within timeout milliseconds,
            a TimeoutError is raised.

        Returns
        -------
        If until is not None, the True-ish result of its call.
        """
        if until is None:
            until = lambda: True

        started = time.perf_counter()
        while True:
            app.processEvents()
            try:
                result = until()
                if result:
                    return result
            except Exception:  # until can fail with anything; pylint: disable=broad-except
                pass
            if (time.perf_counter() - started) * 1000 > timeout:
                raise TimeoutError()
            time.sleep(.05)

    def show(self, widget=None):
        """Show widget in interactive mode.

        Useful for debugging tests, as widget can be inspected manually.
        """
        widget = widget or self.widget
        widget.show()
        app.exec()

    def send_signal(self, input, value, *args, widget=None, wait=-1):
        """ Send signal to widget by calling appropriate triggers.

        Parameters
        ----------
        input : str
        value : Object
        id : int
            channel id, used for inputs with flag Multiple
        widget : Optional[OWWidget]
            widget to send signal to. If not set, self.widget is used
        wait : int
            The amount of time to wait for the widget to complete.
        """
        return self.send_signals([(input, value)], *args,
                                 widget=widget, wait=wait)

    def send_signals(self, signals, *args, widget=None, wait=-1):
        """ Send signals to widget by calling appropriate triggers.
        After all the signals are send, widget's handleNewSignals() in invoked.

        Parameters
        ----------
        signals : list of (str, Object)
        widget : Optional[OWWidget]
            widget to send signals to. If not set, self.widget is used
        wait : int
            The amount of time to wait for the widget to complete.
        """
        if widget is None:
            widget = self.widget
        for input, value in signals:
            self._send_signal(widget, input, value, *args)
        widget.handleNewSignals()
        if wait >= 0 and widget.isBlocking():
            spy = QSignalSpy(widget.blockingStateChanged)
            self.assertTrue(spy.wait(timeout=wait))

    @staticmethod
    def _send_signal(widget, input, value, *args):
        if isinstance(input, str):
            for input_signal in widget.get_signals("inputs"):
                if input_signal.name == input:
                    input = input_signal
                    break
            else:
                raise ValueError("'{}' is not an input name for widget {}"
                                 .format(input, type(widget).__name__))
        if widget.isBlocking():
            raise RuntimeError("'send_signal' called but the widget is in "
                               "blocking state and does not accept inputs.")
        handler = getattr(widget, input.handler)

        # Assert sent input is of correct class
        assert isinstance(value, (input.type, type(None))), \
            '{} should be {}'.format(value.__class__.__mro__, input.type)

        handler(value, *args)

    def wait_until_stop_blocking(self, widget=None, wait=DEFAULT_TIMEOUT):
        """Wait until the widget stops blocking i.e. finishes computation.

        Parameters
        ----------
        widget : Optional[OWWidget]
            widget to send signal to. If not set, self.widget is used
        wait : int
            The amount of time to wait for the widget to complete.

        """
        if widget is None:
            widget = self.widget

        if widget.isBlocking():
            spy = QSignalSpy(widget.blockingStateChanged)
            self.assertTrue(spy.wait(timeout=wait))

    def commit_and_wait(self, widget=None, wait=DEFAULT_TIMEOUT):
        """Unconditinal commit and wait to stop blocking if needed.

        Parameters
        ----------
        widget : Optional[OWWidget]
            widget to send signal to. If not set, self.widget is used
        wait : int
            The amount of time to wait for the widget to complete.

        """
        if widget is None:
            widget = self.widget

        widget.unconditional_commit()
        self.wait_until_stop_blocking(widget=widget, wait=wait)

    def get_output(self, output, widget=None, wait=DEFAULT_TIMEOUT):
        """Return the last output that has been sent from the widget.

        Parameters
        ----------
        output_name : str
        widget : Optional[OWWidget]
            widget whose output is returned. If not set, self.widget is used
        wait : int
            The amount of time (in milliseconds) to wait for widget to complete.

        Returns
        -------
        The last sent value of given output or None if nothing has been sent.
        """
        if widget is None:
            widget = self.widget

        if widget.isBlocking() and wait >= 0:
            spy = QSignalSpy(widget.blockingStateChanged)
            self.assertTrue(spy.wait(wait),
                            "Failed to get output in the specified timeout")
        if not isinstance(output, str):
            output = output.name
        # widget.outputs are old-style signals; if empty, use new style
        outputs = widget.outputs or widget.Outputs.__dict__.values()
        assert output in (out.name for out in outputs), \
            "widget {} has no output {}".format(widget.name, output)
        return self.signal_manager.outputs.get((widget, output), None)

    @contextmanager
    def modifiers(self, modifiers):
        """
        Context that simulates pressed modifiers

        Since QTest.keypress requries pressing some key, we simulate
        pressing "BassBoost" that looks exotic enough to not meddle with
        anything.
        """
        old_modifiers = QApplication.keyboardModifiers()
        try:
            QTest.keyPress(self.widget, Qt.Key_BassBoost, modifiers)
            yield
        finally:
            QTest.keyRelease(self.widget, Qt.Key_BassBoost, old_modifiers)

    def check_minimum_size(self, widget):

        def invalidate_cached_size_hint(w):
            # as in OWWidget.setVisible
            if w.controlArea is not None:
                w.controlArea.updateGeometry()
            if w.buttonsArea is not None:
                w.buttonsArea.updateGeometry()
            if w.mainArea is not None:
                w.mainArea.updateGeometry()

        invalidate_cached_size_hint(widget)
        min_size = widget.minimumSizeHint()
        self.assertLess(min_size.width(), 800)
        self.assertLess(min_size.height(), 700)


class TestWidgetTest(WidgetTest):
    """Meta tests for widget test helpers"""

    def test_process_events_handles_timeouts(self):
        with self.assertRaises(TimeoutError):
            self.process_events(until=lambda: False, timeout=0)

    def test_minimum_size(self):
        return  # skip this test


class BaseParameterMapping:
    """Base class for mapping between gui components and learner's parameters
    when testing learner widgets.

    Parameters
    ----------
    name : str
        Name of learner's parameter.

    gui_element : QWidget
        Gui component who's corresponding parameter is to be tested.

    values: list
        List of values to be tested.

    getter: function
        It gets component's value.

    setter: function
        It sets component's value.
    """

    def __init__(self, name, gui_element, values, getter, setter,
                 problem_type="both"):
        self.name = name
        self.gui_element = gui_element
        self.values = values
        self.get_value = getter
        self.set_value = setter
        self.problem_type = problem_type

    def __str__(self):
        if self.problem_type == "both":
            return self.name
        else:
            return "%s (%s)" % (self.name, self.problem_type)


class DefaultParameterMapping(BaseParameterMapping):
    """Class for mapping between gui components and learner's parameters
    when testing unchecked properties and therefore default parameters
    should be used.

    Parameters
    ----------
    name : str
        Name of learner's parameter.

    default_value: str, int,
        Value that should be used by default.
    """

    def __init__(self, name, default_value):
        super().__init__(name, None, [default_value],
                         lambda: default_value, lambda x: None)


class ParameterMapping(BaseParameterMapping):
    """Class for mapping between gui components and learner parameters
    when testing learner widgets

    Parameters
    ----------
    name : str
        Name of learner's parameter.

    gui_element : QWidget
        Gui component who's corresponding parameter is to be tested.

    values: list, mandatory for ComboBox, optional otherwise
        List of values to be tested. When None, it is set according to
        component's type.

    getter: function, optional
        It gets component's value. When None, it is set according to
        component's type.

    setter: function, optional
        It sets component's value. When None, it is set according to
        component's type.
    """

    def __init__(self, name, gui_element, values=None,
                 getter=None, setter=None, **kwargs):
        super().__init__(
            name, gui_element,
            values or self._default_values(gui_element),
            getter or self._default_get_value(gui_element, values),
            setter or self._default_set_value(gui_element, values),
            **kwargs)

    @staticmethod
    def get_gui_element(widget, attribute):
        return widget.controlled_attributes[attribute][0].control

    @classmethod
    def from_attribute(cls, widget, attribute, parameter=None):
        return cls(parameter or attribute, cls.get_gui_element(widget, attribute))

    @staticmethod
    def _default_values(gui_element):
        if isinstance(gui_element, (QSpinBox, QDoubleSpinBox, QSlider)):
            return [gui_element.minimum(), gui_element.maximum()]
        else:
            raise TypeError("{} is not supported".format(gui_element))

    @staticmethod
    def _default_get_value(gui_element, values):
        if isinstance(gui_element, (QSpinBox, QDoubleSpinBox, QSlider)):
            return lambda: gui_element.value()
        elif isinstance(gui_element, QComboBox):
            return lambda: values[gui_element.currentIndex()]
        else:
            raise TypeError("{} is not supported".format(gui_element))

    @staticmethod
    def _default_set_value(gui_element, values):
        if isinstance(gui_element, (QSpinBox, QDoubleSpinBox, QSlider)):
            return lambda val: gui_element.setValue(val)
        elif isinstance(gui_element, QComboBox):
            def fun(val):
                value = values.index(val)
                gui_element.activated.emit(value)
                gui_element.setCurrentIndex(value)

            return fun
        else:
            raise TypeError("{} is not supported".format(gui_element))


@contextmanager
def open_widget_classes():
    with patch.object(OWWidget, "__init_subclass__"):
        yield
