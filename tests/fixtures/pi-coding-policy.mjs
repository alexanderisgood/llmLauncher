// Test-only restriction around Pi's real read/edit/write tools. Never loaded
// in ordinary user sessions. Test execution has no shell or network access.
import fs from 'node:fs';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {Type} from 'typebox';
const execute = promisify(execFile);

export function fileToolAllowed(root, toolName, input) {
  if (!['read', 'edit', 'write'].includes(toolName) || typeof input?.path !== 'string') return false;
  const target = path.resolve(root, input.path);
  const names = toolName === 'read' ? ['cache.cjs', 'cache.test.cjs'] : ['cache.cjs'];
  return names.some(name => target === path.join(root, name))
    && fs.realpathSync(target) === target && fs.statSync(target).isFile();
}

export function testSandbox(root) {
  return `(version 1)(allow default)(deny network*)(deny process-fork)
    (deny file-write*)(allow file-write* (literal "/dev/null"))
    (deny file-read* (subpath "/Users") (subpath "/private"))
    (allow file-read-metadata)
    (allow file-read* (subpath ${JSON.stringify(root)})
      (subpath "/private/var/db/dyld") (subpath "/private/etc"))`;
}

export default function codingFixture(pi) {
  const root = fs.realpathSync(process.env.LLM_LAUNCHER_PI_FIXTURE_ROOT || '');
  const audit = process.env.LLM_LAUNCHER_PI_FIXTURE_AUDIT;
  if (!audit || !root.includes('/uzu-pi-coding-')) throw new Error('Missing isolated coding fixture');
  let calls = 0;
  const record = data => fs.appendFileSync(audit, JSON.stringify(data) + '\n', {mode:0o600});
  pi.registerTool({
    name:'run_tests', label:'Run isolated tests',
    description:'Run the fixed read-only cache.test.cjs suite. No arguments and no shell.',
    parameters:Type.Object({}, {additionalProperties:false}),
    async execute(_id, _params, signal) {
      const args = ['-p', testSandbox(root), process.execPath,
        '--test', '--test-isolation=none', '--test-reporter=tap', 'cache.test.cjs'];
      let text, code;
      try {
        const result = await execute('/usr/bin/sandbox-exec', args,
          {cwd:root,env:{PATH:'/usr/bin:/bin'},timeout:10000,maxBuffer:64000,signal});
        text = result.stdout + result.stderr; code = 0;
      } catch (error) {
        text = String(error.stdout || '') + String(error.stderr || '') + String(error.message || '');
        code = Number.isInteger(error.code) ? error.code : -1;
      }
      const complete = /^# tests 8$/m.test(text) && /^# pass 8$/m.test(text)
        && /^# fail 0$/m.test(text) && /^# cancelled 0$/m.test(text) && /^# skipped 0$/m.test(text);
      if (code === 0 && !complete) code = -2;
      record({kind:'tests',code,complete,failedTests:text.split('\n').filter(line => /^not ok \d+ - /.test(line))});
      return {content:[{type:'text',text:`Test exit code: ${code}\n${text}`}],details:{code},isError:code !== 0};
    },
  });
  pi.on('session_start', () => pi.setActiveTools(['read','edit','write','run_tests']));
  pi.on('before_provider_request', event => {
    const names = (event.payload?.tools || []).map(t => t.function?.name).sort();
    if (JSON.stringify(names) !== JSON.stringify(['edit','read','run_tests','write'])) throw new Error('Unexpected coding-test tools on wire');
  });
  pi.on('tool_call', event => {
    let allowed = false;
    try { allowed = ++calls <= 24 && (event.toolName === 'run_tests'
      || fileToolAllowed(root, event.toolName, event.input)); } catch {}
    record({kind:'tool',name:event.toolName,allowed});
    if (!allowed) return {block:true,terminate:true,reason:'This test allows only the two fixture files and fixed run_tests tool.'};
  });
}
