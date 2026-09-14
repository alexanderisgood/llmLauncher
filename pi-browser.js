import {createRequire} from 'node:module';
import {mkdir, mkdtemp, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
import {Script} from 'node:vm';

const require = createRequire(import.meta.url);
const evidenceFor = kind => ({
  kind,
  imageDelivered:kind === 'visual-model',
});
const runtimeEvidence = evidenceFor('runtime');
const textResult = (value, evidence = runtimeEvidence) => ({
  content:[{type:'text', text:JSON.stringify({...value, evidence})}],
  details:{evidence},
});
const sequenceEvidence = results => ({
  kind:'sequence',
  imageDelivered:results.some(result => result.evidence?.imageDelivered === true),
});
const actions = ['open','inspect','resize','screenshot','click','fill','press','evaluate','close'];
const requiredFields = {
  open:['url'], inspect:[], resize:['width','height'], screenshot:[], click:['selector'], fill:['selector','text'],
  press:['key'], evaluate:['script'], close:[], sequence:['steps'],
};
const actionProperties = {
  action:{type:'string', enum:actions},
  url:{type:'string', minLength:1, description:'Required for open: http(s) or file URL.'},
  selector:{type:'string', minLength:1, description:'Required for click/fill, optional for screenshot: a Playwright locator selector. Screenshot otherwise captures the viewport.'},
  text:{type:'string', description:'For fill: input text.'},
  key:{type:'string', minLength:1, description:'Required for press: key such as Enter, Space, ArrowRight, or Shift+ArrowRight.'},
  hold_ms:{type:'integer', minimum:0, maximum:3000, description:'For press: how long to hold the key.'},
  wait_for:{type:'string', minLength:1, maxLength:12000, description:'Optional for press/click/fill: a page JavaScript expression that must become truthy after input, such as state === "play". Waits up to 8 seconds within the existing action and sequence deadlines.'},
  width:{type:'integer', minimum:320, maximum:2560, description:'Required for resize: the real browser viewport width in CSS pixels.'},
  height:{type:'integer', minimum:240, maximum:1600, description:'Required for resize: the real browser viewport height in CSS pixels.'},
  script:{type:'string', minLength:1, maxLength:12000, description:'Required for evaluate: JavaScript expression evaluated in the page. Return concise measurements; assertions should throw on failure.'},
};
const actionAlternatives = names => names.map(action => ({
  properties:{action:{const:action}}, required:requiredFields[action],
}));

function validateArguments(args, nested = false) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('Provide a browser action object.');
  if (nested && (args.action === 'sequence' || 'steps' in args)) {
    throw new Error('Use an existing action; sequences cannot be nested.');
  }
  if (!Object.hasOwn(requiredFields, args.action)) throw new Error('Unknown browser action.');
  for (const field of Object.keys(args)) {
    if (field === 'steps' && args.action === 'sequence') continue;
    const schema = Object.hasOwn(actionProperties, field) && actionProperties[field];
    if (!schema) throw new Error(`Unknown browser argument: ${field}.`);
    if (schema.type === 'string' && typeof args[field] !== 'string') throw new Error(`${field} must be a string.`);
    if (schema.minLength && !args[field].trim()) throw new Error(`Provide a non-empty ${field}.`);
    if (schema.maxLength && args[field].length > schema.maxLength) throw new Error(`${field} must be at most ${schema.maxLength} characters.`);
    if (schema.type === 'integer' && (!Number.isInteger(args[field]) || args[field] < schema.minimum || args[field] > schema.maximum)) {
      throw new Error(`${field} must be an integer from ${schema.minimum} to ${schema.maximum}.`);
    }
  }
  for (const field of requiredFields[args.action]) {
    if (!Object.hasOwn(args, field)) throw new Error(`Provide ${field} for ${args.action}.`);
  }
  if (Object.hasOwn(args, 'wait_for') && !['press','click','fill'].includes(args.action)) {
    throw new Error('wait_for is supported only after press, click or fill.');
  }
  if (args.action === 'open') {
    let url;
    try { url = new URL(args.url); } catch { throw new Error('Use a valid http, https or file URL.'); }
    if (!['http:', 'https:', 'file:'].includes(url.protocol)) throw new Error('Use an http, https or file URL.');
  }
  if (args.action === 'evaluate') {
    // Validate only: never execute page code in Node. Catch incomplete generated
    // scripts before earlier sequence steps can change the page.
    try { new Script(args.script); }
    catch (error) {
      try { new Script(`(${args.script})`); }
      catch {
        throw new Error(`Invalid evaluate JavaScript: ${error.message}. Send a complete short expression or async IIFE, not a truncated source function.`);
      }
    }
  }
  if (args.action === 'sequence') {
    if (!Array.isArray(args.steps) || args.steps.length < 1 || args.steps.length > 12) {
      throw new Error('A browser sequence needs 1 to 12 steps.');
    }
    for (const [index, step] of args.steps.entries()) {
      try { validateArguments(step, true); }
      catch (error) { throw new Error(`Invalid browser sequence step ${index + 1} (${step?.action || 'unknown'}): ${error.message}`); }
    }
  }
}

/** One private browser per Pi session. Never attaches to the user's browser. */
export function createBrowserCheck(modulePath, {load = require, timeout = 20000, sequenceTimeout = 120000, artifactDir} = {}) {
  let browser, page, launching, tail = Promise.resolve();
  let errors = [], disposed = false;
  let screenshotDirectory;

  async function screenshotPath() {
    if (!screenshotDirectory) {
      screenshotDirectory = artifactDir ? resolve(artifactDir) : await mkdtemp(join(tmpdir(), 'pi-browser-artifacts-'));
      await mkdir(screenshotDirectory, {recursive:true});
    }
    return join(screenshotDirectory, `${Date.now()}-${randomUUID().slice(0, 8)}.png`);
  }

  async function screenshotImage(png) {
    // Keep the original screenshot for the Hub. Bound the model copy without
    // resizing the live page (which could change the behaviour being tested).
    const width = png.readUInt32BE(16), height = png.readUInt32BE(20);
    if (Math.max(width, height) <= 1280 && png.length <= 512 * 1024) {
      return {image:{type:'image', data:png.toString('base64'), mimeType:'image/png'}, width, height};
    }
    const context = await browser.newContext();
    try {
      // A new blank page keeps the site's scripts from intercepting image work.
      const imagePage = await context.newPage();
      const resized = await imagePage.evaluate(async encoded => {
        const response = await fetch(`data:image/png;base64,${encoded}`);
        const bitmap = await createImageBitmap(await response.blob());
        try {
          const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(bitmap.width * scale));
          canvas.height = Math.max(1, Math.round(bitmap.height * scale));
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
          return {data:canvas.toDataURL('image/jpeg', 0.82).split(',')[1], width:canvas.width, height:canvas.height};
        } finally { bitmap.close(); }
      }, png.toString('base64'));
      if (Buffer.byteLength(resized.data, 'base64') > 2 * 1024 ** 2) {
        throw new Error('The image preview exceeds 2 MiB after resizing. Use a smaller screenshot selector.');
      }
      return {image:{type:'image', data:resized.data, mimeType:'image/jpeg'}, width:resized.width, height:resized.height};
    } finally { await context.close(); }
  }

  async function inspectPage(compact) {
    const structure = await page.evaluate(() => {
      const box = node => {
        const r = node.getBoundingClientRect();
        return {x:Math.round(r.x), y:Math.round(r.y), width:Math.round(r.width), height:Math.round(r.height)};
      };
      const visible = node => {
        const r = node.getBoundingClientRect(), style = getComputedStyle(node);
        return r.width > 0 && r.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
      };
      const canvases = [...document.querySelectorAll('canvas')];
      const controls = [...document.querySelectorAll('button,input,textarea,select,a[href],[role="button"]')].filter(visible);
      return {
        viewport:{width:innerWidth, height:innerHeight, devicePixelRatio},
        readyState:document.readyState,
        canvases:canvases.slice(0, 8).map(node => ({
          selector:node.id ? `#${CSS.escape(node.id)}` : null,
          width:node.width, height:node.height, displayed:box(node), visible:visible(node),
        })),
        controls:controls.slice(0, 20).map(node => ({
          selector:node.id ? `#${CSS.escape(node.id)}` : null,
          tag:node.tagName.toLowerCase(), type:node.getAttribute('type'),
          label:(node.getAttribute('aria-label') || node.labels?.[0]?.innerText || node.innerText || node.getAttribute('placeholder') || '').slice(0, 120),
          disabled:Boolean(node.disabled),
        })),
        failedImages:[...document.images].filter(node => node.complete && !node.naturalWidth).slice(0, 8).map(node => node.currentSrc.slice(0, 300)),
        ...(canvases.length > 8 || controls.length > 20 ? {structureTruncated:true} : {}),
      };
    });
    return {url:page.url().slice(0, 1000), title:(await page.title()).slice(0, 200),
      text:(await page.locator('body').innerText()).slice(0, compact ? 1500 : 6000),
      ...structure, errors:compact ? errors.slice(-3).map(e => e.slice(0, 200)) : errors};
  }

  async function close() {
    const owned = browser || await launching?.catch(() => null);
    browser = page = launching = null;
    errors = [];
    if (owned) await owned.close().catch(() => {});
  }

  async function perform(args, signal, compact = false, remaining = Infinity, imageInput = false) {
    if (disposed) throw new Error('This browser session has ended.');
    signal?.throwIfAborted();
    let timer, rejectCancelled;
    const cancelled = new Promise((_, reject) => { rejectCancelled = reject; });
    const interrupt = reason => {
      // Closing the owned browser also interrupts a stuck page.evaluate().
      void close().finally(() => rejectCancelled(reason));
    };
    const abort = () => interrupt(new Error('Browser check cancelled. Its private browser was closed.'));
    signal?.addEventListener('abort', abort, {once:true});
    timer = setTimeout(() => interrupt(new Error(remaining < timeout
      ? 'Browser sequence timed out. Open the page again and use fewer or shorter steps.'
      : 'Browser check timed out. Open the page again and use a smaller check.')), Math.min(timeout, remaining));
    try {
      return await Promise.race([cancelled, (async () => {
        if (args.action === 'close') {
          await close();
          return textResult({closed:true});
        }
        if (args.action === 'open') {
          const url = new URL(args.url);
          if (browser && (!browser.isConnected() || !page || page.isClosed())) await close();
          if (!browser) {
            try {
              launching = load(modulePath).chromium.launch({headless:true, timeout:10000});
              browser = await launching;
              launching = null;
              signal?.throwIfAborted();
              const context = await browser.newContext({viewport:{width:1280,height:800}});
              page = await context.newPage();
              page.setDefaultTimeout(8000);
              page.on('pageerror', error => { errors.push(String(error.message).slice(0, 500)); errors = errors.slice(-12); });
              page.on('console', message => {
                if (message.type() === 'error') {
                  errors.push(`Console: ${message.text().slice(0, 500)}`); errors = errors.slice(-12);
                }
              });
            } catch (error) {
              // A launched browser with no usable page must not poison the next open.
              await close();
              throw error;
            }
          }
          errors = [];
          await page.goto(url.href, {waitUntil:'domcontentloaded', timeout:10000});
        } else if (!page || page.isClosed()) {
          throw new Error('Open a page with browser_check first. This tool owns a separate headless Chromium browser.');
        }
        switch (args.action) {
          case 'open': case 'inspect': break;
          case 'resize': await page.setViewportSize({width:args.width,height:args.height}); break;
          case 'screenshot': {
            const target = args.selector ? page.locator(args.selector) : page;
            if (args.selector) {
              const bounds = await target.boundingBox();
              if (!bounds || bounds.width <= 0 || bounds.height <= 0) throw new Error('The screenshot element is not visible. Use inspect to check its selector.');
              if (bounds.width > 4096 || bounds.height > 4096 || bounds.width * bounds.height > 8000000) {
                throw new Error('The screenshot element is too large. Omit selector to capture the viewport.');
              }
            }
            const png = await target.screenshot({type:'png', timeout:8000, ...(args.selector ? {} : {fullPage:false})});
            if (png.length > 10 * 1024 ** 2) {
              throw new Error('The screenshot exceeds the 10 MiB preview limit. Resize to a smaller viewport or select a smaller element, then capture again. No screenshot was saved.');
            }
            signal?.throwIfAborted();
            const path = await screenshotPath();
            await writeFile(path, png, {flag:'wx'});
            const preview = imageInput ? await screenshotImage(png) : null;
            const evidence = evidenceFor(preview ? 'visual-model' : 'human-review');
            const result = textResult({
              saved:true, path, mimeType:'image/png', bytes:png.length,
              visualFeedback:preview ? 'image' : 'unavailable',
              ...(preview ? {imageWidth:preview.width, imageHeight:preview.height} : {}),
              note:preview
                ? 'The following image is this screenshot. Inspect it for the specific visual question; runtime assertions and image appearance are separate evidence. The original PNG remains saved for the Hub.'
                : 'Saved locally for human review. This text-only route cannot see screenshot pixels; do not claim visual inspection. Use inspect/evaluate for specific runtime questions. Pixel grids or a hand-written image decoder do not replace visual review. If appearance is the remaining question, report that limitation rather than repeatedly reconstructing the image as text. Do not upload screenshots or search for image-analysis services.',
              ...(compact ? {} : {page:await inspectPage(false)}),
            }, evidence);
            if (preview) result.content.push(preview.image);
            result.details.screenshot = {path, mimeType:'image/png'};
            return result;
          }
          case 'click': await page.locator(args.selector).click(); break;
          case 'fill': await page.locator(args.selector).fill(args.text); break;
          case 'press': await page.keyboard.press(args.key, {delay:args.hold_ms ?? 0}); break;
          case 'evaluate': {
            const value = await page.evaluate(args.script);
            const encoded = JSON.stringify(value ?? null);
            const limit = compact ? 1500 : 10000;
            const notes = [];
            if (value === undefined) notes.push('The script ran but returned no value. A thrown assertion would fail this tool. Return a concise object when you need measurements; null here is not a measured result.');
            if (!imageInput) notes.push('Runtime and pixel diagnostics do not verify visual appearance; use a screenshot for human review.');
            return textResult({...(compact ? {} : {browser:'Chromium', url:page.url()}),
              result:encoded.length <= limit ? (value ?? null) : encoded.slice(0, limit),
              ...(notes.length ? {note:notes.join(' ')} : {}),
              truncated:encoded.length > limit, errors:compact ? errors.slice(-3).map(e => e.slice(0, 200)) : errors});
          }
          default: throw new Error('Unknown browser action.');
        }
        if (args.wait_for) {
          const matched = await page.waitForFunction(args.wait_for, null, {timeout:8000});
          await matched.dispose();
        }
        if (compact) {
          if (args.action === 'inspect' || args.action === 'resize') return textResult({ok:true, ...await inspectPage(true)});
          return textResult({ok:true,
            ...(args.wait_for ? {postcondition:'satisfied'} : {}),
            ...(args.action === 'open' ? {url:page.url().slice(0, 500), title:(await page.title()).slice(0, 200)} : {}),
            ...(errors.length ? {errors:errors.slice(-3).map(e => e.slice(0, 200))} : {})});
        }
        if (args.action === 'open' || args.action === 'inspect' || args.action === 'resize') {
          return textResult({browser:'Chromium', ...await inspectPage(false),
            ...(args.action === 'open' ? {capability:imageInput
              ? 'DOM, trusted input, page JavaScript and screenshot images. Use screenshot for actual appearance and evaluate for focused state/runtime assertions; canvas contents are not DOM text.'
              : 'DOM, trusted input, page JavaScript and local screenshot files. No visual model on this route; canvas contents are not DOM text. Use evaluate for game state/runtime assertions and screenshot for human review. Do not reconstruct screenshots as pixel grids to guess visual quality.'} : {})});
        }
        return textResult({browser:'Chromium', url:page.url(), title:await page.title(),
          ...(args.wait_for ? {postcondition:'satisfied'} : {}), errors});
      })()]);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }

  async function run(args, signal, {imageInput = false} = {}) {
    // Reject every malformed step before any earlier navigation or input occurs.
    validateArguments(args);
    if (args.action !== 'sequence') return perform(args, signal, false, Infinity, imageInput);
    const results = [];
    const images = [];
    // Twelve quick actions share the old six-action worst-case duration.
    const deadline = performance.now() + sequenceTimeout;
    for (const [index, step] of args.steps.entries()) {
      try {
        const remaining = deadline - performance.now();
        if (remaining <= 0) {
          await close();
          throw new Error('Browser sequence timed out. Open the page again and use fewer or shorter steps.');
        }
        const result = await perform(step, signal, true, remaining, imageInput);
        const stepImages = result.content.filter(block => block.type === 'image');
        results.push({step:index + 1, action:step.action, ...JSON.parse(result.content[0].text),
          ...(stepImages.length ? {imageIndex:images.length + 1} : {})});
        // Keep one JSON text block so the existing Hub can still discover the
        // original screenshots. imageIndex maps sequence steps to image order.
        images.push(...stepImages);
      } catch (error) {
        throw new Error(`Browser sequence step ${index + 1} (${step.action}) failed: ${error.message || error}`);
      }
    }
    const result = textResult({browser:'Chromium', results}, sequenceEvidence(results));
    result.content.push(...images);
    return result;
  }

  return {
    execute(args, signal, options) {
      // Pi may dispatch sibling tools together; one page requires ordered actions.
      const pending = tail.catch(() => {}).then(() => run(args, signal, options));
      tail = pending.catch(() => {});
      return pending;
    },
    close,
    async dispose() { disposed = true; await close(); },
  };
}

export function registerBrowserCheck(pi, provider) {
  if (!provider.browserTestModule) return;
  const browser = createBrowserCheck(provider.browserTestModule, {artifactDir:provider.browserArtifactDir});
  const imageInput = provider.model?.input?.includes('image') === true;
  pi.registerTool({
    name:'browser_check', label:'Browser check',
    description:'Ready-to-use local browser: open a URL, inspect DOM and canvas dimensions, resize the viewport, interact, evaluate page JavaScript, or capture a screenshot. The private headless Chromium page persists between calls; no setup script or browser installation is needed. ' + (imageInput ? 'Screenshots include a bounded image preview for the vision model.' : 'This text-only route cannot see screenshot pixels; screenshots are saved for human review.') + ' Passing runtime checks do not establish visual quality or Safari compatibility.',
    promptSnippet:'Open and test web pages in a private browser',
    promptGuidelines:[
      'For browser behaviour, use browser_check early to gather a real result before designing a large test script. Start with a small check and extend it based on the result.',
      imageInput
        ? 'For visual questions, capture action:"screenshot", optionally selector:"#canvas-id", and inspect the returned image. Use one screenshot to answer a specific question, then change or verify the real source. Use evaluate for focused runtime assertions; do not reconstruct pictures as large pixel grids or write image decoders. The original screenshot remains local for human review. Do not install browsers, hunt executable paths, upload images, or use remote image-analysis workarounds.'
        : 'This route has no image understanding. Use inspect for DOM/controls/canvas dimensions and evaluate for runtime state, errors and focused assertions. Save screenshots with action:"screenshot" for human review, optionally selector:"#canvas-id". Screenshots stay local and are not visual evidence to you. Do not reconstruct pictures as large pixel grids or write image decoders to guess visual quality. Continue source work supported by real evidence and report any remaining visual review limitation. Do not install browsers, hunt executable paths, upload images, or use remote image-analysis workarounds.',
      'Use browser_check press, click and fill for user input. These use browser automation input; dispatchEvent from evaluate is synthetic and does not prove gesture-gated behaviour such as audio autoplay.',
      'Input completion does not mean an animation frame or asynchronous UI transition has completed. For games and async UI, add wait_for to press/click/fill using an observed application condition, for example press Enter with wait_for:"state === \\"play\\" && player.onGround". The next sequence step runs after that condition is true. Use actual application state, not fixed sleeps or guessed conditions; a failed immediate state check alone does not establish that requestAnimationFrame is broken.',
      'For responsive checks, use action:"resize", width:390, height:844 (or another supported size), then inspect/evaluate/screenshot the actual page. Resize changes the real browser viewport and media queries; CSS body width or an iframe is not equivalent. It also works in sequence. Restore the desktop viewport with width:1280, height:800 when needed.',
      'For timing-sensitive checks, use action:"sequence" with up to 12 existing actions in steps. Keep start, baseline, movement, jump, result checks and screenshots in one call so a running game does not drift while you think between calls. Steps run without model delay between them, stop on the first error, and return concise measurements. Sequences cannot be nested.',
      'browser_check evaluate accepts an expression, for example ({title:document.title}) or an async IIFE. It has page globals, not Node require or Playwright. Use native tools to edit source. Close the private browser when finished.',
    ],
    parameters:{type:'object', additionalProperties:false, anyOf:actionAlternatives([...actions, 'sequence']),
      required:['action'], properties:{
        ...actionProperties,
        action:{type:'string', enum:[...actions, 'sequence']},
        steps:{type:'array', minItems:1, maxItems:12,
          description:'For sequence: ordered existing actions, with no model delay between steps. Stops at the first failure. No nested sequences.',
          items:{type:'object', additionalProperties:false, required:['action'], properties:actionProperties, anyOf:actionAlternatives(actions)}},
      }},
    // Pi marks rejected executions as failed; an isError field on a resolved
    // result is ignored by its agent loop and would disguise failed checks.
    async execute(_id, args, signal, _onUpdate, ctx) {
      try { return await browser.execute(args, signal, {imageInput:ctx?.model?.input?.includes('image') === true}); }
      catch (error) {
        // Page assertions can include large serialized objects. Keep failures
        // bounded too, without turning them into successful tool results.
        const message = String(error?.message || error);
        const suffix = '… [truncated]';
        throw new Error(message.length > 2000 ? message.slice(0, 2000 - suffix.length) + suffix : message);
      }
    },
  });
  pi.on('session_shutdown', () => browser.dispose());
}
