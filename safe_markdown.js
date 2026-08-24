(function installSafeMarkdown(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMSafeMarkdownCore = api;
})(typeof globalThis === "object" ? globalThis : this, function safeMarkdownFactory() {
  "use strict";

  const MAX_CHARACTERS = 2_000_000;
  const MAX_BLOCKS = 4096;
  const MAX_INLINE_TOKENS = 32768;
  const MAX_TABLE_COLUMNS = 12;
  const MAX_TABLE_ROWS = 128;
  const MAX_DEPTH = 6;

  function safeLink(value) {
    const candidate = String(value || "").trim();
    if (!candidate || candidate.length > 2048 || /[\u0000-\u001f\u007f\s]/u.test(candidate)) return null;
    try {
      const url = new URL(candidate);
      if (!new Set(["http:", "https:"]).has(url.protocol) || url.username || url.password) return null;
      return url.href;
    } catch (_error) {
      return null;
    }
  }

  function appendText(tokens, text) {
    if (!text) return;
    const previous = tokens.at(-1);
    if (previous?.type === "text") previous.text += text;
    else tokens.push({type:"text", text});
  }

  function findUnescaped(value, needle, start) {
    let offset = start;
    while (offset < value.length) {
      const found = value.indexOf(needle, offset);
      if (found < 0) return -1;
      let slashes = 0;
      for (let index = found - 1; index >= 0 && value[index] === "\\"; index -= 1) slashes += 1;
      if (slashes % 2 === 0) return found;
      offset = found + needle.length;
    }
    return -1;
  }

  function linkDestination(raw) {
    let value = String(raw || "").trim();
    if (value.startsWith("<") && value.includes(">")) value = value.slice(1, value.indexOf(">"));
    else value = value.split(/\s+/u, 1)[0] || "";
    return safeLink(value);
  }

  function parseInline(value, depth = 0) {
    const source = String(value || "");
    if (!source || depth > MAX_DEPTH) return source ? [{type:"text", text:source}] : [];
    const tokens = [];
    let index = 0;
    while (index < source.length) {
      if (tokens.length >= MAX_INLINE_TOKENS) {
        appendText(tokens, source.slice(index));
        break;
      }
      const character = source[index];
      if (character === "\\" && index + 1 < source.length && /[\\`*_[\]{}()#+.!|>~-]/u.test(source[index + 1])) {
        appendText(tokens, source[index + 1]);
        index += 2;
        continue;
      }
      if (character === "\n") {
        tokens.push({type:"break"});
        index += 1;
        continue;
      }
      if (character === "`") {
        let size = 1;
        while (source[index + size] === "`") size += 1;
        const marker = "`".repeat(size);
        const close = findUnescaped(source, marker, index + size);
        if (close >= 0) {
          tokens.push({type:"code", text:source.slice(index + size, close).replace(/\n/gu, " ")});
          index = close + size;
          continue;
        }
      }
      const image = source.startsWith("![", index);
      if (image || character === "[") {
        const labelStart = index + (image ? 2 : 1);
        const labelEnd = findUnescaped(source, "](", labelStart);
        if (labelEnd >= 0) {
          const destinationEnd = findUnescaped(source, ")", labelEnd + 2);
          if (destinationEnd >= 0) {
            const url = linkDestination(source.slice(labelEnd + 2, destinationEnd));
            if (url) {
              const label = source.slice(labelStart, labelEnd);
              tokens.push({
                type:"link", url, imageReference:image,
                children:parseInline(image ? `Image: ${label || url}` : label || url, depth + 1),
              });
              index = destinationEnd + 1;
              continue;
            }
          }
        }
      }
      if (character === "<") {
        const close = source.indexOf(">", index + 1);
        if (close > index + 1) {
          const url = safeLink(source.slice(index + 1, close));
          if (url) {
            tokens.push({type:"link", url, imageReference:false, children:[{type:"text", text:url}]});
            index = close + 1;
            continue;
          }
        }
      }
      const emphasis = [
        {marker:"**", type:"strong"}, {marker:"__", type:"strong"},
        {marker:"~~", type:"delete"}, {marker:"*", type:"emphasis"},
      ].find(item => source.startsWith(item.marker, index));
      if (emphasis) {
        const close = findUnescaped(source, emphasis.marker, index + emphasis.marker.length);
        if (close > index + emphasis.marker.length) {
          tokens.push({
            type:emphasis.type,
            children:parseInline(source.slice(index + emphasis.marker.length, close), depth + 1),
          });
          index = close + emphasis.marker.length;
          continue;
        }
      }
      let next = index + 1;
      while (next < source.length && !/[\\\n`<![*_~]/u.test(source[next])) next += 1;
      appendText(tokens, source.slice(index, next));
      index = next;
    }
    return tokens;
  }

  function splitTableRow(value) {
    let source = String(value || "").trim();
    if (source.startsWith("|")) source = source.slice(1);
    if (source.endsWith("|") && !source.endsWith("\\|")) source = source.slice(0, -1);
    const cells = [];
    let cell = "";
    let escaped = false;
    let codeTicks = 0;
    for (let index = 0; index < source.length; index += 1) {
      const character = source[index];
      if (escaped) { cell += character; escaped = false; continue; }
      if (character === "\\") { escaped = true; continue; }
      if (character === "`") { codeTicks = codeTicks ? 0 : 1; cell += character; continue; }
      if (character === "|" && !codeTicks) {
        cells.push(cell.trim());
        cell = "";
        if (cells.length >= MAX_TABLE_COLUMNS) break;
        continue;
      }
      cell += character;
    }
    if (cells.length < MAX_TABLE_COLUMNS) cells.push((escaped ? `${cell}\\` : cell).trim());
    return cells.slice(0, MAX_TABLE_COLUMNS);
  }

  function tableDelimiter(value) {
    const cells = splitTableRow(value);
    if (cells.length < 2 || cells.some(cell => !/^:?-{3,}:?$/u.test(cell))) return null;
    return cells.map(cell => cell.startsWith(":") && cell.endsWith(":") ? "center" : cell.endsWith(":") ? "right" : "left");
  }

  function fenceMatch(value) {
    return String(value || "").match(/^ {0,3}(`{3,}|~{3,})[ \t]*([^\s`~]*)[^\r\n]*$/u);
  }

  function listMatch(value) {
    const unordered = String(value || "").match(/^ {0,3}[-+*][ \t]+(.+)$/u);
    if (unordered) return {ordered:false, start:1, content:unordered[1]};
    const ordered = String(value || "").match(/^ {0,3}(\d{1,9})[.)][ \t]+(.+)$/u);
    return ordered ? {ordered:true, start:Math.max(1, Number(ordered[1]) || 1), content:ordered[2]} : null;
  }

  function isRule(value) {
    return /^ {0,3}((\*[ \t]*){3,}|(-[ \t]*){3,}|(_[ \t]*){3,})$/u.test(String(value || ""));
  }

  function isBlockStart(lines, index) {
    const line = lines[index] || "";
    return !line.trim() || Boolean(
      fenceMatch(line) || /^ {0,3}#{1,6}[ \t]+/u.test(line)
      || /^ {0,3}>/u.test(line) || listMatch(line) || isRule(line)
      || (line.includes("|") && tableDelimiter(lines[index + 1] || ""))
    );
  }

  function parseBlocks(lines, depth = 0) {
    if (depth > MAX_DEPTH) return [{type:"paragraph", children:parseInline(lines.join("\n"), depth)}];
    const blocks = [];
    let index = 0;
    while (index < lines.length) {
      if (blocks.length >= MAX_BLOCKS) {
        blocks.push({type:"paragraph", children:parseInline(lines.slice(index).join("\n"), depth)});
        break;
      }
      const line = lines[index];
      if (!line.trim()) { index += 1; continue; }
      const fence = fenceMatch(line);
      if (fence) {
        const marker = fence[1];
        const language = /^[a-z0-9_+.#-]{1,40}$/iu.test(fence[2] || "") ? fence[2] : "text";
        const content = [];
        let closed = false;
        index += 1;
        while (index < lines.length) {
          const candidate = lines[index];
          const close = candidate.match(/^ {0,3}(`{3,}|~{3,})[ \t]*$/u);
          if (close && close[1][0] === marker[0] && close[1].length >= marker.length) {
            closed = true;
            index += 1;
            break;
          }
          content.push(candidate);
          index += 1;
        }
        blocks.push({type:"code", language, text:content.join("\n"), closed});
        continue;
      }
      const heading = line.match(/^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$/u);
      if (heading) {
        blocks.push({type:"heading", level:heading[1].length, children:parseInline(heading[2], depth)});
        index += 1;
        continue;
      }
      if (isRule(line)) {
        blocks.push({type:"rule"});
        index += 1;
        continue;
      }
      if (/^ {0,3}>/u.test(line)) {
        const quoted = [];
        while (index < lines.length && /^ {0,3}>/u.test(lines[index])) {
          quoted.push(lines[index].replace(/^ {0,3}>[ \t]?/u, ""));
          index += 1;
        }
        blocks.push({type:"quote", blocks:parseBlocks(quoted, depth + 1)});
        continue;
      }
      const list = listMatch(line);
      if (list) {
        const items = [];
        const ordered = list.ordered;
        const start = list.start;
        while (index < lines.length && items.length < 512) {
          const item = listMatch(lines[index]);
          if (!item || item.ordered !== ordered) break;
          let content = item.content;
          index += 1;
          while (index < lines.length && /^ {2,}\S/u.test(lines[index]) && !listMatch(lines[index])) {
            content += `\n${lines[index].trim()}`;
            index += 1;
          }
          const task = content.match(/^\[([ xX])\][ \t]+(.*)$/u);
          items.push({
            checked:task ? task[1].toLowerCase() === "x" : null,
            children:parseInline(task ? task[2] : content, depth),
          });
        }
        blocks.push({type:"list", ordered, start, items});
        continue;
      }
      if (line.includes("|") && index + 1 < lines.length) {
        const align = tableDelimiter(lines[index + 1]);
        if (align) {
          const headers = splitTableRow(line).slice(0, align.length).map(cell => parseInline(cell, depth));
          const rows = [];
          index += 2;
          while (index < lines.length && lines[index].includes("|") && lines[index].trim() && rows.length < MAX_TABLE_ROWS) {
            const cells = splitTableRow(lines[index]).slice(0, align.length);
            while (cells.length < align.length) cells.push("");
            rows.push(cells.map(cell => parseInline(cell, depth)));
            index += 1;
          }
          blocks.push({type:"table", align, headers, rows});
          continue;
        }
      }
      const paragraph = [line];
      index += 1;
      while (index < lines.length && !isBlockStart(lines, index)) {
        paragraph.push(lines[index]);
        index += 1;
      }
      blocks.push({type:"paragraph", children:parseInline(paragraph.join("\n"), depth)});
    }
    return blocks;
  }

  function parse(value) {
    const original = String(value || "").replace(/\r\n?/gu, "\n");
    const truncated = original.length > MAX_CHARACTERS;
    const source = original.slice(0, MAX_CHARACTERS);
    const blocks = parseBlocks(source.split("\n"));
    if (truncated) blocks.push({
      type:"notice", text:`Rich display stopped after ${MAX_CHARACTERS.toLocaleString("en-US")} characters; the saved message remains unchanged.`,
    });
    return {blocks, truncated, sourceLength:original.length};
  }

  return Object.freeze({
    MAX_BLOCKS, MAX_CHARACTERS, MAX_DEPTH, MAX_INLINE_TOKENS,
    MAX_TABLE_COLUMNS, MAX_TABLE_ROWS,
    parse, parseInline, safeLink, splitTableRow, tableDelimiter,
  });
});
