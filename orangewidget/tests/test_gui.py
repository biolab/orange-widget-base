from AnyQt.QtCore import Qt

from orangewidget import gui
from orangewidget.tests.base import GuiTest
from orangewidget.widget import OWWidget


class TestDoubleSpin(GuiTest):
    # make sure that the gui element does not crash when
    # 'checked' parameter is forwarded, ie. is not None
    def test_checked_extension(self):
        widget = OWWidget()
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
