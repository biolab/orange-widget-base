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


if __name__ == "__main__":
    unittest.main()
