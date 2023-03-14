import unittest
from unittest.mock import Mock, patch

from orangewidget.tests.base import GuiTest


class SkipTest(Exception):
    pass


class TestGuiTest(unittest.TestCase):
    @patch("unittest.case.SkipTest", SkipTest)
    def test_english(self):
        class TestA(GuiTest):
            pure_test = Mock()
            test = GuiTest.skipNonEnglish(pure_test)

            pure_test_si = Mock()
            test_si = GuiTest.runOnLanguage("Slovenian")(pure_test_si)

        test_obj = TestA()

        test_obj.test()
        test_obj.pure_test.assert_called()

        self.assertRaises(SkipTest, test_obj.test_si)
        test_obj.pure_test_si.assert_not_called()

    @patch("unittest.case.SkipTest", SkipTest)
    @patch("orangewidget.tests.base.GuiTest.LANGUAGE", "Slovenian")
    def test_non_english(self):
        class TestA(GuiTest):
            pure_test = Mock()
            test = GuiTest.skipNonEnglish(pure_test)

            pure_test_si = Mock()
            test_si = GuiTest.runOnLanguage("Slovenian")(pure_test_si)

            pure_test_fr = Mock()
            test_fr = GuiTest.runOnLanguage("French")(pure_test_fr)

        test_obj = TestA()

        self.assertRaises(SkipTest, test_obj.test)
        test_obj.pure_test.assert_not_called()

        test_obj.test_si()
        test_obj.pure_test_si.assert_called()

        self.assertRaises(SkipTest, test_obj.test_fr)
        test_obj.pure_test_fr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
