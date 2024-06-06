import unittest

from orangewidget.tests.base import WidgetTest
from orangewidget.widget import OWBaseWidget, Msg


class TestMessages(WidgetTest):
    def test_clear_owner(self):
        class WidgetA(OWBaseWidget, openclass=True):
            class Error(OWBaseWidget.Error):
                err_a = Msg("error a")

        class WidgetB(WidgetA):
            class Error(WidgetA.Error):
                err_b = Msg("error b")

        w = self.create_widget(WidgetB)
        w.Error.err_a()
        w.Error.err_b()
        self.assertTrue(w.Error.err_a.is_shown())
        self.assertTrue(w.Error.err_b.is_shown())
        w.Error.clear()
        self.assertFalse(w.Error.err_a.is_shown())
        self.assertFalse(w.Error.err_b.is_shown())

        w.Error.err_a()
        w.Error.err_b()
        w.Error.clear(owner=WidgetB)
        self.assertTrue(w.Error.err_a.is_shown())
        self.assertFalse(w.Error.err_b.is_shown())

        w.Error.err_a()
        w.Error.err_b()
        w.Error.clear(owner=WidgetA)
        self.assertFalse(w.Error.err_a.is_shown())
        self.assertTrue(w.Error.err_b.is_shown())

    def test_numpy_class_attributes(self):
        # There used to be a bug where numpy class attributes crash message
        # binding it expected them to have __eq__ method (see other changes in
        # this commit). This test is to make sure the problem doesn't resurface.
        class Neq:
            def __eq__(self, other):
                raise NotImplementedError

        class WidgetA(OWBaseWidget, openclass=True):
            a = Neq()

        self.create_widget(WidgetA)


if __name__ == "__main__":
    unittest.main()
