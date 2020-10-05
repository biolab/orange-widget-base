import unittest
from unittest.mock import Mock

from AnyQt.QtWidgets import QComboBox, QCheckBox, QSpinBox, QLineEdit

from orangewidget.tests.base import GuiTest
from orangewidget.utils.visual_settings_dlg import SettingsDialog, FontList


class TestSettingsDialog(GuiTest):
    def setUp(self):
        self.defaults = {
            "Box": {"Items": {
                "P1": (["Foo", "Bar", "Baz"], "Bar"),
                "P2": (range(3, 10, 2), 5),
                "P3": (None, True),
                "P4": (None, "Foo Bar"),
                "P5": (FontList([".Foo", ".Bar"]), ".Foo"),
            }}
        }
        self.dlg = SettingsDialog(None, self.defaults)

    @property
    def dialog_controls(self):
        return self.dlg._SettingsDialog__controls

    def test_initialize(self):
        controls = self.dialog_controls
        self.assertEqual(len(controls), len(self.defaults["Box"]["Items"]))
        self.assertIsInstance(controls[("Box", "Items", "P1")][0], QComboBox)
        self.assertIsInstance(controls[("Box", "Items", "P2")][0], QSpinBox)
        self.assertIsInstance(controls[("Box", "Items", "P3")][0], QCheckBox)
        self.assertIsInstance(controls[("Box", "Items", "P4")][0], QLineEdit)
        self.assertIsInstance(controls[("Box", "Items", "P5")][0], QComboBox)

    def test_changed_settings(self):
        self.dialog_controls[("Box", "Items", "P1")][0].setCurrentText("Foo")
        self.dialog_controls[("Box", "Items", "P2")][0].setValue(7)
        self.dialog_controls[("Box", "Items", "P3")][0].setChecked(False)
        self.dialog_controls[("Box", "Items", "P4")][0].setText("Foo Baz")
        self.dialog_controls[("Box", "Items", "P5")][0].setCurrentIndex(1)
        changed = {("Box", "Items", "P1"): "Foo",
                   ("Box", "Items", "P2"): 7,
                   ("Box", "Items", "P3"): False,
                   ("Box", "Items", "P4"): "Foo Baz",
                   ("Box", "Items", "P5"): ".Bar"}
        self.assertDictEqual(self.dlg.changed_settings, changed)

    def test_reset(self):
        ctrls = self.dialog_controls
        ctrls[("Box", "Items", "P1")][0].setCurrentText("Foo")
        ctrls[("Box", "Items", "P2")][0].setValue(7)
        ctrls[("Box", "Items", "P3")][0].setChecked(False)
        ctrls[("Box", "Items", "P4")][0].setText("Foo Baz")
        self.dialog_controls[("Box", "Items", "P5")][0].setCurrentIndex(1)

        self.dlg._SettingsDialog__reset()
        self.assertDictEqual(self.dlg.changed_settings, {})
        self.assertEqual(ctrls[("Box", "Items", "P1")][0].currentText(), "Bar")
        self.assertEqual(ctrls[("Box", "Items", "P2")][0].value(), 5)
        self.assertTrue(ctrls[("Box", "Items", "P3")][0].isChecked())
        self.assertEqual(ctrls[("Box", "Items", "P4")][0].text(), "Foo Bar")
        self.assertEqual(ctrls[("Box", "Items", "P5")][0].currentText(), "Foo")

    def test_setting_changed(self):
        handler = Mock()
        self.dlg.setting_changed.connect(handler)
        self.dialog_controls[("Box", "Items", "P1")][0].setCurrentText("Foo")
        handler.assert_called_with(('Box', 'Items', 'P1'), "Foo")
        self.dialog_controls[("Box", "Items", "P2")][0].setValue(7)
        handler.assert_called_with(('Box', 'Items', 'P2'), 7)
        self.dialog_controls[("Box", "Items", "P3")][0].setChecked(False)
        handler.assert_called_with(('Box', 'Items', 'P3'), False)
        self.dialog_controls[("Box", "Items", "P4")][0].setText("Foo Baz")
        handler.assert_called_with(('Box', 'Items', 'P4'), "Foo Baz")
        self.dialog_controls[("Box", "Items", "P5")][0].setCurrentIndex(1)
        handler.assert_called_with(('Box', 'Items', 'P5'), ".Bar")

    def test_apply_settings(self):
        changed = [(("Box", "Items", "P1"), "Foo"),
                   (("Box", "Items", "P2"), 7),
                   (("Box", "Items", "P3"), False),
                   (("Box", "Items", "P4"), "Foo Baz"),
                   (("Box", "Items", "P5"), ".Bar")]
        self.dlg.apply_settings(changed)
        ctrls = self.dialog_controls
        self.assertEqual(ctrls[("Box", "Items", "P1")][0].currentText(), "Foo")
        self.assertEqual(ctrls[("Box", "Items", "P2")][0].value(), 7)
        self.assertFalse(ctrls[("Box", "Items", "P3")][0].isChecked())
        self.assertEqual(ctrls[("Box", "Items", "P4")][0].text(), "Foo Baz")
        self.assertEqual(ctrls[("Box", "Items", "P5")][0].currentText(), "Bar")
        self.assertDictEqual(self.dlg.changed_settings,
                             {k: v for k, v in changed})


if __name__ == '__main__':
    unittest.main()
