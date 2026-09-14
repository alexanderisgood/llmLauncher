"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const source = fs.readFileSync(path.join(__dirname,'fixtures/pi-coding-policy.mjs'),'utf8');
const context = {fs,path};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('export function fileToolAllowed'), source.indexOf('export default'))
  .replaceAll('export function ', 'function '), context);
const directory = fs.mkdtempSync(path.join(os.tmpdir(),'uzu-pi-coding-policy-'));
const root = path.join(fs.realpathSync(directory),'project');
fs.mkdirSync(root);
const outside = path.join(fs.realpathSync(directory),'private.txt');
fs.writeFileSync(outside,'generated sentinel');
try {
  fs.copyFileSync(path.join(__dirname,'fixtures/pi-coding/cache.cjs'),path.join(root,'cache.cjs'));
  fs.copyFileSync(path.join(__dirname,'fixtures/pi-coding/cache.test.cjs'),path.join(root,'cache.test.cjs'));
  for (const tool of ['read','edit','write']) assert.equal(context.fileToolAllowed(root,tool,{path:'cache.cjs'}),true);
  assert.equal(context.fileToolAllowed(root,'read',{path:'cache.test.cjs'}),true);
  for (const [tool,file] of [['write','cache.test.cjs'],['edit','cache.test.cjs'],['bash','cache.cjs'],
    ['read','../private.cjs'],['read','/etc/passwd']]) {
    assert.equal(context.fileToolAllowed(root,tool,{path:file}),false);
  }
  fs.renameSync(path.join(root,'cache.cjs'),path.join(root,'original.cjs'));
  fs.symlinkSync(path.join(root,'original.cjs'),path.join(root,'cache.cjs'));
  assert.equal(context.fileToolAllowed(root,'write',{path:'cache.cjs'}),false);
  fs.unlinkSync(path.join(root,'cache.cjs'));
  fs.renameSync(path.join(root,'original.cjs'),path.join(root,'cache.cjs'));
  if (process.env.LLM_LAUNCHER_PI_CODING_SANDBOX_TEST === '1') {
    const run = args => spawnSync('/usr/bin/sandbox-exec',['-p',context.testSandbox(root),process.execPath,...args],
      {cwd:root,encoding:'utf8',timeout:15000,env:{PATH:'/usr/bin:/bin'}});
    const initial = run(['--test','--test-isolation=none','--test-reporter=tap','cache.test.cjs']);
    assert.equal(initial.status,1,initial.stderr);
    assert.match(initial.stdout,/# tests 8/);
    assert.match(initial.stdout,/# fail [1-8]/);
    const forbidden = run(['-e',
      "const a=require('node:assert/strict'),f=require('node:fs');"
      +`a.throws(()=>f.readFileSync(${JSON.stringify(outside)}),e=>e.code==='EPERM');`
      +"a.throws(()=>f.writeFileSync('cache.test.cjs','changed'),e=>e.code==='EPERM');"
      +"a.throws(()=>require('node:child_process').execFileSync('/usr/bin/true'));"
      +"const s=require('node:net').createServer();s.once('error',()=>process.exit(0));s.listen(0,'127.0.0.1',()=>process.exit(1));"]);
    assert.equal(forbidden.status,0,forbidden.stderr);
    console.log('Native coding-test sandbox runs the failing fixture and denies writes, subprocesses and sockets.');
  }
  console.log('Pi coding fixture restricts file tools to its source and read-only tests, including symlink rejection.');
} finally { fs.rmSync(directory,{recursive:true,force:true}); }
