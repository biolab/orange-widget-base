from AnyQt.QtGui import QFocusEvent
from AnyQt.QtWidgets import QStyle, QApplication
from orangewidget.tests.base import GuiTest
from orangewidget.utils import buttons


class SimpleButtonTest(GuiTest):
    def test_button(self):
        # Run through various state change and drawing code for coverage
        b = buttons.SimpleButton()
        b.setIcon(b.style().standardIcon(QStyle.SP_ComputerIcon))

        QApplication.sendEvent(b, QFocusEvent(QFocusEvent.FocusIn))
        QApplication.sendEvent(b, QFocusEvent(QFocusEvent.FocusOut))

        b.grab()
        b.setDown(True)
        b.grab()
        b.setCheckable(True)
        b.setChecked(True)
        b.grab()


class TestVariableTextPushButton(GuiTest):
    def test_button(self):
        b = buttons.VariableTextPushButton(
            textChoiceList=["", "A", "MMMMMMM"]
        )
        b.setText("")
        sh = b.sizeHint()
        b.setText("A")
        self.assertEqual(b.sizeHint(), sh)
        b.setText("MMMMMMM")
        self.assertEqual(b.sizeHint(), sh)
        b.setTextChoiceList(["A", "B", "C"])


class TestApplyButton(GuiTest):
    def test_button(self):
        b = buttons.ApplyButton(text="Apply", textChoiceList=["Apply", "Auto"])
        b.grab()
        b.sizeHint()
        b.setModified(True)
        b.grab()
        b.setModified(False)
        b.grab()
