import tempfile
import unittest
from pathlib import Path
from docloop.evidence import archive_change, normalize_evidence, validate_evidence
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

    def test_archive_accepts_canonical_and_legacy_checklist_names(self):
        for index, name in enumerate(('checklist.md', 'checkList.md'), 1):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as base:
                    root, source = Path(base), Path(base) / 'source'
                    source.mkdir()
                    for filename, content in {
                        'spec.md': '# Spec\nAC-001\n', 'decisions.md': '# Decisions\n',
                        'tasks.md': '# Tasks\n', 'evidence.yaml': 'verification:\n  status: passed\n',
                        'review.yaml': 'status: passed\n', name: '# Checklist\n'}.items():
                        (source / filename).write_text(content, encoding='utf-8')
                    target = archive_change(root, f'change-{index}', source)
                    self.assertTrue((target / name).is_file())
                    self.assertTrue((target / 'manifest.yaml').is_file())

    def test_legacy_evidence_is_readable_but_not_gate_accepted(self):
        legacy = {'producer': 'codex-main', 'commit': 'a' * 40, 'checks': [
            {'id': 'V-001', 'test_case_id': 'TC-001', 'requirement_ids': ['AC-001'],
             'type': 'static', 'result': 'passed', 'command_or_method': 'legacy',
             'observed': 'ok', 'evidence': 'logs/V-001.txt'}]}
        normalized = normalize_evidence(legacy)
        self.assertEqual(normalized['checks'][0]['test_layer'], 'static')
        self.assertEqual(normalized['checks'][0]['log_path'], 'logs/V-001.txt')
        with self.assertRaises(GateError):
            validate_evidence(['AC-001'], legacy)

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
