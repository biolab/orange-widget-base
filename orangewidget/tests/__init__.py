import os
import unittest


def load_tests(loader, tests, pattern):
    # Need to guard against inf. recursion. This package will be found again
    # within the discovery process.
    if getattr(load_tests, "_in_load_tests", False):
        return unittest.TestSuite([])

    widget_tests_dir = os.path.dirname(__file__)

    if loader is None:
        loader = unittest.TestLoader()
    if pattern is None:
        pattern = 'test*.py'

    load_tests._in_load_tests = True
    try:
        all_tests = [
            loader.discover(widget_tests_dir, pattern, widget_tests_dir),
        ]
    finally:
        load_tests._in_load_tests = False

    return unittest.TestSuite(all_tests)
