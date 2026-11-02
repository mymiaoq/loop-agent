import unittest
from docloop.evidence import validate_evidence
from docloop.governance import GateError


def evidence(result='passed'):
    return {'producer': 'verify-agent', 'commit': 'a' * 40, 'checks': [
        {'id': 'V-001', 'test_case_id': 'TC-001', 'requirement_ids': ['AC-001'],
         'result': result, 'command_or_method': 'controlled check', 'observed': 'actual value',
         'evidence': 'logs/V-001.txt'}]}


class EvidenceTests(unittest.TestCase):
    def test_missing_coverage_or_non_pass_cannot_verify(self):
        for result in ('failed', 'blocked', 'not_run'):
            with self.subTest(result=result), self.assertRaises(GateError):
                validate_evidence(['AC-001'], evidence(result))
        with self.assertRaises(GateError):
            validate_evidence(['AC-001', 'AC-002'], evidence())

    def test_producer_observation_and_commit_required(self):
        for key, value in [('producer', 'implement-agent'), ('commit', '')]:
            report = evidence()
            report[key] = value
            with self.assertRaises(GateError):
                validate_evidence(['AC-001'], report)
        report = evidence()
        report['checks'][0]['observed'] = ''
        with self.assertRaises(GateError):
            validate_evidence(['AC-001'], report)
        validate_evidence(['AC-001'], evidence())
