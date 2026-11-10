import assert from "node:assert/strict";
import provider, {createResumeHandler} from "../omp-provider.mjs";

const prior = process.env.LLM_LAUNCHER_OMP_PROVIDER;
const priorHost = process.env.LLM_LAUNCHER_AGENT_HOST;
try {
  const data = {id:"launcher-splash-fixture", baseUrl:"http://127.0.0.1:18899/v1", apiKey:"fixture-key",
    api:"openai-completions", authHeader:true, models:[{id:"qwen-fixture", contextWindow:8192, maxTokens:512}]};
  process.env.LLM_LAUNCHER_OMP_PROVIDER = JSON.stringify(data);
  delete process.env.LLM_LAUNCHER_AGENT_HOST;
  let calls = 0;
  provider({registerProvider(id, config) {
    calls += 1;
    assert.equal(id, data.id);
    assert.equal(config.apiKey,"fixture-key");
    assert.equal(config.models[0].id,"qwen-fixture");
    assert.equal(config.models[0].contextWindow,8192);
    assert.equal(config.models[0].maxTokens,512);
    assert.equal(config.api,"openai-completions");
  }});
  assert.equal(calls,1);
  process.env.LLM_LAUNCHER_AGENT_HOST = "console";
  let resume;
  provider({registerProvider() {}, registerCommand(name, command) {
    assert.equal(name, "resume");
    assert.match(command.description, /OMP conversation/);
    resume = command.handler;
  }});
  assert.equal(typeof resume, "function");
  process.env.LLM_LAUNCHER_AGENT_HOST = "terminal";
  provider({registerProvider() {}, registerCommand() {throw new Error("Terminal keeps native /resume");}});
  for (const change of [{baseUrl:"https://example.com/v1"}, {baseUrl:"http://127.0.0.1:18899/v1?key=x"},
    {baseUrl:"http://user:pass@127.0.0.1:18899/v1"}, {id:"cloud-provider"}, {models:[]}]) {
    process.env.LLM_LAUNCHER_OMP_PROVIDER = JSON.stringify({...data,...change});
    assert.throws(() => provider({registerProvider(){throw new Error("must not register");}}),/Invalid local/);
  }
  delete process.env.LLM_LAUNCHER_OMP_PROVIDER;
  assert.throws(() => provider({}),/missing/);
} finally {
  if (prior === undefined) delete process.env.LLM_LAUNCHER_OMP_PROVIDER;
  else process.env.LLM_LAUNCHER_OMP_PROVIDER = prior;
  if (priorHost === undefined) delete process.env.LLM_LAUNCHER_AGENT_HOST;
  else process.env.LLM_LAUNCHER_AGENT_HOST = priorHost;
}

function resumeFixture(sessions, select = options => options[0]) {
  const statuses = [];
  const notices = [];
  const selections = [];
  let loads = 0;
  const handler = createResumeHandler({loadSessionManager: async () => {
    loads += 1;
    return {async listForPicker(cwd, directory) {
      assert.equal(cwd, "/project");
      assert.equal(directory, "/sessions/project");
      return sessions;
    }};
  }});
  const ctx = {
    cwd: "/project",
    sessionManager: {getSessionDir: () => "/sessions/project", getSessionFile: () => "/sessions/project/current.jsonl"},
    switchSession() {throw new Error("Only the launcher may switch sessions with its model override");},
    ui: {
      setStatus(key, value) {statuses.push([key, value]);},
      notify(message, kind) {notices.push({message, kind});},
      async select(title, options) {
        selections.push({title, options});
        return select(options);
      },
    },
  };
  return {handler, ctx, statuses, notices, selections, loads: () => loads};
}

const session = (name, extra = {}) => ({path: `/sessions/project/${name}.jsonl`, id: name,
  title: "Saved conversation", modified: new Date("2026-10-21T15:42:00Z"), ...extra});
{
  const fixture = resumeFixture([
    session("current"), session("chosen", {title: "A\nuseful\u001b conversation"}),
    session("chosen"), session("other"),
  ]);
  assert.equal(fixture.loads(), 0, "native module is loaded only when the command runs");
  await fixture.handler("", fixture.ctx);
  assert.equal(fixture.loads(), 1);
  assert.equal(fixture.selections[0].options.length, 2, "current and duplicate paths are omitted");
  assert.match(fixture.selections[0].options[0], /A useful conversation · 2026-10-21 15:42 UTC/);
  assert.deepEqual(fixture.statuses, [["launcher.resumeSession", undefined],
    ["launcher.resumeSession", JSON.stringify({sessionPath: "/sessions/project/chosen.jsonl"})]]);
}
for (const cancelled of [undefined, null]) {
  const fixture = resumeFixture([session("saved")], () => cancelled);
  await fixture.handler("", fixture.ctx);
  assert.deepEqual(fixture.statuses, [["launcher.resumeSession", undefined]]);
}
{
  const fixture = resumeFixture([session("current"), {path: "relative.jsonl"}, {path: "/bad\u0000.jsonl"}]);
  await fixture.handler("", fixture.ctx);
  assert.equal(fixture.selections.length, 0);
  assert.match(fixture.notices[0].message, /No other saved OMP conversations/);
  assert.deepEqual(fixture.statuses, [["launcher.resumeSession", undefined]]);
}
{
  const fixture = resumeFixture(Array.from({length: 105}, (_, index) => session(`saved-${index}`)));
  await fixture.handler("", fixture.ctx);
  assert.equal(fixture.selections[0].options.length, 100);
}
{
  const fixture = resumeFixture([session("saved")], () => "/arbitrary/not-listed.jsonl");
  await assert.rejects(fixture.handler("", fixture.ctx), /no longer in this picker/);
  assert.deepEqual(fixture.statuses, [["launcher.resumeSession", undefined]]);
}
{
  const fixture = resumeFixture([session("saved")]);
  fixture.ctx.ui.select = async () => {throw new Error("picker closed");};
  await assert.rejects(fixture.handler("", fixture.ctx), /picker closed/);
  assert.deepEqual(fixture.statuses, [["launcher.resumeSession", undefined]]);
}
console.log("OMP provider tests passed");
