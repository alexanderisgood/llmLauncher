"""Resumable pinned HTTP recovery without network or active Xet mutations."""
from contextlib import contextmanager, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import recover_splash_flash_downloads as recovery


class Response:
    def __init__(self, status=206, body=b'ABCD', start=0, end=3, total=8, **headers):
        self.status_code=status;self.body=body;self.history=[]
        self.headers={'Content-Range':f'bytes {start}-{end}/{total}','Content-Length':str(len(body)),**headers}
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def iter_bytes(self,chunk_size):yield self.body


class Client:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def stream(self,*args,**kwargs):self.calls.append((args,kwargs));return next(self.responses)


class Fixture:
    def __init__(self,folder,body=b'ABCDEFGH'):
        self.root=Path(folder).resolve();self.body=body
        self.artifact=recovery.pins.Artifact('variant/model.gguf',len(body),hashlib.sha256(body).hexdigest())
        self.config=replace(recovery.Recovery(),root=self.root/'target',draft_root=self.root/'draft',
            receipt=self.root/'recovery.json',completion_receipt=self.root/'complete.json',chunk_bytes=4,retries=2,poll_seconds=0)
        self.progress=recovery.Progress(self.config);self.events=[]
    @contextmanager
    def lock(self,root,artifact):
        self.events.append(('lock',artifact.path))
        file_path=root/artifact.path;metadata=root/'.cache/huggingface/download'/(artifact.path+'.metadata')
        file_path.parent.mkdir(parents=True,exist_ok=True);metadata.parent.mkdir(parents=True,exist_ok=True)
        yield SimpleNamespace(file_path=file_path,metadata_path=metadata,lock_path=metadata.with_suffix('.lock'))
    def reader(self,client,repo,revision,artifact,start,end,target):
        self.events.append(('range',start,end));body=self.body[start:end+1];target.write(body)
        return hashlib.sha256(body).hexdigest()
    def run(self,reader=None,client=None):
        with redirect_stdout(io.StringIO()):
            return recovery.recover_file(self.config,self.config.root,recovery.pins.Q4_REPO,
                recovery.pins.Q4_REVISION,self.artifact,client,self.progress,locker=self.lock,
                range_reader=reader or self.reader,sleeper=lambda _:None)


class RangeProtocolTests(unittest.TestCase):
    def test_exact_range_headers_and_body_are_required(self):
        client=Client([Response()]);target=io.BytesIO()
        artifact=recovery.pins.Artifact('file.gguf',8,'a'*64)
        sha=recovery.read_range(client,'owner/repo','pinned',artifact,0,3,target)
        self.assertEqual(target.getvalue(),b'ABCD');self.assertEqual(sha,hashlib.sha256(b'ABCD').hexdigest())
        self.assertEqual(client.calls[0][1]['headers'],{'Range':'bytes=0-3','Accept-Encoding':'identity'})
        self.assertIn('/resolve/pinned/file.gguf?',client.calls[0][0][1])

    def test_ignored_ranges_wrong_bounds_lengths_and_encodings_are_rejected(self):
        artifact=recovery.pins.Artifact('file.gguf',8,'a'*64)
        for response in (Response(status=200),Response(start=1,end=4),Response(total=9),
                Response(**{'Content-Length':'9'}),Response(**{'Content-Encoding':'gzip'}),
                Response(**{'X-Repo-Commit':'other'})):
            with self.subTest(response=response.headers),self.assertRaises(recovery.ProtocolError):
                recovery.read_range(Client([response]),'owner/repo','pinned',artifact,0,3,io.BytesIO())

    def test_expired_url_retries_with_fresh_resolve_without_duplicate_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            client=Client([Response(status=403),Response(),Response(body=b'EFGH',start=4,end=7)])
            fixture.run(reader=recovery.read_range,client=client)
            self.assertEqual((fixture.config.root/fixture.artifact.path).read_bytes(),fixture.body)
            self.assertEqual(len(client.calls),3)
            self.assertNotEqual(client.calls[0][0][1],client.calls[1][0][1])
            self.assertEqual(client.calls[0][1]['headers']['Range'],client.calls[1][1]['headers']['Range'])

    def test_short_and_oversized_streams_cannot_publish(self):
        artifact=recovery.pins.Artifact('file.gguf',8,'a'*64)
        for body,error in ((b'ABC',recovery.TransientError),(b'ABCDE',recovery.ProtocolError)):
            response=Response(body=body,**{'Content-Length':'4'})
            with self.subTest(body=body),self.assertRaises(error):
                recovery.read_range(Client([response]),'owner/repo','pinned',artifact,0,3,io.BytesIO())


class RecoveryDurabilityTests(unittest.TestCase):
    def test_success_uses_separate_partial_and_exact_sha_before_atomic_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            xet=fixture.config.root/'.cache/huggingface/download/variant/active-xet.incomplete'
            xet.parent.mkdir(parents=True);xet.write_bytes(b'ACTIVE XET PARTIAL')
            proof=fixture.run()
            self.assertEqual(proof['sha256'],fixture.artifact.digest)
            self.assertEqual(proof['path'],str(fixture.config.root/fixture.artifact.path))
            self.assertEqual(xet.read_bytes(),b'ACTIVE XET PARTIAL')
            self.assertEqual([event for event in fixture.events if event[0]=='range'],[('range',0,3),('range',4,7)])
            self.assertFalse(list(xet.parent.glob('.launcher-http-*.partial')))
            metadata=xet.parent/'model.gguf.metadata'
            self.assertEqual(metadata.read_text().splitlines()[:2],[recovery.pins.Q4_REVISION,fixture.artifact.digest])

    def test_failed_range_preserves_committed_chunks_and_resumes_exact_offset(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);fixture.config=replace(fixture.config,retries=1)
            def interrupted(client,repo,revision,artifact,start,end,target):
                if start==4:
                    target.write(b'XX');raise ConnectionError('interrupted')
                return fixture.reader(client,repo,revision,artifact,start,end,target)
            with self.assertRaisesRegex(RuntimeError,'partial was preserved'):fixture.run(reader=interrupted)
            partial=next(fixture.config.root.rglob('.launcher-http-*.partial'))
            self.assertEqual(partial.read_bytes(),b'ABCD')
            self.assertFalse((fixture.config.root/fixture.artifact.path).exists())
            fixture.events=[];fixture.run()
            self.assertEqual([event for event in fixture.events if event[0]=='range'],[('range',4,7)])
            self.assertEqual((fixture.config.root/fixture.artifact.path).read_bytes(),fixture.body)

    def test_resume_verifies_committed_data_before_discarding_uncommitted_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);fixture.config=replace(fixture.config,retries=1)
            def interrupted(client,repo,revision,artifact,start,end,target):
                if start==4:raise ConnectionError('stop')
                return fixture.reader(client,repo,revision,artifact,start,end,target)
            with self.assertRaises(RuntimeError):fixture.run(reader=interrupted)
            partial=next(fixture.config.root.rglob('.launcher-http-*.partial'))
            with partial.open('ab') as output:output.write(b'uncommitted tail')
            fixture.run();self.assertEqual((fixture.config.root/fixture.artifact.path).read_bytes(),fixture.body)
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder);fixture.config=replace(fixture.config,retries=1)
            with self.assertRaises(RuntimeError):fixture.run(reader=lambda *_:(_ for _ in ()).throw(ConnectionError()))
            partial=next(fixture.config.root.rglob('.launcher-http-*.partial'))
            ledger=partial.with_suffix('.json');state=recovery.pins.read_json(ledger)
            state['revision']='other';recovery.pins.atomic_json(ledger,state)
            with self.assertRaisesRegex(recovery.ProtocolError,'provenance'):fixture.run()

    def test_wrong_full_checksum_never_publishes_or_deletes_active_files(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            def wrong(client,repo,revision,artifact,start,end,target):
                body=b'X'*(end-start+1);target.write(body);return hashlib.sha256(body).hexdigest()
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):fixture.run(reader=wrong)
            self.assertFalse((fixture.config.root/fixture.artifact.path).exists())
            self.assertTrue(list(fixture.config.root.rglob('.launcher-http-*.partial')))

    def test_atomic_publication_refuses_existing_target_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);partial=root/'partial';destination=root/'destination'
            partial.write_bytes(b'new');destination.write_bytes(b'original')
            with self.assertRaises(FileExistsError):recovery.publish_verified(partial,destination)
            self.assertEqual(destination.read_bytes(),b'original');self.assertEqual(partial.read_bytes(),b'new')

    def test_second_shard_only_precedes_original_exit_then_all_pins_and_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture=Fixture(folder)
            targets=tuple(replace(fixture.artifact,path=f'part-{number}.gguf') for number in range(4))
            drafts=tuple(replace(fixture.artifact,path=name) for name in ('config.json','model.safetensors'))
            config=replace(fixture.config,target_files=targets,draft_files=drafts)
            events=[];alive_calls=iter((True,False))
            def alive(pid):events.append(('alive',pid));return next(alive_calls)
            def recover(config,root,repo,revision,artifact,client,progress):
                events.append(('recover',artifact.path))
                return {'path':str(root/artifact.path),'bytes':artifact.size,'sha256':artifact.digest}
            with redirect_stdout(io.StringIO()):
                result=recovery.run_recovery(config,None,recover=recover,alive=alive,sleeper=lambda _:None)
            self.assertEqual(events[0],('recover','part-1.gguf'))
            self.assertEqual(events[1:3],[('alive',7500),('alive',7500)])
            self.assertEqual([event[1] for event in events[3:]],[item.path for item in (*targets,*drafts)])
            self.assertEqual(result['status'],'ready')
            receipt=recovery.pins.read_json(config.completion_receipt)
            self.assertEqual(receipt['revision'],recovery.pins.Q4_REVISION)
            self.assertEqual(receipt['draftRevision'],recovery.pins.DRAFT_REVISION)
            self.assertEqual(len(receipt['files']),4)


if __name__=='__main__':unittest.main()
