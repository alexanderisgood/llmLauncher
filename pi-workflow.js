import {createDeliveryProgressCheck, implementationRequest, applyBashDeadline} from './pi_delivery_progress.js';
import {reasoningRepetition, isDamagedReasoningBlock, createContextRecovery} from './pi_context_recovery.js';
import {registerBrowserCheck} from './pi-browser.js';
import {open} from 'node:fs/promises';
import {constants as fsConstants} from 'node:fs';
import {createHash} from 'node:crypto';
import {homedir} from 'node:os';
import {resolve} from 'node:path';
export {reasoningRepetition, recoveredReasoningContext, cleanCompactionReasoning} from './pi_context_recovery.js';

/** Launcher-owned guidance; leaves native Pi tools, queues and compaction intact. */
export const WORKFLOW_GUIDANCE = `
Launcher coding workflow:
- Follow the user's requested scope. For implementation work, use small runnable milestones: inspect the relevant code, edit, execute a focused check, then integrate.
- For implementation tasks, choose the smallest visible runnable milestone before researching dependencies. Time-box an uncertain subproblem; after two failed approaches, prefer an existing implementation or change approach. Do not make complete asset extraction or perfect infrastructure a prerequisite for all product work. Scratch helpers are preparation, not delivery. If a dependency truly blocks the milestone, state the specific blocker rather than silently expanding research.
- Shell commands default to a 120-second deadline. Set an explicit finite timeout for a legitimately longer build or download. After a timeout, inspect the cause before retrying; do not simply keep increasing the deadline. Start persistent servers in the background with logs and check readiness separately.
- Batch related inspections. When you have enough evidence, apply the identified fix rather than repeatedly restating plans. Further investigation is appropriate when it resolves a concrete uncertainty.
- Resolve observable behaviour with a small executable check. When correctness depends on an external specification or numerical constant, retrieve the source if a tool is available. Do not repeatedly reconstruct it from memory or call an unverified value authoritative. Use the observed result to choose the next action.
- For long tasks, keep a concise project handover recording the actual files changed, verified results, remaining problems and next action. Update it at meaningful milestones so compaction does not lose the plan.
- Record failed approaches and what evidence ruled them out. Before retrying one, identify what changed. A successful tool invocation is not proof that the product or its tests passed.
- Before using a downloaded asset, verify its actual file type or decode it with an existing image reader. A .png filename or successful curl command can still contain an HTML error page. If it does, inspect the source page once for the real asset URL or choose another available source; do not keep retrying the same failed URL with cosmetic command changes.
- Verify the real entry point used by the user. Changes confined to scratch/test files are not delivered until integrated. For browser work, use browser execution and visual checks if available; simulated DOM tests alone do not prove rendering or playability.
- Preserve test intent. Distinguish a test-driver defect from a product defect; do not weaken assertions just to get a pass. Use assertions or nonzero exit status for failed checks, not only printed PASS/FAIL labels. Once the requested behaviour is delivered and relevant checks pass, finish instead of repeatedly rerunning unchanged tests.
- In the final response, state what is actually delivered and verified, and explicitly identify anything unfinished or untested.
- To act, use the available native tools. Printing a tool name or shell command in an answer does not execute it. Follow the tool format supplied by the provider.
`;

// Recognize unexecuted tool-shaped final answers, never execute their contents.
// A syntactically valid call envelope is still not an actual Pi tool call.
export function malformedToolAnswer(message, activeTools) {
  if (message?.role !== 'assistant' || message.stopReason !== 'stop') return false;
  const blocks = Array.isArray(message.content) ? message.content : [];
  if (blocks.some(block => block.type === 'toolCall' || block.type === 'tool_call')) return false;
  const text = (typeof message.content === 'string' ? message.content
    : blocks.filter(block => block.type === 'text').map(block => block.text || '').join('')).trim();
  const match = /^\{\s*"name"\s*:\s*"([\w.-]+)(?=["\s,>:}]|$)/.exec(text);
  try {
    const value = JSON.parse(text);
    return Boolean(value && !Array.isArray(value) && activeTools.includes(value.name)
      && Object.keys(value).every(key => ['name', 'arguments'].includes(key))
      && Object.hasOwn(value, 'arguments') && value.arguments !== null
      && typeof value.arguments === 'object' && !Array.isArray(value.arguments));
  } catch { return Boolean(match && activeTools.includes(match[1])); }
}

export function requestsLiteralToolOutput(text = '') {
  // Mentioning config.json or fixing a JSON parser is implementation work,
  // not a request to print tool syntax instead of performing the task.
  return /\b(?:show|give|provide|explain|demonstrate)\b[^.!?\n]{0,80}\b(?:example|sample|syntax|format)\b/i.test(text)
    || /\b(?:return|output|respond|reply|print)\s+(?:(?:only|in|as|with|the|a|an|raw|literal|verbatim)\s+)*(?:json|xml|syntax|example|sample)\b/i.test(text)
    || /\b(?:quote|repeat|copy)\b[^.!?\n]{0,60}\b(?:literally|verbatim)\b/i.test(text);
}

// Only remove a failed attempt from model-facing context when the launcher
// actually flagged it. The saved transcript and real tool calls stay intact.
export function recoveredToolContext(messages, activeTools) {
  const failed = new Set();
  messages.forEach((message, index) => {
    if (message.role !== 'custom' || !['launcher-tool-format-recovery',
      'launcher-tool-format-error'].includes(message.customType)) return;
    // Pi can persist a display-only message_end notice just before the
    // assistant entry, while queued recovery messages follow the entry.
    for (const adjacent of [index - 1, index + 1]) {
      if (malformedToolAnswer(messages[adjacent], activeTools)) failed.add(adjacent);
    }
  });
  if (!failed.size) return messages;
  return messages.map((message, index) => failed.has(index) ? {
    ...message,
    content:[{type:'text', text:'[Invalid tool output omitted from model context. No tool ran; retry from the last confirmed result.]'}],
  } : message);
}

export function toolRecoveryGuidance(provider = {}) {
  const format = /qwopus/i.test(provider.model?.name || '')
    ? ' This model requires <tool_call>{"name":"TOOL_NAME","arguments":{...}}</tool_call>, with an actual available tool name and schema-valid arguments. These delimiters belong outside the thinking block; a bare JSON wrapper is not a tool call.'
    : ' Use the exact native tool format in the system tool instructions.';
  return 'Tool-call recovery: the previous attempt was invalid and did not execute. Its broken output is omitted from the next model request; use the last confirmed tool result. Continue only the user’s existing request.'
    + format + ' Close every JSON object and array, including the outer tool-call object. Simplify the next action: avoid repeating the same deeply escaped command. Prefer a small native read/write/edit call, or a short shell command with valid JSON escaping. Do not claim execution until a real tool result arrives.';
}

// Native edit rejects the entire batch before writing when an anchor is absent
// or ambiguous. Supply observations with that error, never a guessed replacement
// or an automatic retry. Unknown/custom edit implementations remain untouched.
export async function failedEditEvidence(event, cwd) {
  if (event.toolName !== 'edit' || event.isError !== true || !cwd) return;
  const error = (event.content || []).filter(block => block.type === 'text')
    .map(block => block.text || '').join('\n');
  const missing = /^Could not find (?:edits\[(\d+)\]|the exact text) in [\s\S]+?\. The old(?:Text| text) must match exactly including all whitespace and newlines\.$/.exec(error);
  const duplicate = /^Found \d+ occurrences of (?:edits\[(\d+)\]|the text) in [\s\S]+?\. (?:Each oldText|The text) must be unique\. Please provide more context to make it unique\.$/.exec(error);
  if (!missing && !duplicate) return;
  const index = Number((missing || duplicate)[1] || 0);
  const edits = Array.isArray(event.input?.edits) ? event.input.edits
    : typeof event.input?.oldText === 'string' ? [event.input] : [];
  const oldText = edits[index]?.oldText;
  const requested = event.input?.path;
  if (typeof oldText !== 'string' || !oldText || oldText.length > 100000
      || typeof requested !== 'string' || !requested || requested.includes('\0')
      || /^[a-z][\w+.-]*:/i.test(requested)) return;
  // Match native Pi's common local paths. Unusual expansion syntax is left to
  // the actual tool rather than guessed here. Never traverse a final symlink or
  // wait on a pipe/device just to improve a failed edit's diagnostic.
  const local = requested.startsWith('~/') ? resolve(homedir(), requested.slice(2)) : requested;
  if (local.startsWith('~') || local.startsWith('@')) return;
  const path = resolve(cwd, local);
  let file;
  try {
    file = await open(path, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW | fsConstants.O_NONBLOCK);
    const before = await file.stat();
    if (!before.isFile() || before.size > 512 * 1024) return;
    const buffer = Buffer.alloc(512 * 1024 + 1);
    const {bytesRead} = await file.read(buffer, 0, buffer.length, 0);
    const after = await file.stat();
    if (bytesRead !== before.size || before.size !== after.size || before.mtimeMs !== after.mtimeMs) return;
    const bytes = buffer.subarray(0, bytesRead);
    if (bytes.includes(0)) return;
    const source = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
    const excerpts = editSourceExcerpts(source, oldText);
    return {path, failedEdit:index, batchSize:edits.length, reason:missing ? 'missing' : 'ambiguous',
      sha256:createHash('sha256').update(bytes).digest('hex'), ...excerpts};
  } catch {
    // The original tool failure is authoritative even if the supplementary
    // read is unavailable, changed concurrently, binary, or too large.
  } finally {
    await file?.close();
  }
}

export function editSourceExcerpts(source, oldText) {
  const lines = source.replace(/^\uFEFF/, '').split(/\r?\n/);
  if (lines.length > 20000) return {lineCount:lines.length, regions:[], declarations:[]};
  const anchorLines = new Set(oldText.split(/\r?\n/).map(line => line.trim())
    .filter(line => line.length >= 8 && /[a-zA-Z]/.test(line)));
  const tokens = new Set((oldText.match(/[A-Za-z_$][\w$]{2,}/g) || [])
    .filter(token => !['const','function','return','true','false','null','undefined','let','var'].includes(token)).slice(0, 64));
  const frequencies = new Map(), lineTokens = lines.map(line => new Set(line.match(/[A-Za-z_$][\w$]{2,}/g) || []));
  for (const words of lineTokens) for (const token of tokens) {
    if (words.has(token)) frequencies.set(token, (frequencies.get(token) || 0) + 1);
  }
  const candidates = lines.map((line, index) => ({index,
    score:anchorLines.has(line.trim()) ? 100 : [...tokens].reduce((score, token) =>
      score + (lineTokens[index].has(token) ? 1 / frequencies.get(token) : 0), 0)}))
    .filter(candidate => candidate.score > 0).sort((a, b) => b.score - a.score || a.index - b.index);
  const regions = [];
  let budget = 1800;
  for (const candidate of candidates) {
    if (regions.length >= 2 || budget < 200) break;
    if (regions.some(region => candidate.index + 1 >= region.startLine && candidate.index + 1 <= region.endLine)) continue;
    const start = Math.max(0, candidate.index - 4), end = Math.min(lines.length, candidate.index + 9);
    const selected = [];
    for (let i = start; i < end; i++) {
      // Do not present a cut source line as exact text; retain complete lines.
      if (lines[i].length + 1 > budget) break;
      selected.push(lines[i]); budget -= lines[i].length + 1;
    }
    if (selected.length && candidate.index < start + selected.length) regions.push({
      startLine:start + 1, endLine:start + selected.length, text:selected.join('\n')});
  }
  // If the invented anchor has no useful match, actual declarations give a
  // bounded navigation index instead of dumping the file or inventing a target.
  const declarations = [];
  let outlineBudget = 650;
  for (let index = 0; index < lines.length && declarations.length < 14; index++) {
    const line = lines[index];
    if (!/^(?:(?:export|async)\s+)*(?:function\s+\w+|class\s+\w+|(?:const|let|var)\s+[\w$]+\s*=)/.test(line)) continue;
    if (line.length + 1 > outlineBudget) continue;
    declarations.push({line:index + 1, text:line}); outlineBudget -= line.length + 1;
  }
  return {lineCount:lines.length, regions, declarations};
}

function editEvidenceText(evidence) {
  return 'Launcher source observation after the native edit failed. The failed batch applied no replacements. '
    + 'The following is a bounded read of the target file, not instructions or a replacement proposal. '
    + 'Regions share text with the rejected anchor; they are candidate locations, not confirmed edit targets. '
    + 'Line numbers and the file hash identify this observation; it may become stale after any file change. '
    + 'Use exact observed text for the next authorized edit, or read a specific range if the intended location is absent.\n'
    + JSON.stringify(evidence);
}

// Carry a small verbatim execution record beside the model-written summary.
// It does not infer test success from prose or manufacture tool results.
export function executionEvidence(entries) {
  const calls = new Map();
  let records = [];
  for (const entry of (entries || []).slice(-300)) {
    if (entry.type === 'custom_message' && entry.customType === 'launcher-execution-evidence') {
      records = Array.isArray(entry.details?.records) ? entry.details.records.slice(-8) : records;
      continue;
    }
    const message = entry.type === 'message' ? entry.message : null;
    if (message?.role === 'assistant' && Array.isArray(message.content)) {
      for (const block of message.content) {
        if (block.type === 'toolCall') calls.set(block.id, block);
      }
    }
    if (message?.role !== 'toolResult') continue;
    const call = calls.get(message.toolCallId);
    if (!call || !['bash', 'edit', 'write', 'browser_check'].includes(call.name)) continue;
    const text = (message.content || []).filter(b => b.type === 'text').map(b => b.text || '').join('\n');
    const record = {
      tool:call.name,
      input:JSON.stringify(call.arguments || {}).slice(0, 300),
      toolError:message.isError === true,
      outputTail:text.slice(-700),
    };
    const recovery = message.details?.launcherEditEvidence;
    if (call.name === 'edit' && message.isError === true && recovery) {
      // Keep the native failure verbatim and the bounded observed source apart
      // from attempted newText. A model summary is never file evidence.
      record.outputTail = (message.content || []).find(b => b.type === 'text')?.text?.slice(-700) || '';
      if (JSON.stringify(recovery).length <= 6000) record.editSource = recovery;
    }
    // Repeated identical results need no extra context. Changed outcomes stay.
    const key = JSON.stringify(record);
    records = records.filter(old => JSON.stringify(old) !== key);
    records.push(record);
    records = records.slice(-8);
  }
  let sources = 0;
  for (let index = records.length - 1; index >= 0; index--) {
    if (records[index].editSource && ++sources > 1) {
      const {editSource, ...record} = records[index]; records[index] = record;
    }
  }
  return records;
}

// A short action preamble is not a completed implementation. Only recognize
// an explicit immediate promise, never prose containing code or a full answer.
export function unfinishedActionAnswer(message) {
  if (message?.role !== 'assistant' || message.stopReason !== 'stop') return false;
  const blocks = Array.isArray(message.content) ? message.content : [];
  if (blocks.some(block => block.type === 'toolCall' || block.type === 'tool_call')) return false;
  const text = (typeof message.content === 'string' ? message.content
    : blocks.filter(block => block.type === 'text').map(block => block.text || '').join('')).trim();
  return text.length <= 400 && !/[`{}]/.test(text)
    && !/\b(if|could|would|approve|permission)\b/i.test(text)
    && /(?:^|[.!?]\s+)(?:now[, ]+)?(?:let me|i['’]ll|i will)\s+(?:now\s+)?(?:implement|apply|write|edit|fix|repair|update|run|execute)\b[^.!?\n]*[:.]?$/i.test(text);
}

// A repeated cycle is evidence of revisiting unchanged observations, not proof
// that a task is failing. Keep one bounded note per user input and no evaluator.
export function createInspectionProgressCheck() {
  let history = [], notified = false;
  const reset = () => { history = []; };
  return {
    reset,
    newInput() { reset(); notified = false; },
    commit() { reset(); notified = true; },
    observe({toolName, input, content, isError, turn}) {
      if (notified) return;
      if (!['read', 'grep', 'find', 'ls'].includes(toolName) || isError !== false
          || !Number.isInteger(turn) || !Array.isArray(content) || !content.length
          || content.some(block => block?.type !== 'text' || typeof block.text !== 'string')
          || !content.some(block => block.text.length)) return reset();
      const args = JSON.stringify(input), result = JSON.stringify(content);
      if (!args || args.length > 2048 || result.length > 128 * 1024) return reset();
      const hash = value => createHash('sha256').update(value).digest('hex');
      const action = hash(JSON.stringify([toolName, args])), resultHash = hash(result);
      history.push({action, resultHash, tool:toolName, args, turn});
      if (history.length > 12) history.shift();
      for (let size = 2; size <= 4; size++) {
        const start = history.length - size * 3;
        if (start < 0) continue;
        const sequence = history.slice(start), cycle = sequence.slice(0, size);
        if (new Set(cycle.map(item => item.action)).size < 2) continue;
        // A single batch cannot show that the model ignored earlier results.
        if (sequence[size].turn <= sequence[size - 1].turn
            || sequence[size * 2].turn <= sequence[size * 2 - 1].turn) continue;
        if (!sequence.every((item, index) => item.action === cycle[index % size].action
            && item.resultHash === cycle[index % size].resultHash)) continue;
        reset();
        return {cycles:3, actions:cycle.map(({tool, args, resultHash}) => ({
          tool, input:JSON.parse(args), resultHash,
        }))};
      }
    },
  };
}

/** Annotate observed file-type mismatches, never infer failure from exit code alone. */
export function downloadedImageEvidence(event) {
  if (event.toolName !== 'bash' || typeof event.input?.command !== 'string'
      || !/(?:^|[\s;&|])(?:curl|wget)\s/.test(event.input.command)) return [];
  const output = (event.content || []).filter(block => block.type === 'text')
    .map(block => block.text || '').join('\n');
  if (output.length > 128 * 1024) return [];
  return [...new Set([...output.matchAll(/^(.+\.(?:png|jpe?g|gif|webp|avif|bmp|tiff?)):\s+HTML document[^\r\n]*$/gim)]
    .map(match => match[1].slice(0, 500)))].slice(0, 4);
}

export default function launcherWorkflow(pi) {
  let provider = {};
  try { provider = JSON.parse(process.env.LLM_LAUNCHER_PI_PROVIDER || '{}'); } catch {}
  registerBrowserCheck(pi, provider);
  let formatRetries = 0;
  let totalFormatRetries = 0;
  let formatWarningSent = false;
  let literalRequested = false;
  let repeatedAction = null;
  let monitoringRequested = false;
  let actionRetries = 0;
  let actionSeen = false;
  let planOnly = false;
  let reasoningStopped = false;
  let reasoningCheckedAt = 0;
  let assistantTurn = 0;
  let progressCandidate = null, progressNotice = null;
  const progressCheck = createInspectionProgressCheck();
  const deliveryCheck = createDeliveryProgressCheck();
  let deliveryCalls = 0;
  const contextRecovery = createContextRecovery();
  const pending = new Map();
  const reset = () => { pending.clear(); progressCheck.reset(); progressCandidate = null; };
  pi.on('tool_result', async (event, ctx) => {
    if (event.toolName === 'bash'
        && pi.getAllTools?.().find(tool => tool.name === 'bash')?.sourceInfo?.source === 'builtin') {
      const rejectedImages = downloadedImageEvidence(event);
      if (rejectedImages.length) return {
        content:[...event.content, {type:'text', text:'Downloaded image check: the file inspection reports HTML, not image data, for ' + JSON.stringify(rejectedImages)
          + '. The shell command completed, but these are not usable image assets. Do not decode or visually assess those files. Inspect the source page for its actual image link or use another available source, then verify the file type before using it. Changing only the user-agent does not establish a working image URL.'}],
        details:{...event.details, launcherDownloadEvidence:{unusableImages:rejectedImages}},
      };
    }
    if (event.toolName !== 'edit' || event.isError !== true
        || pi.getAllTools?.().find(tool => tool.name === 'edit')?.sourceInfo?.source !== 'builtin') return;
    const evidence = await failedEditEvidence(event, ctx?.cwd);
    if (!evidence) return;
    return {content:[...event.content, {type:'text',text:editEvidenceText(evidence)}],
      details:{...event.details, launcherEditEvidence:evidence}};
  });
  pi.on('context', event => {
    const messages = contextRecovery.recover(recoveredToolContext(event.messages, pi.getActiveTools()));
    if (!progressNotice || messages.some(message => message.role === 'custom'
        && message.customType === progressNotice.customType
        && message.details?.afterToolCallId === progressNotice.details.afterToolCallId)) return {messages};
    // Pi 0.85 saves context-only notices but its active loop holds an earlier
    // message snapshot. Insert at the confirmed result, never at a moving tail.
    const index = messages.findIndex(message => message.role === 'toolResult'
      && message.toolCallId === progressNotice.details.afterToolCallId);
    return {messages:index < 0 ? messages : [
      ...messages.slice(0, index + 1), progressNotice, ...messages.slice(index + 1),
    ]};
  });
  pi.on('before_provider_headers', (event, ctx) => {
    const headers = event.headers;
    if (!headers || Object.entries(headers).find(([key]) => key.toLowerCase() === 'x-mtplx-client')?.[1] !== 'pi') return;
    const original = String(ctx.sessionManager.getSessionId());
    const recovered = contextRecovery.sessionId(original);
    headers['x-mtplx-session-id'] = recovered;
    // Pi runs global header extensions after explicit launcher extensions.
    // Keep recovery authoritative at our relay even if a later plugin resets
    // the native session ID. The relay consumes this private header.
    if (recovered !== original) headers['x-llm-launcher-mtplx-recovery'] = recovered;
    else delete headers['x-llm-launcher-mtplx-recovery'];
  });
  pi.on('message_start', event => {
    if (event.message?.role === 'assistant') {
      assistantTurn++; reasoningStopped = false; reasoningCheckedAt = 0;
    }
  });
  pi.on('message_update', (event, ctx) => {
    if (reasoningStopped || event.message?.role !== 'assistant') return;
    const thinking = (event.message.content || []).filter(b => b.type === 'thinking')
      .map(b => b.thinking || b.text || '').join('\n\n');
    if (thinking.length < reasoningCheckedAt + 512) return;
    reasoningCheckedAt = thinking.length;
    if (!reasoningRepetition(thinking)) return;
    reasoningStopped = true;
    pi.sendMessage({customType:'launcher-loop-stop', display:true,
      content:'Paused: the model is repeating the same reasoning paragraphs. Generation was stopped before it could fill the context. Compact to create a clean handover before continuing; the original conversation stays saved.'},
    {triggerTurn:false});
    ctx.abort();
  });
  pi.on('before_agent_start', event => {
    reset();
    return {systemPrompt: `${event.systemPrompt || ''}\n${WORKFLOW_GUIDANCE}`};
  });
  pi.on('session_start', (_event, ctx) => {
    const userEntries = (ctx?.sessionManager?.getBranch?.() || []).filter(e => e.message?.role === 'user');
    const priorIntent = [...userEntries].reverse().map(entry => {
      const content = entry.message.content;
      return implementationRequest(typeof content === 'string' ? content : (content || []).map(b => b.text || '').join(' '));
    }).find(value => value !== undefined);
    deliveryCheck.reset(priorIntent ?? false);
    deliveryCalls = 0;
    contextRecovery.reset();
    progressNotice = null;
    progressCheck.newInput(); assistantTurn = 0;
    reset(); formatRetries = 0; totalFormatRetries = 0; formatWarningSent = false; literalRequested = false;
    repeatedAction = null; monitoringRequested = false;
    actionRetries = 0; actionSeen = false; planOnly = false;
    reasoningStopped = false; reasoningCheckedAt = 0;
    const branch = ctx?.sessionManager?.getBranch?.() || [];
    const boundary = branch.findLastIndex(e => e.type === 'compaction'
      || (e.type === 'message' && e.message?.role === 'user'));
    const recent = branch.slice(boundary + 1);
    if (!recent.some(e => e.type === 'custom_message' && e.customType === 'launcher-loop-stop')
        && recent.some(e => e.type === 'message' && e.message?.role === 'assistant'
          && e.message.content?.some(isDamagedReasoningBlock))) {
      pi.sendMessage({customType:'launcher-loop-stop',display:true,
        content:'Repeated reasoning was found in the saved unfinished turn. Compact to create a clean handover before continuing. The original transcript and confirmed tool results remain saved.'}, {triggerTurn:false});
    }
  });
  pi.on('input', event => {
    if (event.source !== 'extension') {
      progressCheck.newInput();
      progressCandidate = null; progressNotice = null;
      formatRetries = 0; totalFormatRetries = 0; formatWarningSent = false;
      literalRequested = requestsLiteralToolOutput(event.text || '');
      repeatedAction = null;
      actionRetries = 0; actionSeen = false;
      const request = event.text || '';
      deliveryCheck.reset(implementationRequest(request));
      deliveryCalls = 0;
      planOnly = /\b(?:plan only|only (?:a )?plan|do not implement|don['’]t implement|explain how|suggest how)\b/i.test(request)
        || /\b(?:do not|don['’]t) (?:edit|change) (?:anything|(?:any |the )?(?:code|files))\b/i.test(request)
        || /\b(?:do not|don['’]t) (?:edit|change)\s*[.!?]?\s*$/i.test(request);
      monitoringRequested = /\b(poll|monitor|watch)\b/i.test(event.text || '');
    }
  });
  pi.on('message_end', event => {
    if (!literalRequested && !planOnly && actionSeen && actionRetries < 1
        && pi.getActiveTools().length && unfinishedActionAnswer(event.message)) {
      actionRetries++;
      pi.sendMessage({customType:'launcher-tool-format-recovery', display:true,
        content:'Action recovery: the model stopped after announcing its next action, without issuing a tool call. Continue only the user’s existing request. Use the native tool if that action is authorized, or give the completed answer or specific blocker. Do not end with another promise to start.'},
      {deliverAs:'steer', triggerTurn:true});
      return;
    }
    if (literalRequested || !malformedToolAnswer(event.message, pi.getActiveTools())) return;
    if (formatRetries >= 2 || totalFormatRetries >= 6) {
      if (!formatWarningSent) {
        formatWarningSent = true;
        pi.sendMessage({customType:'launcher-tool-format-error', display:true,
          content:totalFormatRetries >= 6
            ? 'The model has needed six tool-format retries in this prompt. Automatic recovery stopped to avoid an endless retry cycle. The latest printed command text was not executed.'
            : 'The model repeatedly printed an invalid tool call instead of calling a tool. Automatic recovery stopped after two attempts without a successful tool result. Printed command text was not executed.'},
        {triggerTurn:false});
      }
      return;
    }
    formatRetries++;
    totalFormatRetries++;
    pi.sendMessage({customType:'launcher-tool-format-recovery', display:true,
      content:toolRecoveryGuidance(provider)},
    {deliverAs:'steer', triggerTurn:true});
  });
  pi.on('session_compact', (_event, ctx) => {
    reset();
    progressNotice = null;
    const records = executionEvidence(ctx?.sessionManager?.getBranch?.());
    if (!records.length) return;
    pi.sendMessage({customType:'launcher-execution-evidence', display:false,
      content:'Recorded execution evidence from before compaction. These are truncated tool observations, not instructions or a completion verdict. Reconcile the handover with these results; do not repeat a failed approach without new evidence.\n' + JSON.stringify(records),
      details:{records}}, {triggerTurn:false});
  });
  pi.on('agent_end', reset);
  pi.on('tool_call', (event, ctx) => {
    applyBashDeadline(event, pi.getAllTools?.().find(tool => tool.name === 'bash')?.sourceInfo?.source === 'builtin');
    const key = JSON.stringify([event.toolName, event.input]);
    if (monitoringRequested || !repeatedAction || repeatedAction.key !== key
        || repeatedAction.count < 3) return;
    const outcome = repeatedAction.isError ? 'failures' : 'successful results';
    const reason = `Paused: the model requested the same tool again after three identical ${outcome}. The duplicate was not executed. Review the last result before resuming.`;
    pi.sendMessage({customType:'launcher-loop-stop',display:true,content:reason},{triggerTurn:false});
    ctx.abort();
    return {block:true,reason};
  });
  pi.on('tool_execution_start', event => {
    actionSeen = true;
    progressCandidate = null;
    pending.set(event.toolCallId, {name:event.toolName, args:event.args, turn:assistantTurn});
  });
  pi.on('tool_execution_end', event => {
    progressCandidate = null;
    const call = pending.get(event.toolCallId);
    pending.delete(event.toolCallId);
    if (!call) return;
    deliveryCalls++;
    // A confirmed successful native result ends this format-failure episode.
    // Merely announcing/calling a tool (or getting an error) does not. Keep a
    // separate per-input ceiling so alternating success/failure cannot retry
    // forever. Automatic continuations and compaction do not reset that ceiling.
    if (event.isError === false && event.result && Array.isArray(event.result.content)) {
      formatRetries = 0;
      formatWarningSent = false;
    }
    const actionKey = JSON.stringify([call.name, call.args]);
    const resultKey = JSON.stringify(event.result?.content ?? null);
    const isError = event.isError === true;
    if (resultKey === 'null') repeatedAction = null;
    else if (repeatedAction?.key === actionKey && repeatedAction.result === resultKey
        && repeatedAction.isError === isError) repeatedAction.count++;
    else repeatedAction = {key:actionKey,result:resultKey,isError,count:1};
    if (monitoringRequested || pi.getAllTools?.().find(tool => tool.name === call.name)
        ?.sourceInfo?.source !== 'builtin') { progressCheck.reset(); return; }
    const evidence = progressCheck.observe({toolName:call.name, input:call.args,
      content:event.result?.content, isError:event.isError, turn:call.turn});
    if (!evidence) return;
    progressCandidate = {evidence, toolCallId:event.toolCallId};
  });
  pi.on('turn_end', async (event = {}, ctx) => {
    const completed = deliveryCalls; deliveryCalls = 0;
    const delivery = !progressCandidate && !planOnly && !monitoringRequested ? await deliveryCheck.observe(ctx?.cwd, completed) : null;
    if (delivery && !progressCandidate) {
      const afterToolCallId = event.toolResults?.at(-1)?.toolCallId;
      if (afterToolCallId) {
        progressNotice = {role:'custom', timestamp:Date.now(), customType:'launcher-progress-check', display:true,
          details:{...delivery, afterToolCallId},
          content:`Implementation progress: ${delivery.completedTools} tools completed over ${delivery.minutes} minutes without a change to the ${delivery.sourceFiles} observed project source files. Scratch scripts and downloads may be useful preparation, but no source change was observed in the project. This is not proof of a loop. Use the evidence already obtained to implement and verify the smallest requested runnable milestone. If it is genuinely blocked, identify the exact missing dependency and choose one bounded next step; do not repeat solved investigations or make unrelated edits just to satisfy this check.`,
        };
        pi.sendMessage(progressNotice, {triggerTurn:false});
      }
    }
    if (!progressCandidate) return;
    const {evidence, toolCallId} = progressCandidate;
    progressCandidate = null;
    progressCheck.commit();
    // Parallel tools finish out of order; native history keeps call order.
    const afterToolCallId = event.toolResults?.at(-1)?.toolCallId ?? toolCallId;
    const actions = evidence.actions.map(({tool, input}) => {
      const args = JSON.stringify(input);
      return `- ${tool} ${args.length > 240 ? args.slice(0, 240) + '…' : args}`;
    }).join('\n');
    progressNotice = {role:'custom', timestamp:Date.now(),
      customType:'launcher-progress-check', display:true,
      details:{...evidence, afterToolCallId},
      content:`Progress check: these ${evidence.actions.length} inspection calls returned identical results across three consecutive cycles:\n${actions}\nNo new tool evidence was returned in those cycles. Reuse the observations to choose the next useful action, or finish if the request is answered. If another inspection is needed, target a specific unanswered question. This observation does not require edits or prove the task is failing.`,
    };
    // Save/display the same note without starting a turn or skipping tools.
    pi.sendMessage(progressNotice, {triggerTurn:false});
  });
}
