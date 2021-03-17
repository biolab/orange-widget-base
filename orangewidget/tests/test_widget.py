# pylint: disable=protected-access

import gc
import weakref

import unittest
from unittest.mock import patch, MagicMock

from AnyQt.QtCore import Qt, QPoint, QRect, QByteArray, QObject, pyqtSignal
from AnyQt.QtGui import QShowEvent
from AnyQt.QtWidgets import QAction
from AnyQt.QtTest import QSignalSpy, QTest

from orangewidget.gui import OWComponent
from orangewidget.settings import Setting, SettingProvider
from orangewidget.tests.base import WidgetTest
from orangewidget.widget import OWBaseWidget, Msg, StateInfo
from orangewidget.utils.messagewidget import MessagesWidget


class DummyComponent(OWComponent):
    dummyattr = None


class MyWidget(OWBaseWidget):
    name = "Dummy"

    field = Setting(42)
    component = SettingProvider(DummyComponent)

    def __init__(self):
        super().__init__()

        self.component = DummyComponent(self)
        self.widget = None


class WidgetTestCase(WidgetTest):
    def test_setattr(self):
        widget = self.create_widget(MyWidget)
        widget.widget = self.create_widget(MyWidget)

        setattr(widget, 'field', 1)
        self.assertEqual(widget.field, 1)

        setattr(widget, 'component.dummyattr', 2)
        self.assertEqual(widget.component.dummyattr, 2)

        setattr(widget, 'widget.field', 3)
        self.assertEqual(widget.widget.field, 3)

        setattr(widget, 'unknown_field', 4)
        self.assertEqual(widget.unknown_field, 4)

        with self.assertRaises(AttributeError):
            setattr(widget, 'widget.widget.field', 5)

        with self.assertRaises(AttributeError):
            setattr(widget, 'unknown_field2.field', 6)

    def test_notify_controller_on_attribute_change(self):
        widget = self.create_widget(MyWidget)

        callback = MagicMock()
        callback2 = MagicMock()

        widget.connect_control('field', callback)
        widget.connect_control('field', callback2)
        widget.field = 5
        self.assertTrue(callback.called)
        self.assertTrue(callback2.called)

    def test_widget_tests_do_not_use_stored_settings(self):
        widget = self.create_widget(MyWidget)

        widget.field = 5
        widget.saveSettings()

        widget2 = self.create_widget(MyWidget)
        self.assertEqual(widget2.field, 42)

    def test_widget_help_action(self):
        widget = self.create_widget(MyWidget)
        help_action = widget.findChild(QAction, "action-help")
        help_action.setEnabled(True)
        help_action.setVisible(True)

    def test_widget_without_basic_layout(self):
        class TestWidget2(OWBaseWidget):
            name = "Test"

            want_basic_layout = False

        w = TestWidget2()
        w.showEvent(QShowEvent())
        QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, QPoint(1, 1))
        _ = w.sizeHint()

    def test_store_restore_layout_geom(self):
        class Widget(OWBaseWidget):
            name = "Who"
            want_control_area = True

        w = Widget()
        w._OWBaseWidget__setControlAreaVisible(False)
        w.setGeometry(QRect(51, 52, 53, 54))
        state = w.saveGeometryAndLayoutState()
        w1 = Widget()
        self.assertTrue(w1.restoreGeometryAndLayoutState(state))
        self.assertEqual(w1.geometry(), QRect(51, 52, 53, 54))
        self.assertFalse(w1.controlAreaVisible)

        Widget.want_control_area = False
        w2 = Widget()
        self.assertTrue(w2.restoreGeometryAndLayoutState(state))
        self.assertEqual(w1.geometry(), QRect(51, 52, 53, 54))

        self.assertFalse((w2.restoreGeometryAndLayoutState(QByteArray())))
        self.assertFalse(w2.restoreGeometryAndLayoutState(QByteArray(b'ab')))

    def test_garbage_collect(self):
        widget = MyWidget()
        ref = weakref.ref(widget)
        # insert an object in widget's __dict__ that will be deleted when its
        # __dict__ is cleared.
        widget._finalizer = QObject()
        spyw = DestroyedSignalSpy(widget)
        spyf = DestroyedSignalSpy(widget._finalizer)
        widget.deleteLater()
        del widget
        gc.collect()
        self.assertTrue(len(spyw) == 1 or spyw.wait(1000))
        gc.collect()
        self.assertTrue(len(spyf) == 1 or spyf.wait(1000))
        gc.collect()
        self.assertIsNone(ref())

    def test_garbage_collect_from_scheme(self):
        from orangewidget.workflow.widgetsscheme import WidgetsScheme
        from orangewidget.workflow.discovery import widget_desc_from_module
        new_scheme = WidgetsScheme()
        w_desc = widget_desc_from_module("orangewidget.tests.test_widget")
        node = new_scheme.new_node(w_desc)
        widget = new_scheme.widget_for_node(node)
        widget._finalizer = QObject()
        spyw = DestroyedSignalSpy(widget)
        spyf = DestroyedSignalSpy(widget._finalizer)
        ref = weakref.ref(widget)
        del widget
        new_scheme.remove_node(node)
        gc.collect()
        self.assertTrue(len(spyw) == 1 or spyw.wait(1000))
        gc.collect()
        self.assertTrue(len(spyf) == 1 or spyf.wait(1000))
        self.assertIsNone(ref())

    def _status_bar_visible_test(self, widget):
        # type: (OWBaseWidget) -> None
        # Test that statusBar().setVisible collapses/expands the bottom margins
        sb = widget.statusBar()
        m1 = widget.contentsMargins().bottom()
        sb.setVisible(False)
        m2 = widget.contentsMargins().bottom()
        self.assertLess(m2, m1)
        self.assertEqual(m2, 0)
        sb.setVisible(True)
        m3 = widget.contentsMargins().bottom()
        self.assertEqual(sb.height(), m3)
        self.assertNotEqual(m3, 0)

    def test_status_bar(self):
        # Test that statusBar().setVisible collapses/expands the bottom margins
        w = MyWidget()
        self._status_bar_visible_test(w)
        # run through drawing code (for coverage)
        w.statusBar().grab()

    def test_status_bar_no_basic_layout(self):
        # Test that statusBar() works when widget defines
        # want_basic_layout=False
        with patch.object(MyWidget, "want_basic_layout", False):
            w = MyWidget()
        self._status_bar_visible_test(w)

    def test_status_bar_action(self):
        w = MyWidget()
        action = w.findChild(QAction, "action-show-status-bar")  # type: QAction
        self.assertIsNotNone(action)
        action.setEnabled(True)
        action.setChecked(True)
        self.assertTrue(w.statusBar().isVisibleTo(w))
        action.setChecked(False)
        self.assertFalse(w.statusBar().isVisibleTo(w))
        w.statusBar().hide()
        self.assertFalse(action.isChecked())

    def test_widgets_cant_be_subclassed(self):
        # pylint: disable=unused-variable
        with self.assertWarns(RuntimeWarning):
            class MySubWidget(MyWidget):
                pass

        with patch("warnings.warn") as warn:

            class MyWidget2(OWBaseWidget, openclass=True):
                pass

            class MySubWidget2(MyWidget2):
                pass

            warn.assert_not_called()

    def test_reset_settings(self):
        w = MyWidget()
        w.field = 43
        w._reset_settings()
        self.assertEqual(42, w.field)


class WidgetMsgTestCase(WidgetTest):

    class TestWidget(OWBaseWidget):
        name = "Test"

        class Information(OWBaseWidget.Information):
            hello = Msg("A message")

        def __init__(self):
            super().__init__()

            self.Information.hello()

    @staticmethod
    def active_messages(widget):
        """Return all active messages in a widget"""
        return [m for g in widget.message_groups for m in g.active]

    def test_widget_emits_messages(self):
        """Widget emits messageActivates/messageDeactivated signals"""

        w = WidgetMsgTestCase.TestWidget()
        messages = set(self.active_messages(w))

        self.assertEqual(len(messages), 1, )

        w.messageActivated.connect(messages.add)
        w.messageDeactivated.connect(messages.remove)

        w.Information.hello()
        self.assertEqual(len(messages), 1)
        self.assertSetEqual(messages, set(self.active_messages(w)))

        w.Information.hello.clear()
        self.assertEqual(len(messages), 0)
        self.assertSetEqual(set(self.active_messages(w)), set())

        # OWBaseWidget without a basic layout (completely empty; no default msg bar
        with patch.object(WidgetMsgTestCase.TestWidget,
                          "want_basic_layout", False):
            w = WidgetMsgTestCase.TestWidget()

        messages = set(self.active_messages(w))

        w.messageActivated.connect(messages.add)
        w.messageDeactivated.connect(messages.remove)

        self.assertEqual(len(messages), 1)

        w.Information.hello.clear()
        self.assertEqual(len(messages), 0)

    def test_message_exc_info(self):
        w = WidgetMsgTestCase.TestWidget()
        w.Error.add_message("error")
        messages = set([])
        w.messageActivated.connect(messages.add)
        w.messageDeactivated.connect(messages.remove)
        try:
            _ = 1 / 0
        except ZeroDivisionError:
            w.Error.error("AA", exc_info=True)

        self.assertEqual(len(messages), 1)
        m = list(messages).pop()
        self.assertIsNotNone(m.tb)
        self.assertIn("ZeroDivisionError", m.tb)

        w.Error.error("BB", exc_info=Exception("foobar"))
        self.assertIn("foobar", m.tb)
        w.Error.error("BB")
        self.assertIsNone(m.tb)

    def test_old_style_messages(self):
        w = WidgetMsgTestCase.TestWidget()
        w.Information.clear()

        messages = set(self.active_messages(w))

        w.messageActivated.connect(messages.add)
        w.messageDeactivated.connect(messages.remove)

        with self.assertWarns(UserWarning):
            w.error(1, "A")

        self.assertEqual(len(w.Error.active), 1)
        self.assertEqual(len(messages), 1)

        with self.assertWarns(UserWarning):
            w.error(1)

        self.assertEqual(len(messages), 0)
        self.assertEqual(len(w.Error.active), 0)

        with self.assertWarns(UserWarning):
            w.error(2, "B")
        self.assertEqual(len(messages), 1)

        w.Error.clear()
        self.assertEqual(len(messages), 0)


class TestWidgetStateTracking(WidgetTestCase):
    def test_blocking_state(self):
        w = MyWidget()
        spy = QSignalSpy(w.blockingStateChanged)
        w.setBlocking(True)
        self.assertSequenceEqual(spy, [[True]])
        self.assertTrue(w.isBlocking())
        w.setBlocking(True)
        self.assertSequenceEqual(spy, [[True]])
        spy = QSignalSpy(w.blockingStateChanged)
        w.setBlocking(False)
        self.assertSequenceEqual(spy, [[False]])
        w.setBlocking(False)
        self.assertSequenceEqual(spy, [[False]])
        # Test that setReady, setInvalidate set blocking state as appropriate
        spy = QSignalSpy(w.blockingStateChanged)
        w.setInvalidated(True)
        self.assertSequenceEqual(spy, [])
        w.setReady(False)
        self.assertSequenceEqual(spy, [[True]])
        w.setReady(True)
        self.assertSequenceEqual(spy, [[True], [False]])
        w.setInvalidated(False)
        self.assertSequenceEqual(spy, [[True], [False]])

    def test_invalidated_state(self):
        w = MyWidget()
        spy = QSignalSpy(w.invalidatedStateChanged)
        w.setInvalidated(True)
        self.assertSequenceEqual(spy, [[True]])
        w.setInvalidated(True)
        self.assertSequenceEqual(spy, [[True]])
        spy = QSignalSpy(w.invalidatedStateChanged)
        w.setInvalidated(False)
        self.assertSequenceEqual(spy, [[False]])
        # Test also that setBlocking sets invalidated state
        spy = QSignalSpy(w.invalidatedStateChanged)
        w.setBlocking(True)
        self.assertSequenceEqual(spy, [[True]])
        spy = QSignalSpy(w.invalidatedStateChanged)
        w.setBlocking(False)
        self.assertSequenceEqual(spy, [[False]])

    def test_ready_state(self):
        w = MyWidget()
        spy = QSignalSpy(w.readyStateChanged)
        w.setReady(False)
        self.assertSequenceEqual(spy, [[False]])
        spy = QSignalSpy(w.readyStateChanged)
        w.setReady(True)
        self.assertSequenceEqual(spy, [[True]])
        # Test also that setBlocking sets ready state
        spy = QSignalSpy(w.readyStateChanged)
        w.setBlocking(True)
        self.assertSequenceEqual(spy, [[False]])
        spy = QSignalSpy(w.readyStateChanged)
        w.setBlocking(False)
        self.assertSequenceEqual(spy, [[True]])


class DestroyedSignalSpy(QSignalSpy):
    """
    A signal spy for watching QObject.destroyed signal

    NOTE: This class specifically does not capture the QObject pointer emitted
    from the destroyed signal (i.e. it connects to the no arg overload).
    """
    class Mapper(QObject):
        destroyed_ = pyqtSignal()

    def __init__(self, obj):
        # type: (QObject) -> None
        # Route the signal via a no argument signal to drop the obj pointer.
        # After the destroyed signal is emitted the pointer is invalid
        self.__mapper = DestroyedSignalSpy.Mapper()
        obj.destroyed.connect(self.__mapper.destroyed_)
        super().__init__(self.__mapper.destroyed_)


class WidgetTestInfoSummary(WidgetTest):
    def test_info_set_warn(self):
        test = self

        class TestW(OWBaseWidget):
            name = "a"
            def __init__(self):
                super().__init__()
                with test.assertWarns(DeprecationWarning):
                    self.info = 4
        TestW()

    def test_io_summaries(self):
        w = MyWidget()
        info = w.info  # type: StateInfo
        inmsg = w.findChild(MessagesWidget, "input-summary")  # type: MessagesWidget
        outmsg = w.findChild(MessagesWidget, "output-summary")  # type: MessagesWidget
        self.assertEqual(len(inmsg.messages()), 0)
        self.assertEqual(len(outmsg.messages()), 0)

        w.info.set_input_summary(w.info.NoInput)
        w.info.set_output_summary(w.info.NoOutput)

        self.assertEqual(len(inmsg.messages()), 1)
        self.assertFalse(inmsg.summarize().isEmpty())
        self.assertEqual(len(outmsg.messages()), 1)
        self.assertFalse(outmsg.summarize().isEmpty())

        info.set_input_summary("Foo")

        self.assertEqual(len(inmsg.messages()), 1)
        self.assertEqual(inmsg.summarize().text, "Foo")
        self.assertFalse(inmsg.summarize().icon.isNull())

        info.set_input_summary(12_345)
        info.set_output_summary(1234)

        self.assertEqual(inmsg.summarize().text, "12.3k")
        self.assertEqual(inmsg.summarize().informativeText, "12345")
        self.assertEqual(outmsg.summarize().text, "1234")

        info.set_input_summary("Foo", "A foo that bars",)

        info.set_input_summary(None)
        info.set_output_summary(None)

        self.assertTrue(inmsg.summarize().isEmpty())
        self.assertTrue(outmsg.summarize().isEmpty())

        info.set_output_summary("Foobar", "42")

        self.assertEqual(len(outmsg.messages()), 1)
        self.assertEqual(outmsg.summarize().text, "Foobar")
        self.assertFalse(outmsg.summarize().icon.isNull())

        with self.assertRaises(TypeError):
            info.set_input_summary(None, "a")

        with self.assertRaises(TypeError):
            info.set_input_summary(info.NoInput, "a")

        with self.assertRaises(TypeError):
            info.set_output_summary(None, "a")

        with self.assertRaises(TypeError):
            info.set_output_summary(info.NoOutput, "a")

        info.set_input_summary(1234, "Foo")
        info.set_output_summary(1234, "Bar")

        self.assertEqual(inmsg.summarize().text, "1234")
        self.assertEqual(inmsg.summarize().informativeText, "Foo")
        self.assertEqual(outmsg.summarize().text, "1234")
        self.assertEqual(outmsg.summarize().informativeText, "Bar")

    def test_format_number(self):
        self.assertEqual(StateInfo.format_number(9999), "9999")
        self.assertEqual(StateInfo.format_number(12_345), "12.3k")
        self.assertEqual(StateInfo.format_number(12_000), "12k")
        self.assertEqual(StateInfo.format_number(123_456), "123k")
        self.assertEqual(StateInfo.format_number(99_999), "100k")
        self.assertEqual(StateInfo.format_number(1_234_567), "1.23M")
        self.assertEqual(StateInfo.format_number(999_999), "1M")
        self.assertEqual(StateInfo.format_number(1_000_000), "1M")


if __name__ == "__main__":
    unittest.main()
