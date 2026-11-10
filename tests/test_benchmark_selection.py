"""Complete frozen selection bodies and generated local performance decisions."""
import ast
import copy
import dataclasses
import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import benchmark_selection as domain
import launcher
from tests.helpers.benchmark_selection_fixture import METADATA, FIXTURE, planner, original, method


class Projection(ast.NodeTransformer):
    def visit_Call(self, node):
        if (isinstance(node.func, ast.Attribute) and node.func.attr == 'descriptor_public'
                and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'live'
                and isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == 'self'):
            self.assert_descriptor_call(node)
            return ast.copy_location(ast.Call(ast.Attribute(ast.Name('receipt_descriptor', ast.Load()),
                'public', ast.Load()), [], []), node)
        return self.generic_visit(node)

    @staticmethod
    def assert_descriptor_call(node):
        assert len(node.args) == 1 and not node.keywords
        assert ast.unparse(node.args[0]) == 'receipt_descriptor.id'

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name) and node.value.value.id == "self":
            group = node.value.attr
            if group == "policy":
                return ast.copy_location(ast.Name(node.attr.upper(), ast.Load()), node)
            if group in {"contracts", "evidence", "live"}:
                if group == "live" and node.attr == "binary":
                    return ast.copy_location(ast.Attribute(ast.Name("BINARIES", ast.Load()), "get", ast.Load()), node)
                if group == "live" and node.attr == "mode_label":
                    return ast.copy_location(ast.Attribute(ast.Name("BenchmarkManager", ast.Load()), "_mode_label", ast.Load()), node)
                if group == "live" and node.attr == "now":
                    return ast.copy_location(ast.Attribute(ast.Name("datetime", ast.Load()), "now", ast.Load()), node)
                before = next(name for name, value in METADATA["functionGroups"].items()
                              if value == group and name.lstrip("_") == node.attr)
                return ast.copy_location(ast.Name(before, ast.Load()), node)
        if isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in METADATA["functions"]:
            return ast.copy_location(ast.Name(node.attr, ast.Load()), node)
        return self.generic_visit(node)


class BenchmarkSelectionTests(unittest.TestCase):
    def test_all_34_complete_bodies_and_signatures_match_frozen_source(self):
        old_tree = ast.parse(FIXTURE.read_text())
        new_tree = ast.parse(Path(domain.__file__).read_text())
        old = {node.name: node for node in old_tree.body if isinstance(node, ast.FunctionDef)}
        new = {node.name: node for node in new_tree.body if isinstance(node, ast.FunctionDef)}
        owner = next(node for node in new_tree.body if isinstance(node, ast.ClassDef) and node.name == "BenchmarkSelection")
        new.update({node.name: node for node in owner.body if isinstance(node, ast.FunctionDef)})
        self.assertEqual(set(old), set(METADATA["functions"]))
        current = planner(launcher)
        for name in METADATA["functions"]:
            with self.subTest(function=name):
                before = ast.Module(body=copy.deepcopy(old[name].body), type_ignores=[])
                body = copy.deepcopy(new[name].body)
                if name == 'benchmark_history_request':
                    index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'exact_record_ids')
                    self.assertEqual(ast.unparse(body[index].value), '{id(record) for record in exact_records}')
                    del body[index]
                    matches = [node for statement in body for node in ast.walk(statement)
                        if isinstance(node, ast.Compare) and ast.unparse(node) == 'id(record) in exact_record_ids']
                    self.assertEqual(len(matches), 1)
                    matches[0].left = ast.Name('record', ast.Load())
                    matches[0].comparators = [ast.Name('exact_records', ast.Load())]
                after = Projection().visit(ast.Module(body=body, type_ignores=[]))
                for body in (before.body, after.body):
                    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                        body[0].value.value = inspect.cleandoc(body[0].value.value)
                self.assertEqual(ast.dump(after, include_attributes=False), ast.dump(before, include_attributes=False))
                a, b = inspect.signature(getattr(launcher, name)), inspect.signature(method(current, name))
                self.assertEqual([(p.name, p.kind, p.default) for p in a.parameters.values()],
                                 [(p.name, p.kind, p.default) for p in b.parameters.values()])

    def test_import_needs_no_controller_io_processes_or_model_operations(self):
        code = '''
import builtins,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,sys.argv[1]);original=builtins.__import__
def only(name,*args,**kwargs):
 if name in {'launcher','llm_launcher'}:raise AssertionError('controller import')
 return original(name,*args,**kwargs)
def forbidden(*args,**kwargs):raise AssertionError('import side effect')
builtins.__import__=only;subprocess.Popen=forbidden;urllib.request.urlopen=forbidden
pathlib.Path.write_text=forbidden;pathlib.Path.write_bytes=forbidden
import benchmark_selection
assert 'launcher' not in sys.modules
'''
        result = subprocess.run([sys.executable, "-c", code, str(Path(domain.__file__).parent)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_frozen_policy_is_detached_and_named_binary_ports_remain_live(self):
        current = planner(launcher)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            current.policy.benchmark_max_records = 0
        with self.assertRaises(TypeError):
            current.policy.backend_labels['omlx'] = 'changed'
        detached = copy.deepcopy(current.policy.backend_labels)
        detached['omlx'] = 'changed'
        self.assertNotEqual(current.policy.backend_labels['omlx'], detached['omlx'])
        with mock.patch.dict(launcher.BINARIES, {'omlx': '/generated/one'}):
            self.assertEqual(current.live.binary('omlx'), '/generated/one')
        with mock.patch.dict(launcher.BINARIES, {'omlx': '/generated/two'}):
            self.assertEqual(current.live.binary('omlx'), '/generated/two')

    def test_controller_reuses_only_wiring_and_invalidates_changed_policy_inputs(self):
        first = launcher._benchmark_selection()
        self.assertIs(first, launcher._benchmark_selection())
        with mock.patch.dict(launcher.BINARIES, {'omlx': '/generated/current'}):
            self.assertIs(first, launcher._benchmark_selection())
            self.assertEqual(first.live.binary('omlx'), '/generated/current')
        with mock.patch.dict(launcher.BACKEND_LABELS, {'omlx': 'Generated changed label'}):
            changed = launcher._benchmark_selection()
            self.assertIsNot(first, changed)
            self.assertEqual(changed.policy.backend_labels['omlx'], 'Generated changed label')
            self.assertNotEqual(first.policy.backend_labels['omlx'], 'Generated changed label')
        restored = launcher._benchmark_selection()
        self.assertEqual(restored.policy.backend_labels['omlx'], launcher.BACKEND_LABELS['omlx'])
        with mock.patch.object(launcher, 'hardware_fingerprint', return_value='generated-current-machine'):
            self.assertIs(restored, launcher._benchmark_selection())
            self.assertEqual(restored.live.hardware_fingerprint(), 'generated-current-machine')
        with mock.patch.object(launcher, 'benchmark_integrity_issue', return_value='generated fresh failure'):
            self.assertIs(restored, launcher._benchmark_selection())
            self.assertEqual(restored.evidence.benchmark_integrity_issue({}), 'generated fresh failure')
        self.assertIn(Path(domain.__file__).resolve(), launcher.CONTROLLER_SOURCE_PATHS)

    def test_all_surface_sampling_and_exact_receipt_binding_outputs_match(self):
        old = original(launcher)
        current = planner(launcher)
        model = {'defaultSampling': {'temperature': .7, 'top_p': .9, 'top_k': 20}}
        for client in ('chat', 'pi', 'omp', 'opencode', 'codex'):
            for reasoning in ('off', 'auto', 'medium'):
                for kv in ('off', 'q8', 'q4'):
                    args = (model, 8192, 1024, client, reasoning, kv)
                    self.assertEqual(current.optimizer_evidence(*args), old['optimizer_evidence'](*args))
        valid = [{'evidenceBinding': {'scope': 'route', 'suite': 'quick', 'recordId': 'record-one'}},
                 {'evidenceBinding': {'scope': 'engine', 'suite': 'quick', 'shootoutId': 'matrix-one',
                                      'recordIds': {'omlx': 'one', 'mtplx': 'two'}}}, {}]
        invalid = [{'evidenceBinding': value} for value in ([], 'one', {'scope': 'unknown'},
                   {'scope': 'route', 'suite': 'quick'},
                   {'scope': 'route', 'suite': 'quick', 'recordId': 'bad/id'},
                   {'scope': 'engine', 'suite': 'quick', 'shootoutId': 'one', 'recordIds': {'unknown': 'two'}})]
        for payload in valid + invalid:
            outcomes = []
            for function in (old['validated_optimizer_evidence_binding'], current.validated_optimizer_evidence_binding):
                try: outcomes.append(('value', function(copy.deepcopy(payload))))
                except ValueError as error: outcomes.append(('error', str(error)))
            self.assertEqual(outcomes[0], outcomes[1])

    def test_pure_workload_output_difference_is_not_a_different_request(self):
        old = original(launcher)
        examples = [[], [{'signature': 'one'}],
                    [{'signature': 'one', 'qualityFingerprint': 'a'}, {'signature': 'two', 'qualityFingerprint': 'a'}],
                    [{'signature': 'one', 'qualityFingerprint': 'a', 'qualityCompletionTokens': 32, 'samples': []},
                     {'signature': 'one', 'qualityFingerprint': 'b', 'qualityCompletionTokens': 32, 'samples': []}]]
        for group in examples:
            self.assertEqual(domain.cross_engine_workload_compatibility(group),
                             old['cross_engine_workload_compatibility'](group))

    def test_full_generated_matrix_history_and_exact_contract_mutations_match(self):
        # Run the established complete matrix assertions on their private
        # generated models. This bypasses the class's real-machine model scan.
        from tests import test_launcher as established
        root = established.launcher
        calls = []
        targets = ('best_engine_request', 'benchmark_history_request', 'fastest_safe_options', 'rank_cross_engine_profile')
        def compare(name):
            def run(*args, **kwargs):
                old = original(root)
                current = planner(root)
                outcomes = []
                for function in (old[name], method(current, name)):
                    try: outcomes.append(('value', function(*copy.deepcopy(args), **copy.deepcopy(kwargs))))
                    except (ValueError, RuntimeError) as error: outcomes.append((type(error).__name__, str(error)))
                self.assertEqual(outcomes[0], outcomes[1], name)
                calls.append(name)
                if outcomes[0][0] == 'value':return outcomes[0][1]
                raise (ValueError if outcomes[0][0] == 'ValueError' else RuntimeError)(outcomes[0][1])
            return run
        case = established.LauncherTests('test_best_engine_requires_complete_comparable_matrix_and_clears_noise_floor')
        with mock.patch.multiple(root, **{name: compare(name) for name in targets}):
            result = unittest.TestResult()
            case.run(result)
        self.assertFalse(result.errors, result.errors)
        self.assertFalse(result.failures, result.failures)
        self.assertGreater(len(calls), 20)
        self.assertIn('best_engine_request', calls)
        self.assertIn('benchmark_history_request', calls)

    def test_equal_duplicate_records_keep_independent_fresh_verification_and_rejection_counts(self):
        from tests import test_launcher as established
        root = established.launcher
        captured = []
        real_history = root.benchmark_history_request
        def capture(*args, **kwargs):
            if len(args) > 2 and isinstance(args[2], list) and len(args[2]) >= 6:
                captured.append((copy.deepcopy(args), copy.deepcopy(kwargs)))
            return real_history(*args, **kwargs)
        case = established.LauncherTests('test_best_engine_requires_complete_comparable_matrix_and_clears_noise_floor')
        with mock.patch.object(root, 'benchmark_history_request', side_effect=capture):
            result = unittest.TestResult()
            case.run(result)
        self.assertFalse(result.errors, result.errors)
        self.assertFalse(result.failures, result.failures)
        args, kwargs = captured[0]
        record = copy.deepcopy(next(item for item in args[2] if item['backend'] == 'omlx'))
        record['id'] = 'generated-duplicate'
        duplicate_args = (args[0], args[1], [record, copy.deepcopy(record)])
        real_verifier = root._local_benchmark_record_verified
        for verdict in ('equal-valid', 'equal-rejected', 'changed-current-verdict'):
            outputs = []
            for frozen in (True, False):
                calls = []
                def verify(capability, item, evidence):
                    if item.get('id') == 'generated-duplicate':
                        calls.append(id(item))
                        if verdict == 'equal-rejected':return False
                        if verdict == 'changed-current-verdict':return len(calls) == 1
                    return real_verifier(capability, item, evidence)
                with mock.patch.object(root, 'hardware_fingerprint', return_value='cross-engine-mac'), \
                        mock.patch.object(root, '_local_benchmark_record_verified', side_effect=verify):
                    function = original(root)['benchmark_history_request'] if frozen else planner(root).benchmark_history_request
                    value = function(*copy.deepcopy(duplicate_args), **copy.deepcopy(kwargs))
                self.assertEqual(len(calls), 2, 'Equal values must not reuse an eligibility verdict')
                self.assertEqual(len(set(calls)), 2, 'Both separately owned records must be checked')
                outputs.append((value['exactRecordCount'], value['otherEvidence']['count'], value['receipt']['state']))
            if verdict == 'changed-current-verdict':
                self.assertEqual(outputs[0][:2], (1, 0))
                self.assertEqual(outputs[1][:2], (1, 1), 'Do not hide a rejected equal-value record')
                self.assertEqual(outputs[0][2], outputs[1][2])
                self.assertEqual(outputs[1][2], 'incomplete')
            else:
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[1][:2], (2, 0) if verdict == 'equal-valid' else (0, 2))


if __name__ == '__main__':
    unittest.main()
