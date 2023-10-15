# pylint: disable=protected-access

import gc
import weakref

import unittest
from unittest.mock import patch, MagicMock

from AnyQt.QtCore import Qt, QPoint, QRect, QByteArray, QObject, pyqtSignal
from AnyQt.QtGui import QShowEvent, QKeyEvent
from AnyQt.QtWidgets import QAction, QMenu, QApplication
from AnyQt.QtTest import QSignalSpy, QTest

from orangewidget.gui import OWComponent
from orangewidget.settings import Setting, SettingProvider
from orangewidget.tests.base import WidgetTest
from orangewidget.utils.buttons import SimpleButton
from orangewidget.utils.signals import summarize, PartialSummary
from orangewidget.widget import OWBaseWidget, Msg, StateInfo, Input, Output
from orangewidget.utils.messagewidget import InOutStateWidget


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


class SignalTypeA:
    pass


class SignalTypeB:
    pass


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

    def test_keywords(self):
        class Widget(OWBaseWidget):
            pass

        self.assertEqual(Widget.keywords, [])

        class Widget(OWBaseWidget):
            keywords = ["bar", "qux"]

        self.assertEqual(Widget.keywords, ["bar", "qux"])

        class Widget(OWBaseWidget):
            keywords = "foo bar   baz"

        self.assertEqual(Widget.keywords, ["foo", "bar", "baz"])

        class Widget(OWBaseWidget):
            keywords = "foo bar, baz"

        self.assertEqual(Widget.keywords, ["foo bar", "baz"])

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
        geom = QRect(151, 152, 53, 54)
        geom.setSize(geom.size().expandedTo(w.minimumSize()))
        w.setGeometry(geom)
        state = w.saveGeometryAndLayoutState()
        w1 = Widget()
        self.assertTrue(w1.restoreGeometryAndLayoutState(state))
        self.assertEqual(w1.geometry(), geom)
        self.assertFalse(w1.controlAreaVisible)

        Widget.want_control_area = False
        w2 = Widget()
        self.assertTrue(w2.restoreGeometryAndLayoutState(state))
        self.assertEqual(w1.geometry(), geom)

        self.assertFalse((w2.restoreGeometryAndLayoutState(QByteArray())))
        self.assertFalse(w2.restoreGeometryAndLayoutState(QByteArray(b'ab')))

    def test_resizing_disabled_width_hint(self):
        class TestWidget(OWBaseWidget):
            name = "Test"
            resizing_enabled = False
            want_main_area = True
        w = TestWidget()
        w._OWBaseWidget__setControlAreaVisible(False)
        sm1 = w.maximumSize()
        w._OWBaseWidget__setControlAreaVisible(True)
        sm2 = w.maximumSize()
        self.assertLess(sm1.width() + 30, sm2.width())

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


class TestWidgetStateTracking(WidgetTest):
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
        inmsg: InOutStateWidget = w.findChild(InOutStateWidget, "input-summary")
        outmsg: InOutStateWidget = w.findChild(InOutStateWidget, "output-summary")
        self.assertFalse(inmsg.message)
        self.assertFalse(outmsg.message)

        w.info.set_input_summary(w.info.NoInput)
        w.info.set_output_summary(w.info.NoOutput)
        self.assertTrue(inmsg.message.text)
        self.assertTrue(outmsg.message.text)

        info.set_input_summary("Foo")

        self.assertTrue(inmsg.message)
        self.assertEqual(inmsg.message.text, "Foo")

        info.set_input_summary(12_345)
        info.set_output_summary(1234)

        self.assertEqual(inmsg.message.text, "12.3k")
        self.assertEqual(inmsg.message.informativeText, "12345")
        self.assertEqual(outmsg.message.text, "1234")

        info.set_input_summary("Foo", "A foo that bars",)

        info.set_input_summary(None)
        info.set_output_summary(None)

        self.assertFalse(inmsg.message.text)
        self.assertFalse(outmsg.message.text)

        info.set_output_summary("Foobar", "42")

        self.assertTrue(outmsg.message)
        self.assertEqual(outmsg.message.text, "Foobar")

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

        self.assertEqual(inmsg.message.text, "1234")
        self.assertEqual(inmsg.message.informativeText, "Foo")
        self.assertEqual(outmsg.message.text, "1234")
        self.assertEqual(outmsg.message.informativeText, "Bar")

    def test_info_no_basic_layout(self):
        with patch.object(MyWidget, "want_basic_layout", False):
            w = MyWidget()

        w.info.set_input_summary(w.info.NoInput)
        inmsg = w.findChild(InOutStateWidget, "input-summary")  # type: InOutStateWidget
        self.assertTrue(inmsg.isVisibleTo(w))
        self.assertTrue(inmsg.message)

    def test_format_number(self):
        self.assertEqual(StateInfo.format_number(9999), "9999")
        self.assertEqual(StateInfo.format_number(12_345), "12.3k")
        self.assertEqual(StateInfo.format_number(12_000), "12k")
        self.assertEqual(StateInfo.format_number(123_456), "123k")
        self.assertEqual(StateInfo.format_number(99_999), "100k")
        self.assertEqual(StateInfo.format_number(1_234_567), "1.23M")
        self.assertEqual(StateInfo.format_number(999_999), "1M")
        self.assertEqual(StateInfo.format_number(1_000_000), "1M")

    def test_overriden_handler(self):
        class TestWidget(OWBaseWidget, openclass=True):
            class Inputs(OWBaseWidget.Inputs):
                inputA = Input("a", SignalTypeA)

            @Inputs.inputA
            def handler(self, _):
                pass

        class DerivedWidget(TestWidget):
            name = "tw"

            @TestWidget.Inputs.inputA
            def handler(self, obj):
                super().handler(obj)

        widget = self.create_widget(DerivedWidget)
        widget.set_partial_input_summary = MagicMock()
        self.send_signal(widget.Inputs.inputA, SignalTypeA())
        widget.set_partial_input_summary.assert_called_once()


@summarize.register(SignalTypeA)
def summarize(_: SignalTypeA):
    return PartialSummary("foo", "bar")


class AutoSummarizeTest(WidgetTest):
    @patch("orangewidget.widget.OWBaseWidget._check_input_handlers")
    def test_auto_summarize_default(self, _):
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Inputs(OWBaseWidget.Inputs):
                    inputA1 = Input("a1", SignalTypeA)
                    inputA2 = Input("a2", SignalTypeA, auto_summary=True)
                    inputA3 = Input("a3", SignalTypeA, auto_summary=False)

                class Outputs(OWBaseWidget.Inputs):
                    outputA1 = Output("a", SignalTypeA)
                    outputA2 = Output("b", SignalTypeA, auto_summary=True)
                    outputA3 = Output("c", SignalTypeA, auto_summary=False)

            self.assertTrue(TestWidget.Inputs.inputA1.auto_summary)
            self.assertTrue(TestWidget.Inputs.inputA2.auto_summary)
            self.assertFalse(TestWidget.Inputs.inputA3.auto_summary)

            self.assertTrue(TestWidget.Outputs.outputA1.auto_summary)
            self.assertTrue(TestWidget.Outputs.outputA2.auto_summary)
            self.assertFalse(TestWidget.Outputs.outputA3.auto_summary)

    @patch("orangewidget.widget.OWBaseWidget._check_input_handlers")
    def test_warning_no_summarizer(self, _):
        with self.assertWarns(UserWarning):
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Inputs(OWBaseWidget.Inputs):
                    inputB = Input("b", SignalTypeB)

            self.assertFalse(TestWidget.Inputs.inputB.auto_summary)

        with self.assertWarns(UserWarning):
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Outputs(OWBaseWidget.Inputs):
                    outputB = Output("b", SignalTypeB)

            self.assertFalse(TestWidget.Outputs.outputB.auto_summary)

        with patch("warnings.warn") as warn:
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Inputs(OWBaseWidget.Inputs):
                    inputB = Input("b", SignalTypeB, auto_summary=True)

                class Outputs(OWBaseWidget.Inputs):
                    outputB = Output("b", SignalTypeB, auto_summary=False)

            warn.assert_not_called()
            self.assertTrue(TestWidget.Inputs.inputB.auto_summary)
            self.assertFalse(TestWidget.Outputs.outputB.auto_summary)

    @patch("orangewidget.widget.OWBaseWidget._check_input_handlers")
    def test_signal_as_qualified_name(self, _):
        with self.assertWarns(UserWarning):
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Inputs(OWBaseWidget.Inputs):
                    inputA = Input(
                        "a", "orangewidget.tests.test_widget.SignalTypeA")

            self.assertFalse(TestWidget.Inputs.inputA.auto_summary)

        with patch("warnings.warn") as warn:
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Inputs(OWBaseWidget.Inputs):
                    inputA = Input(
                        "a", "orangewidget.tests.test_widget.SignalTypeA",
                        auto_summary=False)

            warn.assert_not_called()
            self.assertFalse(TestWidget.Inputs.inputA.auto_summary)

        with patch("warnings.warn") as warn:
            class TestWidget(OWBaseWidget):
                name = "tw"

                class Inputs(OWBaseWidget.Inputs):
                    inputA = Input(
                        "a", "orangewidget.tests.test_widget.SignalTypeA",
                        auto_summary=True)

            warn.assert_not_called()
            self.assertTrue(TestWidget.Inputs.inputA.auto_summary)


class TestSignals(WidgetTest):
    @patch("orangewidget.widget.OWBaseWidget._check_input_handlers")
    @patch("orangewidget.utils.signals.can_summarize")
    def test_assign_ids(self, *_):
        class TestWidget(OWBaseWidget):
            class Inputs(OWBaseWidget.Inputs):
                inputA = Input("a", int)
                inputB = Input("b", int, id="c")

            class Outputs(OWBaseWidget.Outputs):
                outputA = Output("a", int)
                outputB = Output("b", int, id="c")

        self.assertEqual(TestWidget.Inputs.inputA.id, "inputA")
        self.assertEqual(TestWidget.Inputs.inputB.id, "c")

        self.assertEqual(TestWidget.Outputs.outputA.id, "outputA")
        self.assertEqual(TestWidget.Outputs.outputB.id, "c")

    @patch("orangewidget.widget.OWBaseWidget._check_input_handlers")
    @patch("orangewidget.utils.signals.can_summarize")
    def test_prevent_same_name_id(self, *_):
        with self.assertRaises(RuntimeError):
            class TestWidget(OWBaseWidget):
                class Inputs(OWBaseWidget.Inputs):
                    inputA = Input("a", int, id="c")
                    inputB = Input("b", int, id="c")

        with self.assertRaises(RuntimeError):
            class TestWidget(OWBaseWidget):
                class Inputs(OWBaseWidget.Inputs):
                    inputA = Input("a", int)
                    inputB = Input("a", int)

        with self.assertRaises(RuntimeError):
            class TestWidget(OWBaseWidget):
                class Outputs(OWBaseWidget.Outputs):
                    outputA = Output("a", int)
                    outputB = Output("b", int, id="outputA")

        with self.assertRaises(RuntimeError):
            class TestWidget(OWBaseWidget):
                inputs = [("name 1", int, "foo", 0, "x"),
                          Input("name 2", int, id="x")]

                def foo(self):
                    pass

        with self.assertWarns(UserWarning):
            class TestWidget(OWBaseWidget):
                class Outputs(OWBaseWidget.Outputs):
                    outputA = Output("a", int)
                    outputB = Output("b", int, id="a")

        class TestWidget(OWBaseWidget):
            class Inputs(OWBaseWidget.Inputs):
                inputA = Input("a", int, id="x")

            class Outputs(OWBaseWidget.Outputs):
                outputA = Output("a", int, id="x")

        class TestWidget(OWBaseWidget):
            inputs = [("name 1", int, "foo"), Input("name 2", int, "foo")]

            def foo(self):
                pass


class TestWidgetMenu(WidgetTest):
    def test_menu(self):
        class Widget(OWBaseWidget):
            def __init__(self):
                super().__init__()
                menubar = self.menuBar()
                test = menubar.addMenu("Test")
                test.addAction("Test")

        w = self.create_widget(Widget)
        mb = w.menuBar()
        native = mb.isNativeMenuBar()
        if native:
            self.skipTest("Native menu bar in use")
        sb = w.statusBar()
        button = sb.findChild(SimpleButton, "status-bar-menu-button")
        with patch.object(QMenu, "popup") as popup:
            button.click()
            QTest.qWait(0)
            popup.assert_called_once()
            # close the menu
            menu = QApplication.activePopupWidget()
            if menu is not None:
                menu.close()

        # Simulate show menu bar on Alt key press
        QTest.keyPress(w, Qt.Key_Alt, Qt.NoModifier)
        timer = w._OWBaseWidget__menubar_visible_timer
        self.assertTrue(timer.isActive())
        spy = QSignalSpy(timer.timeout)
        spy.wait()
        self.assertTrue(mb.isVisibleTo(w))
        QTest.keyRelease(w, Qt.Key_Alt, Qt.NoModifier)
        self.assertFalse(mb.isVisibleTo(w))


class MetaClassTest(WidgetTest):
    @patch("AnyQt.QtWidgets.QDialog.eventFilter")
    def test_eventFilter(self, eventFilter):
        class NoFilter(OWBaseWidget):
            pass

        class HasFilter(OWBaseWidget):
            def __init__(self):
                self.myprop = 42

            def eventFilter(self, *args ,**kwargs):
                super().eventFilter(*args, **kwargs)
                self.myprop += 1  # will crash on empty dict

        nf = NoFilter()
        nf.eventFilter()
        eventFilter.assert_called()
        eventFilter.reset_mock()

        hf = HasFilter()
        hf.eventFilter()
        self.assertEqual(hf.myprop, 43)
        eventFilter.assert_called()
        eventFilter.reset_mock()

        hf.__dict__.clear()
        hf.eventFilter()
        eventFilter.assert_called()
        eventFilter.reset_mock()


if __name__ == "__main__":
    unittest.main()
