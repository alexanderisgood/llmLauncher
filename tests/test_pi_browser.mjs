import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readFile, readdir, stat, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createBrowserCheck, registerBrowserCheck} from '../pi-browser.js';

// Invalid later arguments must be rejected before an earlier step changes a page.
{
  const mutations = [];
  const check = createBrowserCheck('fixture', {load:() => ({chromium:{async launch() {
    mutations.push('launch');
    const page = {
      isClosed:() => false, setDefaultTimeout() {}, on() {},
      async goto(url) { mutations.push(url); },
      url:() => 'https://fixture.test/', title:async () => 'Fixture',
      evaluate:async () => ({}),
      locator:() => ({innerText:async () => 'Ready'}),
    };
    return {isConnected:() => true, async close() {},
      newContext:async () => ({newPage:async () => page})};
  }}})});
  try {
    for (const [invalid, error] of [
      [{action:'evaluate'}, /script/],
      [{action:'evaluate',script:' '.repeat(3)}, /script/],
      [{action:'evaluate',script:'x'.repeat(12001)}, /12000/],
      [{action:'evaluate',script:'(() => { const colour = "red";'}, /Invalid evaluate JavaScript.*complete short expression/],
      [{action:'open'}, /url/],
      [{action:'open',url:'relative.html'}, /URL/],
      [{action:'open',url:'javascript:void(0)'}, /URL/],
      [{action:'click'}, /selector/],
      [{action:'click',selector:' '}, /selector/],
      [{action:'fill',selector:'input'}, /text/],
      [{action:'fill',selector:'input',text:null}, /text/],
      [{action:'press'}, /key/],
      [{action:'press',key:'Enter',hold_ms:3001}, /hold_ms/],
      [{action:'press',key:'Enter',hold_ms:0.5}, /hold_ms/],
      [{action:'resize'}, /width/],
      [{action:'resize',width:390}, /height/],
      [{action:'resize',width:319,height:800}, /width/],
      [{action:'resize',width:2561,height:800}, /width/],
      [{action:'resize',width:390,height:239}, /height/],
      [{action:'resize',width:390,height:1601}, /height/],
      [{action:'resize',width:390.5,height:800}, /width/],
      [{action:'press',key:'Enter',wait_for:' '}, /wait_for/],
      [{action:'press',key:'Enter',wait_for:42}, /wait_for/],
      [{action:'press',key:'Enter',wait_for:'x'.repeat(12001)}, /12000/],
      [{action:'inspect',wait_for:'true'}, /only after press, click or fill/],
      [{action:'inspect',typo:true}, /typo/],
    ]) {
      await assert.rejects(check.execute({action:'sequence', steps:[
        {action:'open',url:'https://fixture.test/'}, invalid,
      ]}), failure => /step 2/.test(failure.message) && error.test(failure.message));
      await assert.rejects(check.execute(invalid), error);
      assert.deepEqual(mutations, [], 'Malformed arguments must not launch or navigate');
    }
  } finally { await check.dispose(); }
}

// Partial startup failures must release Chromium and allow an ordinary open retry.
for (const failure of ['context', 'page']) {
  let launches = 0, closes = 0, currentPage;
  const check = createBrowserCheck('fixture', {load:() => ({chromium:{async launch() {
    const attempt = ++launches;
    return {
      isConnected:() => true,
      async close() { closes++; },
      async newContext() {
        if (attempt === 1 && failure === 'context') throw new Error('Context allocation failed');
        return {async newPage() {
          if (attempt === 1 && failure === 'page') throw new Error('Page allocation failed');
          currentPage = {closed:false, isClosed() { return this.closed; },
            setDefaultTimeout() {}, on() {}, async goto() {},
            url:() => 'https://fixture.test/', title:async () => 'Recovered',
            evaluate:async () => ({}),
            locator:() => ({innerText:async () => 'Ready'})};
          return currentPage;
        }};
      },
    };
  }}})});
  try {
    const open = {action:'open',url:'https://fixture.test/'};
    await assert.rejects(check.execute(open), /allocation failed/);
    assert.equal(closes, 1, 'Failed initialization must close its browser');
    assert.equal(JSON.parse((await check.execute(open)).content[0].text).title, 'Recovered');
    assert.equal(launches, 2);
    currentPage.closed = true;
    await check.execute(open);
    assert.equal(launches, 3, 'Open must recover a closed page');
    assert.equal(closes, 2);
  } finally { await check.dispose(); }
  assert.equal(closes, 3);
}

// Several individually legal actions must still obey the shared sequence budget.
{
  let closes=0, lateMutation=false;
  const page = {
    isClosed:()=>false, setDefaultTimeout() {}, on() {}, async goto() {},
    url:()=> 'https://fixture.test/', title:async()=> 'Deadline fixture',
    locator:()=>({innerText:async()=> 'Ready'}),
    async evaluate(script) {
      if (script==='slow') return new Promise(resolve=>setTimeout(()=>resolve('done'),70));
      if (script==='lateMutation()') lateMutation=true;
      return {};
    },
  };
  const check = createBrowserCheck('fixture', {timeout:1000,sequenceTimeout:100,load:()=>({chromium:{launch:async()=>({
    isConnected:()=>true, close:async()=>{closes++;}, newContext:async()=>({newPage:async()=>page}),
  })}})});
  try {
    await assert.rejects(check.execute({action:'sequence',steps:[
      {action:'open',url:'https://fixture.test/'},
      {action:'evaluate',script:'slow'},
      {action:'evaluate',script:'slow'},
      {action:'evaluate',script:'lateMutation()'},
    ]}), /Browser sequence timed out/);
    assert.equal(closes,1,'The shared deadline closes the owned browser');
    assert.equal(lateMutation,false,'A sequence must not run later steps after its total deadline');
    await assert.rejects(check.execute({action:'inspect'}), /Open a page/);
  } finally { await check.dispose(); }
}

const modulePath = process.env.LLM_LAUNCHER_BROWSER_PACKAGE;

// Image feedback is per request, never sticky across a model change. Sequence
// aggregation must carry the image blocks, not silently keep only JSON text.
{
  const root = await mkdtemp(join(tmpdir(), 'pi-browser-image-gate-'));
  const png = Buffer.alloc(32); png.write('\x89PNG\r\n\x1a\n', 0, 'binary');
  png.writeUInt32BE(640, 16); png.writeUInt32BE(400, 20);
  const page = {
    isClosed:()=>false, setDefaultTimeout() {}, on() {}, async goto() {},
    url:()=> 'https://fixture.test/', title:async()=> 'Image fixture',
    evaluate:async()=>({}), locator:()=>({innerText:async()=> 'Ready'}),
    screenshot:async()=>png,
  };
  const check = createBrowserCheck('fixture', {artifactDir:root, load:()=>({chromium:{launch:async()=>({
    isConnected:()=>true, close:async()=>{}, newContext:async()=>({newPage:async()=>page}),
  })}})});
  try {
    const opened = await check.execute({action:'open',url:'https://fixture.test/'});
    assert.deepEqual(JSON.parse(opened.content[0].text).evidence,
      {kind:'runtime',imageDelivered:false});
    const vision = await check.execute({action:'screenshot'}, undefined, {imageInput:true});
    assert.equal(vision.content[1].type, 'image');
    assert.equal(vision.content[1].mimeType, 'image/png');
    assert.equal(vision.content[1].data, png.toString('base64'));
    const visionResult = JSON.parse(vision.content[0].text);
    assert.equal(visionResult.visualFeedback, 'image');
    assert.deepEqual(visionResult.evidence,
      {kind:'visual-model',imageDelivered:true});
    assert.deepEqual(vision.details.evidence, visionResult.evidence);
    const textOnly = await check.execute({action:'screenshot'});
    assert.equal(textOnly.content.length, 1, 'Text-only calls must never inherit a previous vision capability');
    const textResult = JSON.parse(textOnly.content[0].text);
    assert.equal(textResult.visualFeedback, 'unavailable');
    assert.deepEqual(textResult.evidence,
      {kind:'human-review',imageDelivered:false});
    assert.deepEqual(textOnly.details.evidence, textResult.evidence);
    const runtime = JSON.parse((await check.execute({action:'evaluate',script:'({pixels:[1,2,3]})'})).content[0].text);
    assert.deepEqual(runtime.evidence,
      {kind:'runtime',imageDelivered:false});
    assert.match(runtime.note, /pixel diagnostics do not verify visual appearance/i);
    const sequence = await check.execute({action:'sequence',steps:[
      {action:'screenshot'}, {action:'inspect'}, {action:'screenshot'},
    ]}, undefined, {imageInput:true});
    assert.deepEqual(sequence.content.map(block=>block.type), ['text','image','image']);
    const steps = JSON.parse(sequence.content[0].text).results;
    assert.equal(steps.length, 3);
    assert.equal(steps[0].imageIndex, 1);
    assert.equal(steps[2].imageIndex, 2);
    const sequenceResult = JSON.parse(sequence.content[0].text);
    assert.deepEqual(sequenceResult.evidence, {kind:'sequence',imageDelivered:true});
    assert.deepEqual(sequence.details.evidence, sequenceResult.evidence);
    assert.equal(sequenceResult.results[0].evidence.kind, 'visual-model');
    assert.equal(sequenceResult.results[1].evidence.kind, 'runtime');
  } finally { await check.dispose(); await rm(root,{recursive:true,force:true}); }
}

// The producer must obey the Hub artifact endpoint's byte limit, before writing.
{
  const root = await mkdtemp(join(tmpdir(), 'pi-browser-size-'));
  try {
    for (const size of [10 * 1024 ** 2, 10 * 1024 ** 2 + 1]) {
      const artifactDir = join(root, String(size));
      const page = {
        isClosed:()=>false, setDefaultTimeout() {}, on() {}, async goto() {},
        url:()=> 'https://fixture.test/', title:async()=> 'Size fixture',
        evaluate:async()=>({}), locator:()=>({innerText:async()=> 'Ready'}),
        screenshot:async()=>Buffer.alloc(size),
      };
      const check = createBrowserCheck('fixture', {artifactDir, load:()=>({chromium:{launch:async()=>({
        isConnected:()=>true, close:async()=>{}, newContext:async()=>({newPage:async()=>page}),
      })}})});
      try {
        await check.execute({action:'open',url:'https://fixture.test/'});
        if (size === 10 * 1024 ** 2) {
          const result = JSON.parse((await check.execute({action:'screenshot'})).content[0].text);
          assert.equal(result.saved,true);
          assert.equal((await stat(result.path)).size,size,'Exactly 10 MiB remains a valid preview artifact');
          assert.equal((await readdir(artifactDir)).length,1);
        } else {
          await assert.rejects(check.execute({action:'screenshot'}), /10 MiB.*smaller viewport.*No screenshot was saved/);
          await assert.rejects(stat(artifactDir), {code:'ENOENT'}, 'An oversized screenshot must not create an artifact directory or file');
        }
      } finally { await check.dispose(); }
    }
  } finally { await rm(root,{recursive:true,force:true}); }
}

if (!modulePath) {
  console.log('Private browser check skipped (requires an installed Playwright path).');
} else {
  const root = await mkdtemp(join(tmpdir(), 'pi-browser-check-'));
  const file = join(root, 'index.html');
  await writeFile(file, `<title>Private browser fixture</title><button id="check" onclick="requestAnimationFrame(()=>this.textContent='Clicked')">Check</button><input id="entry" aria-label="Fixture input" oninput="requestAnimationFrame(()=>window.appliedInput=this.value)">
    <canvas id="stage" width="320" height="200" style="display:block;width:640px;height:400px"></canvas>
    <script>
    const art=document.querySelector('#stage').getContext('2d'); art.fillStyle='#48a8ee'; art.fillRect(0,0,320,200);
    window.presses=[]; window.inputEvents=[]; window.position=0; window.jumps=0; window.running=false; window.rightHeld=false;
    addEventListener('keydown', event => {
      presses.push(event.key); inputEvents.push({type:event.type,key:event.key,trusted:event.isTrusted});
      if (event.key === 'Enter') requestAnimationFrame(()=>requestAnimationFrame(()=>{running=true;}));
      if (event.key === 'ArrowRight') rightHeld=true;
      if (event.key === ' ' && running) jumps++;
    });
    addEventListener('keyup', event => {
      inputEvents.push({type:event.type,key:event.key,trusted:event.isTrusted});
      if (event.key === 'ArrowRight') rightHeld=false;
    });
    setInterval(() => {
      if (running && rightHeld) position++;
      art.fillStyle='#48a8ee'; art.fillRect(0,0,320,200);
      art.fillStyle='#e84838'; art.fillRect(10+position%290,jumps?100:150,16,24);
    }, 10);
    </script>`);
  const browser = createBrowserCheck(modulePath, {artifactDir:join(root,'screenshots')});
  const value = result => JSON.parse(result.content[0].text);
  try {
    let registered, shutdown;
    registerBrowserCheck({registerTool(tool) { registered = tool; }, on(event, cb) { if (event === 'session_shutdown') shutdown = cb; }}, {browserTestModule:modulePath});
    assert.equal(registered.name, 'browser_check');
    await assert.rejects(registered.execute('no-page', {action:'evaluate',script:'1'}), /Open a page/);
    await shutdown();
    const open = {action:'open',url:pathToFileURL(file).href};
    const initial = value(await browser.execute(open));
    assert.equal(initial.title, 'Private browser fixture');
    assert.equal(initial.canvases[0].selector, '#stage');
    assert.deepEqual([initial.canvases[0].width, initial.canvases[0].height], [320,200]);
    assert.deepEqual([initial.canvases[0].displayed.width, initial.canvases[0].displayed.height], [640,400]);
    assert.equal(initial.controls.find(control=>control.selector==='#entry').label, 'Fixture input');
    assert.match(initial.capability, /No visual model/);
    assert.deepEqual(initial.evidence,
      {kind:'runtime',imageDelivered:false});
    const responsive = value(await browser.execute({action:'sequence',steps:[
      {action:'resize',width:390,height:844},
      {action:'evaluate',script:'({width:innerWidth,height:innerHeight,mobile:matchMedia("(max-width: 400px)").matches})'},
      {action:'resize',width:320,height:240},
      {action:'resize',width:1280,height:800},
      {action:'evaluate',script:'({width:innerWidth,height:innerHeight,mobile:matchMedia("(max-width: 400px)").matches})'},
    ]}));
    assert.deepEqual(responsive.results[0].viewport,{width:390,height:844,devicePixelRatio:1});
    assert.deepEqual(responsive.results[1].result,{width:390,height:844,mobile:true});
    assert.deepEqual(responsive.results[2].viewport,{width:320,height:240,devicePixelRatio:1});
    assert.deepEqual(responsive.results[3].viewport,{width:1280,height:800,devicePixelRatio:1});
    assert.deepEqual(responsive.results[4].result,{width:1280,height:800,mobile:false});
    assert.deepEqual(responsive.evidence, {kind:'sequence',imageDelivered:false});
    const runtime = value(await browser.execute({action:'evaluate',script:'({pixels:[1,2,3]})'}));
    assert.equal(runtime.evidence.kind, 'runtime');
    assert.match(runtime.note, /pixel diagnostics do not verify visual appearance/i);
    const shot = await browser.execute({action:'screenshot',selector:'#stage'});
    const saved = value(shot);
    assert.equal(saved.saved, true);
    assert.match(saved.note, /cannot see screenshot pixels/);
    assert.deepEqual(saved.evidence,
      {kind:'human-review',imageDelivered:false});
    assert.deepEqual(shot.details.evidence, saved.evidence);
    assert.equal(shot.details.screenshot.path, saved.path);
    assert.deepEqual(shot.content.map(block=>block.type), ['text'], 'Text-only screenshot results must not place image bytes in model context');
    const png = await readFile(saved.path);
    assert.equal(png.subarray(1,4).toString(), 'PNG');
    assert.deepEqual([png.readUInt32BE(16),png.readUInt32BE(20)], [640,400]);
    const visualShot = await browser.execute({action:'screenshot',selector:'#stage'}, undefined, {imageInput:true});
    assert.deepEqual(value(visualShot).evidence,
      {kind:'visual-model',imageDelivered:true});
    assert.deepEqual(visualShot.details.evidence, value(visualShot).evidence);
    assert.equal(visualShot.content[1].type,'image');
    assert.equal(visualShot.content[1].mimeType,'image/png');
    await browser.execute({action:'evaluate',script:'document.querySelector("#stage").style.width="1800px"'});
    const scaledShot = await browser.execute({action:'screenshot',selector:'#stage'}, undefined, {imageInput:true});
    const scaledInfo = value(scaledShot), scaledImage = scaledShot.content[1];
    assert.equal(scaledInfo.imageWidth,1280);
    assert.equal(scaledInfo.imageHeight,284);
    assert.equal(scaledImage.mimeType,'image/jpeg');
    assert.equal(Buffer.from(scaledImage.data,'base64').subarray(0,2).toString('hex'),'ffd8');
    assert.ok(Buffer.byteLength(scaledImage.data,'base64') < 2 * 1024 ** 2);
    const original = await readFile(scaledInfo.path);
    assert.deepEqual([original.readUInt32BE(16),original.readUInt32BE(20)],[1800,400], 'Only model copy is resized');
    const afterImage = value(await browser.execute({action:'inspect'}));
    assert.equal(afterImage.canvases[0].displayed.width,1800,'Resizing an image must not resize or navigate the tested page');
    assert.deepEqual(afterImage.viewport,{width:1280,height:800,devicePixelRatio:1});
    await browser.execute({action:'evaluate',script:'document.querySelector("#stage").style.width="640px"'});
    const viewportShot = value(await browser.execute({action:'screenshot'}));
    const viewportPng = await readFile(viewportShot.path);
    assert.deepEqual([viewportPng.readUInt32BE(16),viewportPng.readUInt32BE(20)], [1280,800]);
    assert.notEqual(saved.path, viewportShot.path, 'A later screenshot must preserve earlier evidence');
    await browser.execute({action:'evaluate',script:'console.error("Fixture runtime error")'});
    assert.ok(value(await browser.execute({action:'inspect'})).errors.includes('Console: Fixture runtime error'));
    await browser.execute({action:'evaluate',script:'document.querySelector("#stage").style.width="5000px"'});
    await assert.rejects(browser.execute({action:'screenshot',selector:'#stage'}), /too large/);
    await browser.execute({action:'evaluate',script:'document.querySelector("#stage").style.width="640px"'});
    const clickResult = value(await browser.execute({action:'click',selector:'button',wait_for:'document.querySelector("button").textContent === "Clicked"'}));
    const fillResult = value(await browser.execute({action:'fill',selector:'input',text:'Bounded check',wait_for:'window.appliedInput === "Bounded check"'}));
    const pressResult = value(await browser.execute({action:'press',key:'Enter',wait_for:'running === true'}));
    assert.equal(clickResult.postcondition,'satisfied');
    assert.equal(fillResult.postcondition,'satisfied');
    assert.equal(pressResult.postcondition,'satisfied');
    for (const result of [clickResult,fillResult,pressResult]) assert.equal(result.evidence.kind, 'runtime');
    const result = value(await browser.execute({action:'evaluate',script:'({text:document.querySelector("button").textContent,input:document.querySelector("input").value,presses,running})'}));
    assert.deepEqual(result.result, {text:'Clicked',input:'Bounded check',presses:['Enter'],running:true});
    await browser.execute({action:'fill',selector:'input',text:''});
    assert.equal(value(await browser.execute({action:'evaluate',script:'document.querySelector("input").value'})).result, '',
      'An explicitly empty fill is valid and clears the input');
    // Timing-sensitive trusted input and measurements fit in a single model call.
    const sequence = value(await browser.execute({action:'sequence',steps:[
      open,
      {action:'press',key:'Enter',wait_for:'running === true'},
      {action:'evaluate',script:'({position,running,inputEvents})'},
      {action:'press',key:'ArrowRight',hold_ms:150},
      {action:'evaluate',script:'({position,running,rightHeld,inputEvents})'},
      {action:'close'},
    ]}));
    assert.equal(sequence.results.length, 6);
    assert.deepEqual(sequence.results[2].result, {position:0,running:true,inputEvents:[
      {type:'keydown',key:'Enter',trusted:true}, {type:'keyup',key:'Enter',trusted:true},
    ]});
    assert.ok(sequence.results[4].result.position > 0, 'The held key must advance the running fixture');
    assert.equal(sequence.results[4].result.rightHeld, false);
    assert.deepEqual(sequence.results[4].result.inputEvents, [
      {type:'keydown',key:'Enter',trusted:true}, {type:'keyup',key:'Enter',trusted:true},
      {type:'keydown',key:'ArrowRight',trusted:true}, {type:'keyup',key:'ArrowRight',trusted:true},
    ]);
    assert.equal(sequence.results[5].closed, true);
    await assert.rejects(browser.execute({action:'inspect'}), /Open a page/);
    const gameplay = value(await browser.execute({action:'sequence',steps:[
      open,
      {action:'press',key:'Enter',wait_for:'running === true'},
      {action:'evaluate',script:'({position,jumps,running})'},
      {action:'press',key:'ArrowRight',hold_ms:150},
      {action:'press',key:'Space',hold_ms:50},
      {action:'evaluate',script:'({position,jumps,running,inputEvents})'},
      {action:'screenshot',selector:'#stage'},
      {action:'inspect'},
      {action:'close'},
    ]}));
    assert.equal(gameplay.results.length,9);
    assert.deepEqual(gameplay.results[2].result,{position:0,jumps:0,running:true});
    assert.ok(gameplay.results[5].result.position>0);
    assert.equal(gameplay.results[5].result.jumps,1);
    assert.equal(gameplay.results[5].result.running,true);
    assert.deepEqual(gameplay.results[5].result.inputEvents.map(event=>[event.type,event.key,event.trusted]),[
      ['keydown','Enter',true],['keyup','Enter',true],
      ['keydown','ArrowRight',true],['keyup','ArrowRight',true],
      ['keydown',' ',true],['keyup',' ',true],
    ]);
    assert.equal(gameplay.results[6].saved,true);
    assert.deepEqual(gameplay.evidence, {kind:'sequence',imageDelivered:false});
    assert.equal(gameplay.results[7].canvases[0].selector,'#stage');
    assert.equal(gameplay.results[8].closed,true);
    await browser.execute(open);
    // A sibling tool cannot interleave an action between sequence steps.
    const order = await Promise.all([
      browser.execute({action:'sequence',steps:[
        {action:'evaluate',script:'new Promise(r=>setTimeout(()=>{window.order=1;r(1)},100))'},
        {action:'evaluate',script:'++window.order'},
      ]}),
      browser.execute({action:'evaluate',script:'++window.order'}),
    ]);
    assert.deepEqual(value(order[0]).results.map(step=>step.result), [1,2]);
    assert.equal(value(order[1]).result, 3);
    await assert.rejects(browser.execute({action:'sequence',steps:[
      {action:'evaluate',script:'window.afterFailure=0'},
      {action:'evaluate',script:'(() => { throw new Error("Sequence assertion failed") })()'},
      {action:'evaluate',script:'window.afterFailure=1'},
    ]}), /step 2 \(evaluate\).*Sequence assertion failed/);
    assert.equal(value(await browser.execute({action:'evaluate',script:'window.afterFailure'})).result, 0);
    await assert.rejects(browser.execute({action:'sequence',steps:[
      {action:'evaluate',script:'window.afterFailure=1'}, {action:'fill',selector:'input'},
    ]}), /step 2.*text/);
    assert.equal(value(await browser.execute({action:'evaluate',script:'window.afterFailure'})).result, 0,
      'Invalid later arguments must leave an already-open page unchanged');
    await assert.rejects(browser.execute({action:'sequence',steps:Array(13).fill({action:'evaluate',script:'window.afterFailure=1'})}), /1 to 12 steps/);
    await assert.rejects(browser.execute({action:'sequence',steps:[
      {action:'evaluate',script:'window.afterFailure=1'}, {action:'sequence',steps:[open]},
    ]}), /step 2.*cannot be nested/);
    assert.equal(value(await browser.execute({action:'evaluate',script:'window.afterFailure'})).result, 0);
    const bounded = value(await browser.execute({action:'sequence',steps:[{action:'evaluate',script:'"x".repeat(20000)'}]}));
    assert.equal(bounded.results[0].truncated, true);
    assert.equal(bounded.results[0].result.length, 1500);
    await assert.rejects(browser.execute({action:'evaluate',script:'(() => { throw new Error("Deliberate failure") })()'}), /Deliberate failure/);
    const aborted = new AbortController();
    const pending = browser.execute({action:'sequence',steps:[{action:'evaluate',script:'new Promise(()=>{})'}, open]}, aborted.signal);
    setTimeout(()=>aborted.abort(), 100);
    await assert.rejects(pending, /step 1 \(evaluate\).*(?:cancelled|closed)/s);
    await assert.rejects(browser.execute({action:'inspect'}), /Open a page/);
    await browser.execute(open);
    assert.equal(value(await browser.execute({action:'inspect'})).title, 'Private browser fixture');
    await browser.dispose();
    await assert.rejects(browser.execute(open), /ended/);
    // A timed out expression cannot leave a renderer or operation behind.
    const timed = createBrowserCheck(modulePath, {timeout:3000});
    try {
      await assert.rejects(timed.execute({action:'sequence',steps:[open,{action:'evaluate',script:'new Promise(()=>{})'},open]}), /step 2 \(evaluate\).*(?:timed out|closed)/s);
      await assert.rejects(timed.execute({action:'inspect'}), /Open a page/);
      await timed.execute(open);
      await assert.rejects(timed.execute({action:'sequence',steps:[
        {action:'press',key:'Enter',wait_for:'false'},
        {action:'evaluate',script:'(() => { throw new Error("Unexpected later step") })()'},
      ]}), /step 1 \(press\).*(?:timed out|closed)/s);
      await assert.rejects(timed.execute({action:'inspect'}), /Open a page/,
        'A postcondition that never becomes true is bounded by the action deadline and closes its browser');
    } finally { await timed.dispose(); }
    console.log('Private browser: real page, trusted input, bounded sequences, ordering, failure recovery, abort, timeout and shutdown passed.');
  } finally { await browser.dispose(); await rm(root,{recursive:true,force:true}); }
}
