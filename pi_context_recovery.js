import {createHash} from "node:crypto";

// Detect sustained verbatim prose loops, not repeated tokens, code, lists, or
// merely lengthy reasoning. Work on a bounded tail and require substantial
// repeated material to dominate it before interrupting the model.
export function reasoningRepetition(text) {
  if (typeof text !== 'string' || text.length < 2400) return false;
  // Exclude fences before selecting the tail: its opening fence may be
  // outside the window, in which case slicing first misclassifies code.
  const tail = text.replace(/```[\s\S]*?(?:```|$)/g, '').slice(-16000);
  const paragraphs = tail.split(/\n\s*\n/).map(p => p.replace(/\s+/g, ' ').trim());
  const counts = new Map();
  for (const p of paragraphs) {
    const words = p.match(/[a-z]+/gi) || [];
    // Real Qwopus loops alternate a longer explanation with short prose
    // paragraphs. Ignoring the short members made an almost entirely copied
    // cycle score below the coverage threshold and reach the next prompt.
    if (p.length < 80 || words.length < 14 || new Set(words.map(w => w.toLowerCase())).size < 10) continue;
    counts.set(p, (counts.get(p) || 0) + 1);
  }
  let repeated = 0;
  for (const [p, count] of counts) if (count >= (p.length < 180 ? 4 : 3)) repeated += p.length * count;
  return repeated >= 2400 && repeated / Math.max(1, tail.length) >= 0.65;
}

// Older launcher versions injected this as an assistant answer. Remove exact
// echoes as well as the original loop; never teach the model to print repairs.
export const LEGACY_REASONING_MARKER = '[Repetitive reasoning omitted. Use the confirmed tool results and test the unresolved question directly.]';

export function isDamagedReasoningBlock(block) {
  const text = block.type === 'thinking' ? block.thinking || block.text || ''
    : block.type === 'text' ? block.text || '' : '';
  return text.trim() === LEGACY_REASONING_MARKER
    || (block.type === 'thinking' && reasoningRepetition(text));
}

export function recoveredReasoningContext(messages, onChanged = () => {}) {
  return messages.flatMap(message => {
    if (message.role !== 'assistant' || !Array.isArray(message.content)) return [message];
    const content = message.content.filter(block => !isDamagedReasoningBlock(block));
    if (content.length === message.content.length) return [message];
    onChanged(message);
    return content.length ? [{...message, content}] : [];
  });
}

export function cleanCompactionReasoning(preparation) {
  for (const field of ['messagesToSummarize', 'turnPrefixMessages']) {
    if (Array.isArray(preparation[field])) {
      preparation[field] = recoveredReasoningContext(preparation[field]);
    }
  }
}

function summaryContext(context, retry, maxTokens) {
  // Keep the native system prompt and serialized source intact. The relay
  // identifies housekeeping by that system prompt; changing it would enable
  // task-sized thinking/output during memory recovery.
  const words = Math.max(32, Math.min(retry ? 500 : 900, Math.floor(maxTokens * (retry ? 0.14 : 0.22))));
  const instruction = retry
    ? `The previous summary exhausted its allowance or returned no usable summary. Start a new, complete checkpoint in at most ${words} words. Do not continue or quote the partial attempt.`
    : `Write a complete checkpoint in at most ${words} words; use short bullets and finish every required section.`;
  const focus = `${instruction} Preserve the current user request, constraints, exact checkpoint markers, important file paths, verified changes and tests, unresolved failures, and the next concrete action. Distinguish verified results from plans. Omit full code, logs, and repeated reasoning; the original transcript remains saved. Do not perform the task.`;
  const messages = context.messages.map((message, index) => {
    if (index !== context.messages.length - 1 || message.role !== 'user') return message;
    const content = typeof message.content === 'string'
      ? [{type: 'text', text: message.content}] : [...message.content];
    return {...message, content: [...content, {type: 'text', text: focus}]};
  });
  return {...context, messages};
}

function addSummaryUsage(first, second) {
  if (!first) return second;
  if (!second) return first;
  const sum = (a, b) => Object.fromEntries([...new Set([...Object.keys(a), ...Object.keys(b)])]
    .map(key => [key, typeof a[key] === 'number' || typeof b[key] === 'number'
      ? (Number(a[key]) || 0) + (Number(b[key]) || 0) : b[key] ?? a[key]]));
  return {...sum(first, second), cost: sum(first.cost || {}, second.cost || {})};
}

// Native Pi calls .result() for summaries, then validates and persists the
// checkpoint itself. Retry only an incomplete/empty summary, inside that call:
// no synthetic task message, replayed task turn, or partial checkpoint.
export function compactionRecoveryStream(streamFn, onRetry = () => {}) {
  // Pi may retry a transient transport error around this stream. Remember the
  // shorter retry for that same summary so an intervening disconnect cannot
  // renew its allowance for length retries.
  const summaries = new WeakMap();
  return (model, context, options) => ({
    result: async () => {
      const bounded = {...options, maxTokens: Math.min(options.maxTokens, 4096)};
      const state = summaries.get(context) || {retried: false, usage: undefined};
      summaries.set(context, state);
      for (let attempt = 0; attempt < 2; attempt++) {
        if (options.signal?.aborted) throw new Error('Compaction cancelled');
        const stream = await streamFn(model, summaryContext(context, state.retried, bounded.maxTokens), bounded);
        const response = await stream.result();
        state.usage = addSummaryUsage(state.usage, response.usage);
        if (options.signal?.aborted || response.stopReason === 'aborted') throw new Error('Compaction cancelled');
        if (response.stopReason === 'toolUse' || response.content.some(block => block.type === 'toolCall')) {
          throw new Error('Compaction failed: the model attempted a tool call instead of returning a checkpoint. The original conversation is still saved.');
        }
        const empty = response.stopReason === 'stop'
          && !response.content.some(block => block.type === 'text' && block.text?.trim());
        if (!state.retried && (response.stopReason === 'length' || empty)) {
          state.retried = true;
          onRetry();
          continue;
        }
        if (empty) throw new Error('Compaction failed: the model returned no summary after one shorter retry. The original conversation is still saved.');
        // Length/errors still reach Pi's native failure checks.
        return {...response, usage: state.usage};
      }
    },
  });
}

export function createContextRecovery() {
  let recoveryKey = '';
  return {
    recover(messages) {
      const changed = [];
      const cleaned = recoveredReasoningContext(messages, message => changed.push(message));
      if (changed.length) {
        // MTPLX's preserve-mode cache may restore omitted thinking from its
        // committed stream. Give rewritten history a stable cache namespace
        // instead of modifying visible answers to defeat that matching.
        recoveryKey = createHash('sha256').update(JSON.stringify(changed)).digest('hex').slice(0, 24);
      }
      return cleaned;
    },
    sessionId(original) { return recoveryKey ? `${original}:recovery:${recoveryKey}` : original; },
    reset() { recoveryKey = ''; },
  };
}
