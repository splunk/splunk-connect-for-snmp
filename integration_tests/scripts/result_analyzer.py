from junitparser import JUnitXml


xml = JUnitXml.fromfile('./result.xml')

for suite in xml:
    assert suite.tests > 0, "Suite does not contain any tests"
    assert suite.errors == 0, "Some errors detected in test results"
    assert suite.failures == 0, "Some failures detected in test results"
    assert suite.skipped == 0, "Some tests were skipped"

print("All tests PASSED")
