#!/usr/bin/env python3
"""
Test runner script for Shabbat poster generation tests.

This script discovers and runs all unit tests in the tests/ directory.
It uses Python's built-in unittest framework for compatibility.

Usage:
    python run_tests.py                  # Run all tests
    python run_tests.py -v               # Run with verbose output
    python run_tests.py tests.test_core  # Run specific test module
"""

import sys
import unittest
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def run_all_tests(verbosity=2):
    """Discover and run all tests in the tests/ directory."""
    # Discover all tests
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Return exit code (0 for success, 1 for failure)
    return 0 if result.wasSuccessful() else 1


def run_specific_tests(test_pattern, verbosity=2):
    """Run specific tests matching the pattern."""
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern=f'{test_pattern}*.py')
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    # Parse command line arguments
    verbosity = 2
    test_pattern = None
    
    args = sys.argv[1:]
    for arg in args:
        if arg == '-v' or arg == '--verbose':
            verbosity = 2
        elif arg == '-q' or arg == '--quiet':
            verbosity = 1
        elif not arg.startswith('-'):
            test_pattern = arg
    
    print("=" * 70)
    print("Shabbat Poster Generation - Unit Tests")
    print("=" * 70)
    print()
    
    if test_pattern:
        print(f"Running tests matching: {test_pattern}")
        exit_code = run_specific_tests(test_pattern, verbosity)
    else:
        print("Running all tests...")
        exit_code = run_all_tests(verbosity)
    
    print()
    print("=" * 70)
    if exit_code == 0:
        print("All tests passed!")
    else:
        print("Some tests failed.")
    print("=" * 70)
    
    sys.exit(exit_code)

