from unittest.mock import Mock

from AnyQt.QtCore import Qt, QTimer

from orangewidget import gui
from orangewidget.tests.base import GuiTest, WidgetTest
from orangewidget.widget import OWBaseWidget


class TestDoubleSpin(GuiTest):
    # make sure that the gui element does not crash when
    # 'checked' parameter is forwarded, ie. is not None
    def test_checked_extension(self):
        widget = OWBaseWidget()
        widget.some_param = 0
        widget.some_option = False
        gui.doubleSpin(widget=widget, master=widget, value="some_param",
                       minv=1, maxv=10, checked="some_option")


class TestFloatSlider(GuiTest):

    def test_set_value(self):
        w = gui.FloatSlider(Qt.Horizontal, 0., 1., 0.5)
        w.setValue(1)
        # Float slider returns value divided by step
        # 1/0.5 = 2
        self.assertEqual(w.value(), 2)
        w = gui.FloatSlider(Qt.Horizontal, 0., 1., 0.05)
        w.setValue(1)
        # 1/0.05 = 20
        self.assertEqual(w.value(), 20)


class TestDelayedNotification(WidgetTest):

    def test_immediate(self):
        dn = gui.DelayedNotification(timeout=5000)
        call = Mock()
        dn.notification.connect(call)
        dn.notify_immediately()
        self.process_events(lambda: call.call_args is not None, timeout=1)

    def test_notify_eventually(self):
        dn = gui.DelayedNotification(timeout=500)
        call = Mock()
        dn.notification.connect(call)
        dn.changed()
        self.process_events(lambda: True, timeout=1)
        self.assertIsNone(call.call_args)  # no immediate notification
        self.process_events(lambda: call.call_args is not None)

    def test_delay_by_change(self):
        dn = gui.DelayedNotification(timeout=500)
        call = Mock()
        dn.notification.connect(call)
        timer = QTimer()
        timer.timeout.connect(dn.changed)
        timer.start(100)
        dn.changed()
        # notification should never be emitted as the input changes too fast
        with self.assertRaises(TimeoutError):
            self.process_events(lambda: call.call_args is not None, timeout=1000)

    def test_no_notification_on_no_change(self):
        dn = gui.DelayedNotification(timeout=500)
        call = Mock()
        dn.notification.connect(call)
        dn.changed(42)
        dn.notify_immediately()  # only for faster test
        self.process_events(lambda: call.call_args is not None)  # wait for the first call
        dn.changed(43)
        dn.changed(42)
        # notification should not be called again
        with self.assertRaises(TimeoutError):
            self.process_events(lambda: len(call.call_args_list) > 1, timeout=1000)


class TestCheckBoxWithDisabledState(GuiTest):
    def test_check_checkbox_disable_false(self):
        widget = OWBaseWidget()
        widget.some_option = False
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=False)
        self.assertFalse(cb.isChecked())
        cb.setEnabled(False)
        self.assertFalse(cb.isChecked())
        widget.some_option = True
        self.assertFalse(cb.isChecked())
        cb.setEnabled(True)
        self.assertTrue(cb.isChecked())
        widget.some_option = False
        self.assertFalse(cb.isChecked())

        cb.setDisabled(True)
        self.assertFalse(cb.isChecked())
        widget.some_option = True
        self.assertFalse(cb.isChecked())
        cb.setDisabled(False)
        self.assertTrue(cb.isChecked())
        widget.some_option = False
        self.assertFalse(cb.isChecked())

    def test_check_checkbox_disable_true(self):
        widget = OWBaseWidget()
        widget.some_option = False
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=True)
        self.assertFalse(cb.isChecked())
        cb.setEnabled(False)
        self.assertTrue(cb.isChecked())
        widget.some_option = True
        self.assertTrue(cb.isChecked())
        cb.setEnabled(True)
        self.assertTrue(cb.isChecked())
        widget.some_option = False
        self.assertFalse(cb.isChecked())

        cb.setDisabled(True)
        self.assertTrue(cb.isChecked())
        widget.some_option = True
        self.assertTrue(cb.isChecked())
        cb.setDisabled(False)
        self.assertTrue(cb.isChecked())
        widget.some_option = False
        self.assertFalse(cb.isChecked())

    def test_clicks(self):
        widget = OWBaseWidget()
        widget.some_option = False
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=False)
        cb.clicked.emit(True)
        cb.setEnabled(False)
        cb.setEnabled(True)
        self.assertTrue(cb.isChecked())

    def test_set_checked(self):
        widget = OWBaseWidget()

        widget.some_option = False
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=False)
        self.assertFalse(cb.isChecked())
        cb.setEnabled(False)
        cb.setChecked(True)
        self.assertFalse(cb.isChecked())
        cb.setEnabled(True)
        self.assertTrue(cb.isChecked())

        widget.some_option = True
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=True)
        self.assertTrue(cb.isChecked())
        cb.setEnabled(False)
        cb.setChecked(False)
        self.assertTrue(cb.isChecked())
        cb.setEnabled(True)
        self.assertFalse(cb.isChecked())

    def test_set_check_state(self):
        widget = OWBaseWidget()

        widget.some_option = 0
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=Qt.Unchecked)
        cb.setCheckState(Qt.Unchecked)
        cb.setEnabled(False)
        self.assertEqual(cb.checkState(), Qt.Unchecked)

        cb.setCheckState(Qt.PartiallyChecked)
        self.assertEqual(cb.checkState(), Qt.Unchecked)
        cb.setEnabled(True)
        self.assertEqual(cb.checkState(), Qt.PartiallyChecked)
        cb.setEnabled(False)
        self.assertEqual(cb.checkState(), Qt.Unchecked)

        cb.setCheckState(Qt.Checked)
        self.assertEqual(cb.checkState(), Qt.Unchecked)
        cb.setEnabled(True)
        self.assertEqual(cb.checkState(), Qt.Checked)
        cb.setEnabled(False)
        self.assertEqual(cb.checkState(), Qt.Unchecked)

        widget.some_option = 2
        cb = gui.checkBox(widget, widget, "some_option", "foo",
                          stateWhenDisabled=Qt.PartiallyChecked)
        cb.setCheckState(Qt.Unchecked)
        cb.setEnabled(False)
        self.assertEqual(cb.checkState(), Qt.PartiallyChecked)

        cb.setCheckState(Qt.Unchecked)
        self.assertEqual(cb.checkState(), Qt.PartiallyChecked)
        cb.setEnabled(True)
        self.assertEqual(cb.checkState(), Qt.Unchecked)
        cb.setEnabled(False)
        self.assertEqual(cb.checkState(), Qt.PartiallyChecked)

        cb.setCheckState(Qt.Checked)
        self.assertEqual(cb.checkState(), Qt.PartiallyChecked)
        cb.setEnabled(True)
        self.assertEqual(cb.checkState(), Qt.Checked)
        cb.setEnabled(False)
        self.assertEqual(cb.checkState(), Qt.PartiallyChecked)
