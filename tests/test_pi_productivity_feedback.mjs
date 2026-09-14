import assert from 'node:assert/strict';
import test from 'node:test';
import install, {downloadedImageEvidence} from '../pi-workflow.js';

const failedDownload = () => ({toolName:'bash', isError:false,
  input:{command:'cd /tmp && curl -sL -o reference.png "https://fixture.test/file.png" && file reference.png'},
  content:[{type:'text',text:'reference.png: HTML document text, ASCII text, with CRLF line terminators\n'}],
  details:{exitCode:0},
});

test('Successful shell exit does not disguise an HTML response saved as an image', () => {
  const event = failedDownload();
  assert.deepEqual(downloadedImageEvidence(event), ['reference.png']);
  event.content[0].text += '/tmp/other image.webp:     HTML document, UTF-8 Unicode text\n';
  assert.deepEqual(downloadedImageEvidence(event), ['reference.png','/tmp/other image.webp']);
});

test('Real images, deliberate HTML downloads and unobserved failures are left alone', () => {
  for (const text of [
    'reference.png: PNG image data, 45 x 61, 8-bit/color RGBA, non-interlaced',
    'reference.html: HTML document text',
    'curl: (22) The requested URL returned error: 404',
    'The documentation says downloaded images could contain an HTML document.',
    'reference.png: HTML document text\n' + 'x'.repeat(128 * 1024),
  ]) {
    const event = failedDownload(); event.content[0].text = text;
    assert.deepEqual(downloadedImageEvidence(event), []);
  }
  const inspection = failedDownload(); inspection.input.command = 'file reference.png';
  assert.deepEqual(downloadedImageEvidence(inspection), [], 'An ordinary file inspection is not a failed download');
});

test('Native result receives evidence in the existing turn, with no steering, retries or mutations', async () => {
  const hooks = new Map(), messages = [];
  let source = 'builtin';
  install({on:(name, handler)=>hooks.set(name, handler),
    sendMessage:(...args)=>messages.push(args),
    getAllTools:()=>[{name:'bash', sourceInfo:{source}}], getActiveTools:()=>['bash']});
  const event = failedDownload(), original = structuredClone(event);
  const result = await hooks.get('tool_result')(event, {});
  assert.deepEqual(event, original, 'Original transcript evidence must remain intact');
  assert.equal(result.content[0], event.content[0]);
  assert.match(result.content[1].text, /not usable image assets/);
  assert.match(result.content[1].text, /actual image link/);
  assert.equal(result.details.exitCode, 0, 'Do not claim the shell command failed');
  assert.deepEqual(result.details.launcherDownloadEvidence.unusableImages, ['reference.png']);
  assert.deepEqual(messages, [], 'Evidence belongs in the natural result, not an injected model turn');
  source = 'extension';
  assert.equal(await hooks.get('tool_result')(event, {}), undefined, 'Custom shell tools remain untouched');
});
