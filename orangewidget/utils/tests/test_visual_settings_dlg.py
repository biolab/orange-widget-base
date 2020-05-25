import unittest
from unittest.mock import Mock
from collections import OrderedDict

from AnyQt.QtWidgets import QComboBox, QCheckBox, QSpinBox

from orangewidget.tests.base import GuiTest
from orangewidget.utils.visual_settings_dlg import VisualSettingsDialog


class TestVisualSettingsDialog(GuiTest):
    def setUp(self):
        self.defaults = {
            "Box": {"Items": OrderedDict({
                "P1": (["Foo", "Bar", "Baz"], "Bar"),
                "P2": (range(3, 10, 2), 5),
                "P3": (None, True),
            })}
        }
        self.dlg = VisualSettingsDialog(None)
        self.dlg.initialize(self.defaults)

    @property
    def dialog_controls(self):
        return self.dlg._VisualSettingsDialog__controls

    def test_initialize(self):
        controls = self.dialog_controls
        self.assertEqual(len(controls), len(self.defaults["Box"]["Items"]))
        self.assertIsInstance(controls[("Box", "Items", "P1")][0], QComboBox)
        self.assertIsInstance(controls[("Box", "Items", "P2")][0], QSpinBox)
        self.assertIsInstance(controls[("Box", "Items", "P3")][0], QCheckBox)

    def test_changed_settings(self):
        self.dialog_controls[("Box", "Items", "P1")][0].setCurrentText("Foo")
        self.dialog_controls[("Box", "Items", "P2")][0].setValue(7)
        self.dialog_controls[("Box", "Items", "P3")][0].setChecked(False)
        changed = {("Box", "Items", "P1"): "Foo",
                   ("Box", "Items", "P2"): 7,
                   ("Box", "Items", "P3"): False}
        self.assertDictEqual(self.dlg.changed_settings, changed)

    def test_reset(self):
        ctrls = self.dialog_controls
        ctrls[("Box", "Items", "P1")][0].setCurrentText("Foo")
        ctrls[("Box", "Items", "P2")][0].setValue(7)
        ctrls[("Box", "Items", "P3")][0].setChecked(False)

        self.dlg._VisualSettingsDialog__reset()
        self.assertDictEqual(self.dlg.changed_settings, {})
        self.assertEqual(ctrls[("Box", "Items", "P1")][0].currentText(), "Bar")
        self.assertEqual(ctrls[("Box", "Items", "P2")][0].value(), 5)
        self.assertTrue(ctrls[("Box", "Items", "P3")][0].isChecked())

    def test_setting_changed(self):
        handler = Mock()
        self.dlg.setting_changed.connect(handler)
        self.dialog_controls[("Box", "Items", "P1")][0].setCurrentText("Foo")
        handler.assert_called_with(('Box', 'Items', 'P1'), "Foo")
        self.dialog_controls[("Box", "Items", "P2")][0].setValue(7)
        handler.assert_called_with(('Box', 'Items', 'P2'), 7)
        self.dialog_controls[("Box", "Items", "P3")][0].setChecked(False)
        handler.assert_called_with(('Box', 'Items', 'P3'), False)


if __name__ == '__main__':
    unittest.main()
