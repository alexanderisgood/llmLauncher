"""Pinned Splash Q4/BF16 setup safety on tiny local fixtures; no downloads/GPU."""
from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import prepare_splash_flash_bf16 as worker


def artifact(name, body, algorithm='sha256'):
    digest = hashlib.sha256(body).hexdigest() if algorithm == 'sha256' else hashlib.sha1(f'blob {len(body)}\0'.encode() + body).hexdigest()
    return worker.Artifact(name, len(body), digest, algorithm)


class Fixture:
    def __init__(self, folder, receipt=True):
        self.root = Path(folder).resolve()
        self.q4 = [(f'variant/part-{number}.gguf', f'Q4-main-{number}'.encode()) for number in range(4)]
        self.ple = ('original-bf16.gguf', b'Original BF16 PLE')
        self.draft = [('config.json', b'{"model_type":"fixture"}'), ('model.safetensors', b'Pinned draft weights')]
        self.config = replace(worker.Setup(), workspace=self.root, runtime=self.root/'runtime',
            q4_root=self.root/'original-q4', bf16_root=self.root/'ple-source',
            output=self.root/'models'/'Q4-BF16', models_root=self.root/'assemblies',
            draft_root=self.root/'draft', receipt=self.root/'results'/'setup.json',
            q4_receipts=(self.root/'results'/'q4-download.json',),
            q4_files=tuple(artifact(name, body) for name, body in self.q4),
            bf16_file=artifact(*self.ple),
            draft_files=(artifact(*self.draft[0], 'git-sha1'), artifact(*self.draft[1])),
            poll_seconds=0, wait_seconds=1)
        for root, pairs in ((self.config.q4_root, self.q4), (self.config.draft_root, self.draft)):
            for name, body in pairs:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        self.unknown = self.config.q4_root/'variant'/'unexpected-user-file.gguf'
        self.unknown.write_bytes(b'Keep this unrelated model')
        if receipt:
            worker.atomic_json(self.config.q4_receipts[0], {
                'targetRepo':worker.Q4_REPO,'revision':worker.Q4_REVISION,'quantization':'Q4_K_M',
                'draftRevision':worker.DRAFT_REVISION,'draftRoot':str(self.config.draft_root),
                'completedAt':1,
                'files':[{'path':str(self.config.q4_root/item.path),'bytes':item.size,'sha256':item.digest}
                         for item in self.config.q4_files],
            })
        self.events=[]

    @property
    def inputs(self):
        return [self.config.q4_root/name for name,_ in self.q4] + [self.config.bf16_root/self.ple[0]]

    def download(self, config, progress):
        self.events.append('download')
        config.bf16_root.mkdir(parents=True,exist_ok=True)
        path=config.bf16_root/self.ple[0];path.write_bytes(self.ple[1]);return path

    def build(self, config, sources, ple, output, progress):
        self.events.append('build')
        self.assert_originals()
        output.mkdir(parents=True)
        paths=[]
        for number in range(5):
            path=output/f'part-{number}.gguf';path.write_bytes(f'unchanged model clone {number}'.encode());paths.append(str(path))
        receipt={'outputPaths':paths,'outputs':[{'path':path} for path in paths],
            'mainTensorParityVerified':True,'mainTensorDigest':'a'*64,'plePrecision':'BF16'}
        worker.atomic_json(output/'receipt.json',receipt)
        return receipt

    def inspect(self, config, paths, progress):
        self.events.append('inspect')
        return {'family':'Qwen3.8-Flash-Next','plePrecision':'BF16','quantization':'Q4_K',
            'path':str(paths[0]),'identity':'fixture-source'}

    def prepare(self, config, source, draft, progress):
        self.events.append('prepare')
        self.assert_originals()
        prepared=config.models_root/'prepared';prepared.mkdir(parents=True)
        files={f'target/{path.name}':{'path':str(path)} for path in sorted(config.output.glob('*.gguf'))}
        files.update({f'draft/{item.path}':{'path':str(draft/item.path)} for item in config.draft_files})
        worker.atomic_json(prepared/'model.json',{'files':files})
        return prepared

    def assert_originals(self):
        assert all(path.is_file() for path in self.inputs), 'Cleanup occurred before qualification'

    def run(self, **overrides):
        calls={'downloader':self.download,'builder':self.build,'inspector':self.inspect,
            'preparer':self.prepare,'sleeper':lambda _:None,'preflight_check':lambda *_:None}
        calls.update(overrides)
        with redirect_stdout(io.StringIO()):return worker.run_setup(self.config,**calls)


class FlashSetupTests(unittest.TestCase):
    def test_plan_is_read_only_and_contains_all_pins(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            before={str(path):path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()}
            output=io.StringIO()
            with mock.patch.object(worker,'Setup',return_value=fixture.config),redirect_stdout(output), \
                    mock.patch.object(worker,'run_setup',side_effect=AssertionError('plan started work')):
                self.assertEqual(worker.main(['--plan']),0)
            plan=json.loads(output.getvalue())
            self.assertEqual(plan['target']['revision'],worker.Q4_REVISION)
            self.assertEqual(plan['ple']['revision'],worker.BF16_REVISION)
            self.assertEqual(plan['draft']['revision'],worker.DRAFT_REVISION)
            self.assertEqual(len(plan['target']['files']),4)
            self.assertEqual(before,{str(path):path.read_bytes() for path in fixture.root.rglob('*') if path.is_file()})
            self.assertFalse(fixture.config.receipt.exists())

    def test_revision_mismatch_stops_before_download_or_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);fixture.config=replace(fixture.config,q4_revision='main')
            with self.assertRaisesRegex(ValueError,'pinned source'):fixture.run()
            self.assertFalse(fixture.events);self.assertFalse(fixture.config.receipt.exists())

    def test_checksum_is_independent_of_old_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            path=fixture.config.q4_root/fixture.q4[0][0]
            path.write_bytes(b'X'*path.stat().st_size)
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):fixture.run()
            fixture.assert_originals();self.assertNotIn('build',fixture.events)
            receipt=worker.read_json(fixture.config.receipt)
            self.assertEqual(receipt['status'],'failed');self.assertIn('checksum',receipt['error'])

    def test_git_blob_and_lfs_checksums_are_both_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            for item in fixture.config.draft_files:
                proof=worker.verify_artifact(fixture.config.draft_root,item)
                self.assertEqual(proof[item.algorithm],item.digest)
            bad=replace(fixture.config.draft_files[0],digest='0'*40)
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                worker.verify_artifact(fixture.config.draft_root,bad)

    def test_success_cleans_only_known_originals_after_native_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);result=fixture.run()
            self.assertEqual(fixture.events,['download','build','inspect','prepare'])
            self.assertEqual(result['status'],'ready');self.assertEqual(result['plePrecision'],'BF16')
            self.assertEqual(result['mainPrecision'],'Q4_K_M');self.assertTrue(result['mainTensorParityVerified'])
            self.assertTrue(result['completedAt']);self.assertTrue(Path(result['preparedRoot']).is_dir())
            self.assertTrue(all(not path.exists() for path in fixture.inputs))
            self.assertEqual(fixture.unknown.read_bytes(),b'Keep this unrelated model')
            self.assertTrue(all((fixture.config.draft_root/name).is_file() for name,_ in fixture.draft))
            self.assertTrue(all(Path(path).is_file() for path in result['outputPaths']))
            self.assertTrue(all(Path(item['path']).parent==fixture.config.output for item in result['builderReceipt']['outputs']))

    def test_completed_pinned_files_recover_when_old_receipts_are_lost(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder,receipt=False);result=fixture.run()
            self.assertEqual(result['status'],'ready')
            self.assertIn('pinned local files',result['originalDownloadReceipt']['completionEvidence'])

    def test_wrong_download_receipt_revision_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);record=worker.read_json(fixture.config.q4_receipts[0])
            record['revision']='different';worker.atomic_json(fixture.config.q4_receipts[0],record)
            with self.assertRaisesRegex(ValueError,'pinned target/draft'):fixture.run()
            fixture.assert_originals();self.assertNotIn('build',fixture.events)

    def test_native_rejection_preserves_all_inputs_and_published_output(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            def reject(*_):return {'family':'Qwen3.8-Flash-Next','plePrecision':'Q8_0','quantization':'Q4_K'}
            with self.assertRaisesRegex(ValueError,'original BF16'):fixture.run(inspector=reject)
            fixture.assert_originals();self.assertTrue(fixture.config.output.is_dir())
            self.assertNotIn('prepare',fixture.events)

    def test_builder_failure_and_wrong_draft_fallback_preserve_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            def fail(*_):raise RuntimeError('clone failure')
            with self.assertRaisesRegex(RuntimeError,'clone failure'):fixture.run(builder=fail)
            fixture.assert_originals()
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            def wrong_draft(config,source,draft,progress):
                prepared=fixture.prepare(config,source,draft,progress)
                record=worker.read_json(prepared/'model.json')
                record['files']['draft/config.json']['path']=str(fixture.unknown)
                worker.atomic_json(prepared/'model.json',record);return prepared
            with self.assertRaisesRegex(ValueError,'verified pinned draft'):fixture.run(preparer=wrong_draft)
            fixture.assert_originals()

    def test_late_input_change_stops_before_any_original_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            def mutate(config,source,draft,progress):
                prepared=fixture.prepare(config,source,draft,progress)
                fixture.inputs[-1].write_bytes(b'X'*len(fixture.ple[1]));return prepared
            with self.assertRaisesRegex(ValueError,'changed before cleanup'):fixture.run(preparer=mutate)
            fixture.assert_originals()
            self.assertFalse(worker.read_json(fixture.config.receipt).get('removedOriginals'))

    def test_interruption_during_cleanup_resumes_without_download_or_rebuild(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);real_unlink=Path.unlink;deleted=[]
            def interrupted(path,*args,**kwargs):
                if path in fixture.inputs:
                    if deleted:raise RuntimeError('simulated interruption')
                    deleted.append(str(path))
                return real_unlink(path,*args,**kwargs)
            with mock.patch.object(Path,'unlink',interrupted),self.assertRaisesRegex(RuntimeError,'interruption'):
                fixture.run()
            self.assertEqual(len(deleted),1);self.assertFalse(fixture.inputs[0].exists())
            prior=worker.read_json(fixture.config.receipt)
            self.assertTrue(prior['preparedRoot']);self.assertTrue(prior['cleanupStartedAt'])
            def forbidden(*_):raise AssertionError('qualified setup must not download, rebuild or reprepare')
            result=fixture.run(downloader=forbidden,builder=forbidden,preparer=forbidden)
            self.assertEqual(result['status'],'ready');self.assertEqual(len(result['removedOriginals']),5)
            self.assertTrue(all(not path.exists() for path in fixture.inputs));self.assertTrue(fixture.unknown.exists())
            again=fixture.run(downloader=forbidden,builder=forbidden,preparer=forbidden)
            self.assertEqual(again['status'],'ready')

    def test_run_lock_refuses_duplicate_worker_without_altering_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            with worker.setup_lock(fixture.config):
                with self.assertRaisesRegex(RuntimeError,'Setup lock exists'):
                    with worker.setup_lock(fixture.config):self.fail('duplicate worker acquired lock')
            self.assertFalse(fixture.config.receipt.with_suffix('.json.lock').exists())

    def test_recovery_receipt_cannot_expand_cleanup_to_unknown_files(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);fixture.run()
            record=worker.read_json(fixture.config.receipt)
            record['status']='failed'
            record['verifiedInputs'][0]['path']=str(fixture.unknown)
            worker.atomic_json(fixture.config.receipt,record)
            with self.assertRaisesRegex(ValueError,'exactly the pinned original'):
                fixture.run(downloader=mock.Mock(side_effect=AssertionError('unexpected download')))
            self.assertEqual(fixture.unknown.read_bytes(),b'Keep this unrelated model')

    def test_storage_resume_counts_only_allocated_exact_pinned_partials(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);item=fixture.config.bf16_file
            cache=fixture.config.bf16_root/'.cache/huggingface/download'
            cache.mkdir(parents=True)
            (cache/('unknown.'+'0'*64+'.incomplete')).write_bytes(b'x'*100)
            self.assertEqual(worker.remaining_download_bytes(fixture.config.bf16_root,item),item.size)
            partial=cache/f'part.{item.digest}.fixture.incomplete';partial.write_bytes(b'abcd')
            info=partial.stat();allocated=min(info.st_size,info.st_blocks*512)
            self.assertEqual(worker.remaining_download_bytes(fixture.config.bf16_root,item),item.size-allocated)

    def test_preparation_pins_explicit_local_draft_and_disables_network(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            completed=mock.Mock(stdout=json.dumps({'root':str(fixture.config.models_root/'prepared')})+'\n')
            with mock.patch.object(worker.subprocess,'run',return_value=completed) as run:
                result=worker.prepare_output(fixture.config,{'path':'fixture'},fixture.config.draft_root,None)
            args=run.call_args
            self.assertEqual(args.args[0][0],str(fixture.config.runtime/'python/bin/python3'))
            self.assertEqual(args.kwargs['env']['HF_HUB_OFFLINE'],'1')
            self.assertEqual(json.loads(args.kwargs['input'])['drafts'],[str(fixture.config.draft_root)])
            self.assertEqual(result,fixture.config.models_root/'prepared')


if __name__=='__main__':unittest.main()
