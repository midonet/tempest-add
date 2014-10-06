#!/usr/bin/env python

import os
import sys
from lxml import etree


"""
Merge multiple JUnit XML files into a single results file.
Assumes that xml files are the result of sequencially
running the previous failing tests

Output dumps to sdtdout.

example usage:
    $ python midokura/utils/merge_xml_results.py file1.xml file2.xml ... filen.xml > results-merged.xml"
"""

if __name__ == '__main__':
    files = sys.argv[1:]
    if not files:
        print "Usage: merge_xml_results.py file1.xml file2.xml ... filen.xml > results-merged.xml"
        sys.exit(1)

    tests = 0
    failures = 10000000
    errors = 10000000
    time = 0.0
    cases = dict()

    for f in files:
        tree = etree.parse(f)
        test_suite = tree.getroot()
        tests = max(int(test_suite.attrib['tests']), tests)
        failures = min(int(test_suite.attrib['failures']), failures)
        errors = min(int(test_suite.attrib['errors']), errors)
        time = max(float(test_suite.attrib['time']), time)
        test_cases = test_suite.getchildren()
        for case in test_cases:
            cases[case.attrib['classname']+'.'+case.attrib['name']] = case

    new_root = etree.Element('testsuite')
    new_root.attrib['tests'] = '%s' % tests
    new_root.attrib['failures'] = '%s' % failures
    new_root.attrib['errors'] = '%s' % errors
    new_root.attrib['time'] = '%s' % time
    for case_name in sorted(cases.keys()):
        new_root.append(cases[case_name])
    new_tree = etree.ElementTree(new_root)
    etree.dump(new_root)

