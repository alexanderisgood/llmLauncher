import {opendir, open} from 'node:fs/promises';
import {constants as fsConstants} from 'node:fs';
import {createHash} from 'node:crypto';
import {join} from 'node:path';

const excluded = new Set(['node_modules', 'vendor', 'dist', 'build', 'coverage', '__pycache__']);
const sourceFile = /\.(?:[cm]?[jt]sx?|html?|css|scss|vue|svelte|py|rs|go|c|cpp|h|swift|java|cs|glsl|wgsl)$/i;

// Bounded actual source observation. Unknown/oversized trees never count as unchanged.
export async function projectSourceFingerprint(cwd) {
  if (!cwd) return null;
  const files = [];
  let entries = 0;
  async function walk(dir, depth) {
    const handle = await opendir(dir);
    try {
      for await (const item of handle) {
        if (++entries > 4000) throw new Error('tree limit');
        if (item.name.startsWith('.') || excluded.has(item.name)) continue;
        const path = join(dir, item.name);
        if (item.isDirectory()) {
          if (depth >= 8) throw new Error('depth limit');
          await walk(path, depth + 1);
        } else if (item.isFile() && sourceFile.test(item.name)) files.push(path);
      }
    } finally {
      // Async iteration normally closes the directory. Ignore the duplicate-close
      // error when an exception stops the walk before iteration can do so.
      await handle.close().catch(() => {});
    }
  }
  try {
    await walk(cwd, 0);
    const hash = createHash('sha256');
    let bytes = 0;
    for (const file of files.sort()) {
      // Avoid following a raced symlink and avoid blocking forever if a path is
      // replaced with a FIFO between directory enumeration and this open.
      const handle = await open(file, fsConstants.O_RDONLY | fsConstants.O_NONBLOCK | fsConstants.O_NOFOLLOW);
      let data;
      try {
        const before = await handle.stat();
        if (!before.isFile() || !Number.isSafeInteger(before.size) || before.size < 0
            || before.size > 2 * 1024 * 1024 || bytes + before.size > 8 * 1024 * 1024) return null;
        const buffer = Buffer.alloc(before.size + 1);
        const {bytesRead} = await handle.read(buffer, 0, buffer.length, 0);
        const after = await handle.stat();
        if (bytesRead !== before.size || after.mtimeMs !== before.mtimeMs || after.size !== before.size) return null;
        data = buffer.subarray(0, bytesRead); bytes += bytesRead;
      } finally { await handle.close(); }
      hash.update(file).update('\0').update(data).update('\0');
    }
    return {hash:hash.digest('hex'), files:files.length};
  } catch { return null; }
}

export function implementationRequest(text) {
  if (/^\s*(?:(?:ok|yes|please)[, .!]*\s*)?(?:continue|resume|keep (?:going|working))(?: please)?[.! ]*$/i.test(text)) return undefined;
  if (/\b(?:monitor|watch|poll)\b/i.test(text)) return false;
  if (/\b(?:research|review|explain|inspect|analyse|analyze|monitor|watch)\b/i.test(text)
      && !/\b(?:implement|build|recreate|develop|fix|improve|add)\b/i.test(text)) return false;
  if (/\b(?:do not|don't|don’t)\s+(?:edit|change|implement|write)\b|\bplan only\b/i.test(text)) return false;
  return /\b(?:implement|build|recreate|develop|fix|improve|add)\b/i.test(text);
}

export function createDeliveryProgressCheck({now = Date.now, snapshot = projectSourceFingerprint} = {}) {
  let enabled = false, baseline = null, since = 0, calls = 0, checked = 0, notified = false;
  let generation = 0;
  return {
    reset(implementation) {
      generation++;
      enabled = implementation ?? enabled; baseline = null; since = now(); calls = 0; checked = 0; notified = false;
    },
    async observe(cwd, completedCalls = 0) {
      if (!enabled || notified) return;
      const observedGeneration = generation;
      calls += completedCalls;
      const time = now();
      if (baseline && time - checked < 60000) return;
      checked = time;
      let current;
      try { current = await snapshot(cwd); } catch { current = null; }
      // A new input, compaction, or session reset invalidates work that was
      // still awaiting the filesystem. It must not notify the new input.
      if (observedGeneration !== generation) return;
      if (!current || typeof current !== 'object' || typeof current.hash !== 'string'
          || !Number.isInteger(current.files) || current.files < 0) current = null;
      if (!current) { baseline = null; since = time; calls = 0; return; }
      if (!baseline || baseline.hash !== current.hash) {
        baseline = current; since = time; calls = 0; return;
      }
      if (time - since < 15 * 60000 || calls < 12) return;
      notified = true;
      return {minutes:Math.floor((time - since) / 60000), completedTools:calls, sourceFiles:current.files};
    },
  };
}

// Native Pi has no default. Explicit finite deadlines remain available for long builds/downloads.
export function applyBashDeadline(event, builtin) {
  if (builtin && event.toolName === 'bash' && event.input && event.input.timeout === undefined) {
    event.input.timeout = 120;
  }
}
