#!/usr/bin/env python3
"""Run the real Hub RPC coding fixture on an idle launcher, then unload it.

Uses the selected production engine/context/sampling contract. Tests remain
external oracles: their bytes must stay unchanged and a separate Node process
must pass them. No user project or existing session is reused. This is a small
reliability/speed screen, not proof of general coding ability.
"""
import argparse
import fcntl
import hashlib
import json
import secrets
import re
import select
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PROMPT = """In this isolated launcher test folder, repair cache.cjs. Read cache.cjs and cache.test.cjs, and run node --test cache.test.cjs BEFORE editing to observe the failures. TTLCache must implement a capacity-bounded LRU cache with expiry: positive integer capacity; finite nonnegative TTL with no mutation on rejection; inclusive expiry; zero TTL removes a key; reads refresh recency without extending TTL; overwrites refresh recency; expired entries are purged before eviction and size reporting. Preserve falsy values and object keys. Modify only cache.cjs and preserve every test. Run the tests again after the repair, inspect the actual result, and finish with a concise explanation. Do not use the network or change anything outside this test folder."""


class Hub:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.token = self.call("/api/bootstrap")["token"]

    def call(self, path, data=None, *, timeout=30):
        headers = {"Content-Type": "application/json"}
        if data is not None:
            headers["X-Launcher-Token"] = self.token
        req = urllib.request.Request(self.base + path, headers=headers,
            data=json.dumps(data).encode() if data is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as reply:
                return json.load(reply)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read(4000).decode(errors="replace")) from error


class Timeline:
    """Use the same bounded transcript reducer as the production Hub."""
    def __init__(self):
        script = """const core=require(process.argv[1]); let state=core.emptyTimeline();
require('node:readline').createInterface({input:process.stdin}).on('line', line=>{
 state=core.applyTimelineEnvelope(state,JSON.parse(line)).state;
 process.stdout.write(JSON.stringify(state.items)+'\\n');
});"""
        self.process = subprocess.Popen(['node', '-e', script, str(ROOT/'pi_timeline.js')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    def apply(self, envelope):
        self.process.stdin.write(json.dumps(envelope)+'\n'); self.process.stdin.flush()
        if not select.select([self.process.stdout], [], [], 5)[0]:
            raise RuntimeError('The Hub transcript reducer did not respond.')
        return json.loads(self.process.stdout.readline())

    def close(self):
        self.process.stdin.close()
        try: self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait(timeout=3)
        self.process.stdout.close()


def stage_completion(command, items, previous_summaries, start_revision, console):
    """Idle is insufficient: require fresh native success evidence for this stage."""
    if console.get('streaming') or console.get('compacting') or console.get('pendingMessages'):
        return None
    fresh = [item for item in items if item.get('revision', 0) > start_revision]
    summaries = [item for item in fresh if item.get('kind') == 'summary'
                 and item.get('itemId') not in previous_summaries]
    failures = [item for item in summaries if item.get('title') != 'Complete']
    failures += [item for item in fresh if (item.get('kind') == 'error' and item.get('text'))
                 or item.get('title') in {'Compaction cancelled', 'No final answer', 'Turn incomplete'}]
    if failures:
        return {'state':'failed', 'evidence':failures}
    if command == 'compact':
        evidence = [item for item in fresh if item.get('title') == 'Context ready']
    else:
        evidence = [item for item in summaries if item.get('title') == 'Complete']
    return {'state':'complete', 'evidence':evidence} if evidence else None


def oracle_result(check):
    """An exit code alone cannot prove the eight unchanged tests executed."""
    names = ('tests', 'pass', 'fail', 'cancelled', 'skipped', 'todo')
    counts = {}
    for name in names:
        values = re.findall(rf'^# {name} ([0-9]+)\s*$', check.stdout, re.MULTILINE)
        if len(values) != 1:
            return {'passed':False, 'counts':counts, 'error':'Missing or ambiguous TAP totals'}
        counts[name] = int(values[0])
    passed = check.returncode == 0 and counts == {
        'tests':8, 'pass':8, 'fail':0, 'cancelled':0, 'skipped':0, 'todo':0,
    }
    return {'passed':passed, 'counts':counts, 'exitCode':check.returncode}


def stop_owned_fixture(hub, run_id, project):
    status = hub.call('/api/status')
    run = status.get('run') or {}
    if status.get('phase') == 'idle':
        return 'idle'
    # The unique generated project also identifies an accepted launch whose
    # HTTP reply was lost before its run ID could be captured.
    if run.get('project') != str(project) or (run_id and run.get('runId') != run_id):
        raise RuntimeError('Cleanup skipped: the launcher no longer owns this fixture route.')
    hub.call('/api/stop', {}, timeout=60)
    after = hub.call('/api/status')
    if after.get('phase') != 'idle':
        raise RuntimeError('The fixture stop did not leave the launcher idle.')
    return 'unloaded'


def verify(args):
    hub = Hub(args.controller)
    if hub.call("/api/status").get("phase") != "idle":
        raise RuntimeError("End the current model session first; this check requires an idle launcher.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = Path(tempfile.mkdtemp(prefix="launcher-hub-check-")).resolve()
    for name in ("cache.cjs", "cache.test.cjs"):
        shutil.copyfile(ROOT / "tests/fixtures/pi-coding" / name, project / name)
    original = hashlib.sha256((project / "cache.test.cjs").read_bytes()).hexdigest()
    baseline = subprocess.run(["node", "--test", "--test-reporter=tap", "cache.test.cjs"], cwd=project,
                              capture_output=True, text=True, timeout=15)
    if baseline.returncode == 0:
        raise RuntimeError("The fixture must fail before the model repairs it.")
    request = json.loads(args.route.read_text())
    request.update(client="pi", agentHost="console", project=str(project))
    request.pop("piSessionFile", None)
    (output / "route.json").write_text(json.dumps(request, indent=2))
    (output / "baseline.txt").write_text(baseline.stdout + baseline.stderr)
    run_id = None
    items, requests, stages = [], {}, []
    timeline = None
    launch_attempted = False
    summary_items = {}
    thinking_seen = False
    offset = revision = 0
    result = {"completed": False, "project": str(project), "stages": stages}
    started = time.monotonic()
    try:
        planned = hub.call("/api/session/plan", request)
        (output / "admission.json").write_text(json.dumps(planned, indent=2))
        timeline = Timeline()
        launch_attempted = True
        launched = hub.call("/api/launch", request)  # Normal launch enforces admission itself.
        run_id = (launched.get("run") or {}).get("runId")
        if not run_id:
            raise RuntimeError("Launch did not return an owned run ID.")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            status = hub.call("/api/status")
            run = status.get("run") or {}
            if run and run.get("project") != str(project):
                raise RuntimeError("The active route changed during startup.")
            if run and run.get("runId") != run_id:
                raise RuntimeError("The active run changed during startup.")
            if status.get("phase") == "running" and status.get("agentConsoles"):
                break
            if status.get("phase") in {"failed", "error", "idle"}:
                raise RuntimeError(status.get("message"))
            time.sleep(1)
        else:
            raise TimeoutError("Hub startup exceeded three minutes")
        console = next(c for c in status["agentConsoles"] if c["ownerRunId"] == run_id)
        identity = {"ownerRunId": run_id, "surfaceId": console["surfaceId"]}
        result.update(runId=run_id, run=run)

        def stage(label, command, message=None):
            nonlocal offset, revision, items, thinking_seen
            start_revision = revision
            previous_summaries = set(summary_items)
            data = {**identity, "command": command}
            if message is not None:
                data["message"] = message
            hub.call("/api/agent-console/input", data)
            began = time.monotonic()
            last_report = began
            while time.monotonic() - began < args.timeout:
                status = hub.call("/api/status")
                if (status.get("run") or {}).get("runId") != run_id:
                    raise RuntimeError("The fixture no longer owns the active route.")
                c = hub.call("/api/agent-console/read", {**identity, "offset": offset,
                    "timelineRevision": revision})["console"]
                offset, revision = c["nextOffset"], c["timelineRevision"]
                items = timeline.apply(c)
                for item in items:
                    if item.get('kind') == 'summary': summary_items[item['itemId']] = item
                    if item.get('kind') == 'thinking' and item.get('text'): thinking_seen = True
                result['summaries'] = list(summary_items.values())
                activity = status.get('activity') or {}
                for collection in ('recent', 'active', 'queued'):
                    for record in activity.get(collection, []): requests[record['id']] = record
                (output / "timeline.json").write_text(json.dumps(items, indent=2))
                (output / "requests.json").write_text(json.dumps(list(requests.values()), indent=2))
                if c.get("interactions"):
                    raise RuntimeError("The fixture is waiting for an unexpected interactive approval.")
                if c.get("queuePaused") or c.get("state") != "running":
                    raise RuntimeError("The fixture paused or its Pi process stopped.")
                elapsed = time.monotonic() - began
                if len(requests) > 24:
                    raise RuntimeError("The bounded screen exceeded 24 model requests.")
                terminal = stage_completion(command, items, previous_summaries, start_revision, c)
                if terminal:
                    if terminal['state'] == 'failed':
                        stages.append({'name':label, 'seconds':round(elapsed, 2), **terminal})
                        raise RuntimeError(f"{label} did not finish cleanly: " + ', '.join(item.get('title', 'Error') for item in terminal['evidence']))
                    # The pre-read status can lag the closing Pi event. Refresh
                    # receipts before advancing so the final request is counted.
                    latest = hub.call('/api/status')
                    if (latest.get('run') or {}).get('runId') != run_id:
                        raise RuntimeError('The fixture lost ownership at stage completion.')
                    activity = latest.get('activity') or {}
                    for collection in ('recent', 'active', 'queued'):
                        for record in activity.get(collection, []): requests[record['id']] = record
                    if len(requests) > 24:
                        raise RuntimeError("The bounded screen exceeded 24 model requests.")
                    if not any(record.get('state') in {'queued', 'running', 'cancelling'} for record in requests.values()):
                        stages.append({'name':label, 'seconds':round(elapsed, 2), **terminal})
                        (output/'requests.json').write_text(json.dumps(list(requests.values()), indent=2))
                        return
                if time.monotonic() - last_report > 30:
                    print(json.dumps({"stage": label, "seconds": round(elapsed),
                        "requests": len(requests), "tools": sum(i.get("kind") == "toolResult" for i in items)}), flush=True)
                    last_report = time.monotonic()
                time.sleep(1)
            raise TimeoutError(f"{label} exceeded the {args.timeout}-second stage limit")

        stage("repair", "prompt", PROMPT)
        result['repairSha256'] = hashlib.sha256((project/'cache.cjs').read_bytes()).hexdigest()
        marker = None
        if args.compact:
            # Enough real tool history for native Pi to choose a compaction cut.
            # These generated rows are disposable test data, never user history.
            marker = 'hub-check-' + secrets.token_hex(8)
            notes = ''.join(f"ROW{index:04d}: diagnostic fixture data {secrets.token_hex(24)}\n" for index in range(512))
            (project/'context-notes.txt').write_text(notes + f"Verification marker: {marker}\n")
            stage("context-checkpoint", "prompt", "Read context-notes.txt once. Its rows are synthetic test data; no analysis is needed. Remember the verification marker at the end for the next prompt. Do not edit anything. Reply briefly that the checkpoint is recorded, then stop.")
            stage("compact", "compact")
            (project/'context-notes.txt').unlink()  # The follow-up must use retained context.
        before_warm = revision
        warm_prompt = "Verify the saved repair by running node --test cache.test.cjs once more. Do not edit anything. Report the observed pass/fail count, then finish."
        if marker:
            warm_prompt += " Also report the verification marker from the context checkpoint, without reading context-notes.txt again."
        stage("warm-verification", "prompt", warm_prompt)
        result['checkpointRetained'] = marker is None or any(
            item.get('kind') == 'answer' and item.get('revision', 0) > before_warm
            and marker in item.get('text', '') for item in items)
        result['afterWarmSha256'] = hashlib.sha256((project/'cache.cjs').read_bytes()).hexdigest()
        result['warmUnchanged'] = result['afterWarmSha256'] == result['repairSha256']
        check = subprocess.run(["node", "--test", "--test-reporter=tap", "cache.test.cjs"], cwd=project,
                               capture_output=True, text=True, timeout=15)
        unchanged = hashlib.sha256((project / "cache.test.cjs").read_bytes()).hexdigest() == original
        thinking = thinking_seen
        summaries = list(summary_items.values())
        failed = not requests or any(r.get("statusCode") != 200 or r.get('result') != 'completed' for r in requests.values())
        oracle = oracle_result(check)
        result.update(testsPassed=oracle['passed'], testOracle=oracle, testsUnchanged=unchanged,
            reasoningPresent=thinking, requests=len(requests), summaries=summaries,
            completed=oracle['passed'] and unchanged and result['warmUnchanged']
            and result['checkpointRetained'] and thinking and not failed)
        (output / "verification.txt").write_text(check.stdout + check.stderr)
        shutil.copyfile(project / "cache.cjs", output / "cache.cjs")
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        result["elapsedSeconds"] = round(time.monotonic() - started, 2)
        if timeline:
            try: timeline.close()
            except Exception as error: result['transcriptCleanupError'] = str(error)
        if launch_attempted:
            try: result['cleanup'] = stop_owned_fixture(hub, run_id, project)
            except Exception as error:
                result['cleanupError'] = str(error)
                result['completed'] = False
        (output / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    return result["completed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", default="http://127.0.0.1:17344")
    parser.add_argument("--route", type=Path, required=True, help="Normal launcher request JSON; project/session are replaced")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if not 30 <= args.timeout <= 900:
        parser.error("Use a stage timeout between 30 and 900 seconds")
    with open(Path(tempfile.gettempdir()) / "llm-launcher-harness-screen.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raise SystemExit(0 if verify(args) else 1)


if __name__ == "__main__":
    main()
