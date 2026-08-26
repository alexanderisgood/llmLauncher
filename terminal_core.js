(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LLMTerminalCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const clamp = (value, low, high) => Math.max(low, Math.min(high, Number(value) || low));
  const blankLine = cols => Array.from({length:cols}, () => " ");
  const blankStyleLine = cols => Array.from({length:cols}, () => "");
  const MAX_STYLED_RUNS = 4096;
  const rstrip = line => line.join("").replace(/\s+$/u, "");
  const DEFAULT_STYLE = Object.freeze({
    bold:false, dim:false, italic:false, underline:false,
    inverse:false, strike:false, foreground:null, background:null,
  });
  const styleKey = style => {
    if (!style || (
      !style.bold && !style.dim && !style.italic && !style.underline
      && !style.inverse && !style.strike && !style.foreground && !style.background
    )) return "";
    const flags = `${style.bold ? 1 : 0}${style.dim ? 1 : 0}${style.italic ? 1 : 0}${style.underline ? 1 : 0}${style.inverse ? 1 : 0}${style.strike ? 1 : 0}`;
    return `${flags}|${style.foreground || ""}|${style.background || ""}`;
  };
  const colorFromKey = value => {
    if (!value) return null;
    if (value.startsWith("i:")) return {mode:"indexed", value:clamp(Number(value.slice(2)), 0, 255)};
    if (value.startsWith("r:")) {
      const [red, green, blue] = value.slice(2).split(",").map(channel => clamp(Number(channel), 0, 255));
      return {mode:"rgb", red, green, blue};
    }
    return null;
  };
  const styleFromKey = key => {
    if (!key) return DEFAULT_STYLE;
    const [flags = "000000", foreground = "", background = ""] = String(key).split("|");
    return Object.freeze({
      bold:flags[0] === "1", dim:flags[1] === "1", italic:flags[2] === "1",
      underline:flags[3] === "1", inverse:flags[4] === "1", strike:flags[5] === "1",
      foreground:colorFromKey(foreground), background:colorFromKey(background),
    });
  };
  const segmentStyledRuns = (runs = [], ranges = []) => {
    const segments = [];
    let offset = 0;
    let rangeIndex = 0;
    for (const run of Array.isArray(runs) ? runs : []) {
      const text = String(run?.text || "");
      let localOffset = 0;
      while (localOffset < text.length) {
        const absolute = offset + localOffset;
        while (rangeIndex < ranges.length && Number(ranges[rangeIndex]?.end) <= absolute) rangeIndex += 1;
        const range = ranges[rangeIndex];
        let localEnd = text.length;
        let matchIndex = -1;
        if (range && Number(range.start) < offset + text.length) {
          if (absolute < Number(range.start)) localEnd = Math.min(localEnd, Number(range.start) - offset);
          else if (absolute < Number(range.end)) {
            localEnd = Math.min(localEnd, Number(range.end) - offset);
            matchIndex = rangeIndex;
          }
        }
        if (localEnd <= localOffset) localEnd = localOffset + 1;
        segments.push({
          text:text.slice(localOffset, localEnd),
          style:run.style || DEFAULT_STYLE,
          styleKey:String(run.styleKey || ""),
          matchIndex,
        });
        localOffset = localEnd;
      }
      offset += text.length;
    }
    return segments;
  };
  const isCombining = value => /[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f\ufe0e\ufe0f]/u.test(value);
  const isWide = value => {
    const code = value.codePointAt(0) || 0;
    return code >= 0x1100 && (
      code <= 0x115f || code === 0x2329 || code === 0x232a
      || (code >= 0x2e80 && code <= 0xa4cf && code !== 0x303f)
      || (code >= 0xac00 && code <= 0xd7a3)
      || (code >= 0xf900 && code <= 0xfaff)
      || (code >= 0xfe10 && code <= 0xfe19)
      || (code >= 0xfe30 && code <= 0xfe6f)
      || (code >= 0xff00 && code <= 0xff60)
      || (code >= 0xffe0 && code <= 0xffe6)
      || (code >= 0x1f300 && code <= 0x1faff)
      || (code >= 0x20000 && code <= 0x3fffd)
    );
  };

  class TerminalBuffer {
    constructor(cols = 100, rows = 30, scrollbackLimit = 2000) {
      this.scrollbackLimit = clamp(scrollbackLimit, 0, 10000);
      this.cols = clamp(cols, 40, 240);
      this.rows = clamp(rows, 12, 100);
      this.main = this._screen();
      this.alternate = this._screen();
      this.useAlternate = false;
      this.scrollback = [];
      this.scrollbackStyled = [];
      this.currentStyle = {...DEFAULT_STYLE};
      this.parser = "normal";
      this.sequence = "";
      this.oscEscaped = false;
      this.skipNext = false;
    }

    _screen() {
      return {
        lines:Array.from({length:this.rows}, () => blankLine(this.cols)),
        styles:Array.from({length:this.rows}, () => blankStyleLine(this.cols)),
        x:0, y:0, savedX:0, savedY:0,
        scrollTop:0, scrollBottom:this.rows - 1,
        cursorVisible:true, wrapPending:false,
      };
    }

    get screen() { return this.useAlternate ? this.alternate : this.main; }

    reset() {
      this.main = this._screen();
      this.alternate = this._screen();
      this.useAlternate = false;
      this.scrollback = [];
      this.scrollbackStyled = [];
      this.currentStyle = {...DEFAULT_STYLE};
      this.parser = "normal";
      this.sequence = "";
      this.oscEscaped = false;
      this.skipNext = false;
    }

    resize(cols, rows) {
      const nextCols = clamp(cols, 40, 240);
      const nextRows = clamp(rows, 12, 100);
      const previousRows = this.rows;
      const pushScrollback = (cells, styles) => {
        let cellCount = cells.length;
        while (cellCount > 0 && /^\s*$/u.test(cells[cellCount - 1])) cellCount -= 1;
        const keptCells = cells.slice(0, cellCount);
        const keptStyles = (styles || []).slice(0, cellCount);
        this.scrollback.push(keptCells.join(""));
        this.scrollbackStyled.push({cells:keptCells, styles:keptStyles});
        if (this.scrollback.length > this.scrollbackLimit) {
          const excess = this.scrollback.length - this.scrollbackLimit;
          this.scrollback.splice(0, excess);
          this.scrollbackStyled.splice(0, excess);
        }
      };
      const resizeScreen = (screen, preserveTranscript = false) => {
        let lines = screen.lines.slice();
        let styles = screen.styles.slice();
        const fullScrollRegion = screen.scrollTop === 0 && screen.scrollBottom === previousRows - 1;
        if (preserveTranscript && fullScrollRegion && nextRows < previousRows) {
          const removedCount = Math.min(lines.length, previousRows - nextRows);
          for (let index = 0; index < removedCount; index += 1) {
            pushScrollback(lines.shift() || [], styles.shift() || []);
          }
          screen.y = Math.max(0, screen.y - removedCount);
          screen.savedY = Math.max(0, screen.savedY - removedCount);
        } else if (nextRows < lines.length) {
          lines = lines.slice(0, nextRows);
          styles = styles.slice(0, nextRows);
        }
        if (preserveTranscript && fullScrollRegion && nextRows > previousRows && this.scrollback.length) {
          const restoreCount = Math.min(nextRows - previousRows, this.scrollback.length);
          const restoredLines = this.scrollback.splice(this.scrollback.length - restoreCount, restoreCount);
          const restoredStyles = this.scrollbackStyled.splice(
            this.scrollbackStyled.length - restoreCount, restoreCount,
          );
          lines.unshift(...restoredStyles.map(record => [...record.cells]));
          styles.unshift(...restoredStyles.map(record => [...record.styles]));
          screen.y += restoreCount;
          screen.savedY += restoreCount;
          // Keep the plain and styled scrollback stores in lock-step. The styled
          // records are authoritative here; restoredLines is removed only to
          // preserve that invariant.
          void restoredLines;
        }
        while (lines.length < nextRows) lines.push(blankLine(nextCols));
        while (styles.length < nextRows) styles.push(blankStyleLine(nextCols));
        for (let index = 0; index < lines.length; index += 1) {
          lines[index] = lines[index].slice(0, nextCols);
          while (lines[index].length < nextCols) lines[index].push(" ");
        }
        screen.lines = lines;
        for (let index = 0; index < styles.length; index += 1) {
          styles[index] = styles[index].slice(0, nextCols);
          while (styles[index].length < nextCols) styles[index].push("");
        }
        screen.styles = styles;
        screen.x = clamp(screen.x, 0, nextCols - 1);
        screen.y = clamp(screen.y, 0, nextRows - 1);
        screen.savedX = clamp(screen.savedX, 0, nextCols - 1);
        screen.savedY = clamp(screen.savedY, 0, nextRows - 1);
        screen.scrollTop = 0;
        screen.scrollBottom = nextRows - 1;
        screen.wrapPending = false;
      };
      this.cols = nextCols;
      this.rows = nextRows;
      resizeScreen(this.main, true);
      resizeScreen(this.alternate, false);
    }

    _scrollUp(count = 1) {
      const screen = this.screen;
      for (let index = 0; index < count; index += 1) {
        const removed = screen.lines.splice(screen.scrollTop, 1)[0];
        const removedStyles = screen.styles.splice(screen.scrollTop, 1)[0];
        screen.lines.splice(screen.scrollBottom, 0, blankLine(this.cols));
        screen.styles.splice(screen.scrollBottom, 0, blankStyleLine(this.cols));
        if (!this.useAlternate && screen.scrollTop === 0 && removed) {
          let cellCount = removed.length;
          while (cellCount > 0 && /^\s*$/u.test(removed[cellCount - 1])) cellCount -= 1;
          const cells = removed.slice(0, cellCount);
          const styles = (removedStyles || []).slice(0, cellCount);
          this.scrollback.push(cells.join(""));
          this.scrollbackStyled.push({cells, styles});
          if (this.scrollback.length > this.scrollbackLimit) {
            const excess = this.scrollback.length - this.scrollbackLimit;
            this.scrollback.splice(0, excess);
            this.scrollbackStyled.splice(0, excess);
          }
        }
      }
    }

    _scrollDown(count = 1) {
      const screen = this.screen;
      for (let index = 0; index < count; index += 1) {
        screen.lines.splice(screen.scrollBottom, 1);
        screen.styles.splice(screen.scrollBottom, 1);
        screen.lines.splice(screen.scrollTop, 0, blankLine(this.cols));
        screen.styles.splice(screen.scrollTop, 0, blankStyleLine(this.cols));
      }
    }

    _lineFeed() {
      const screen = this.screen;
      if (screen.y === screen.scrollBottom) this._scrollUp(1);
      else screen.y = Math.min(this.rows - 1, screen.y + 1);
    }

    _reverseIndex() {
      const screen = this.screen;
      if (screen.y === screen.scrollTop) this._scrollDown(1);
      else screen.y = Math.max(0, screen.y - 1);
    }

    _put(value) {
      const screen = this.screen;
      if (screen.wrapPending) {
        screen.x = 0;
        screen.wrapPending = false;
        this._lineFeed();
      }
      if (isCombining(value) && screen.x > 0) {
        screen.lines[screen.y][screen.x - 1] += value;
        return;
      }
      const width = isWide(value) ? 2 : 1;
      if (screen.x + width > this.cols) {
        screen.x = 0;
        this._lineFeed();
      }
      screen.lines[screen.y][screen.x] = value;
      screen.styles[screen.y][screen.x] = styleKey(this.currentStyle);
      if (width === 2 && screen.x + 1 < this.cols) {
        screen.lines[screen.y][screen.x + 1] = " ";
        screen.styles[screen.y][screen.x + 1] = styleKey(this.currentStyle);
      }
      screen.x += width;
      if (screen.x >= this.cols) {
        screen.x = this.cols - 1;
        screen.wrapPending = true;
      }
    }

    _params(value) {
      const body = value.replace(/^[?>!]/u, "").replace(/[ -/].*$/u, "");
      if (!body) return [0];
      return body.split(";").map(item => item === "" ? 0 : Number(item) || 0);
    }

    _eraseLine(mode) {
      const screen = this.screen;
      if (mode === 1) {
        for (let x = 0; x <= screen.x; x += 1) {
          screen.lines[screen.y][x] = " ";
          screen.styles[screen.y][x] = "";
        }
      } else if (mode === 2) {
        screen.lines[screen.y] = blankLine(this.cols);
        screen.styles[screen.y] = blankStyleLine(this.cols);
      }
      else {
        for (let x = screen.x; x < this.cols; x += 1) {
          screen.lines[screen.y][x] = " ";
          screen.styles[screen.y][x] = "";
        }
      }
    }

    _eraseDisplay(mode) {
      const screen = this.screen;
      if (mode === 3) {
        this.scrollback = [];
        this.scrollbackStyled = [];
        return;
      }
      if (mode === 2) {
        screen.lines = Array.from({length:this.rows}, () => blankLine(this.cols));
        screen.styles = Array.from({length:this.rows}, () => blankStyleLine(this.cols));
        return;
      }
      if (mode === 1) {
        for (let y = 0; y < screen.y; y += 1) {
          screen.lines[y] = blankLine(this.cols);
          screen.styles[y] = blankStyleLine(this.cols);
        }
        const x = screen.x;
        for (let column = 0; column <= x; column += 1) {
          screen.lines[screen.y][column] = " ";
          screen.styles[screen.y][column] = "";
        }
        return;
      }
      const x = screen.x;
      for (let column = x; column < this.cols; column += 1) {
        screen.lines[screen.y][column] = " ";
        screen.styles[screen.y][column] = "";
      }
      for (let y = screen.y + 1; y < this.rows; y += 1) {
        screen.lines[y] = blankLine(this.cols);
        screen.styles[y] = blankStyleLine(this.cols);
      }
    }

    _alternate(enable) {
      if (enable && !this.useAlternate) {
        this.alternate = this._screen();
        this.useAlternate = true;
      } else if (!enable && this.useAlternate) this.useAlternate = false;
    }

    _sgr(params) {
      const values = params.length ? params : [0];
      for (let index = 0; index < values.length; index += 1) {
        const value = values[index];
        if (value === 0) this.currentStyle = {...DEFAULT_STYLE};
        else if (value === 1) this.currentStyle.bold = true;
        else if (value === 2) this.currentStyle.dim = true;
        else if (value === 3) this.currentStyle.italic = true;
        else if (value === 4) this.currentStyle.underline = true;
        else if (value === 7) this.currentStyle.inverse = true;
        else if (value === 9) this.currentStyle.strike = true;
        else if (value === 21) this.currentStyle.bold = false;
        else if (value === 22) { this.currentStyle.bold = false; this.currentStyle.dim = false; }
        else if (value === 23) this.currentStyle.italic = false;
        else if (value === 24) this.currentStyle.underline = false;
        else if (value === 27) this.currentStyle.inverse = false;
        else if (value === 29) this.currentStyle.strike = false;
        else if (value >= 30 && value <= 37) this.currentStyle.foreground = `i:${value - 30}`;
        else if (value === 39) this.currentStyle.foreground = null;
        else if (value >= 40 && value <= 47) this.currentStyle.background = `i:${value - 40}`;
        else if (value === 49) this.currentStyle.background = null;
        else if (value >= 90 && value <= 97) this.currentStyle.foreground = `i:${value - 90 + 8}`;
        else if (value >= 100 && value <= 107) this.currentStyle.background = `i:${value - 100 + 8}`;
        else if ((value === 38 || value === 48) && values[index + 1] === 5 && index + 2 < values.length) {
          const color = `i:${clamp(values[index + 2], 0, 255)}`;
          if (value === 38) this.currentStyle.foreground = color;
          else this.currentStyle.background = color;
          index += 2;
        } else if ((value === 38 || value === 48) && values[index + 1] === 2 && index + 4 < values.length) {
          const color = `r:${clamp(values[index + 2], 0, 255)},${clamp(values[index + 3], 0, 255)},${clamp(values[index + 4], 0, 255)}`;
          if (value === 38) this.currentStyle.foreground = color;
          else this.currentStyle.background = color;
          index += 4;
        }
      }
    }

    _csi(final, raw) {
      const screen = this.screen;
      screen.wrapPending = false;
      const params = this._params(raw);
      const first = params[0] || 0;
      const amount = first || 1;
      const privateMode = raw.startsWith("?");
      switch (final) {
        case "A": screen.y = Math.max(screen.scrollTop, screen.y - amount); break;
        case "B": screen.y = Math.min(screen.scrollBottom, screen.y + amount); break;
        case "C": screen.x = Math.min(this.cols - 1, screen.x + amount); break;
        case "D": screen.x = Math.max(0, screen.x - amount); break;
        case "E": screen.y = Math.min(screen.scrollBottom, screen.y + amount); screen.x = 0; break;
        case "F": screen.y = Math.max(screen.scrollTop, screen.y - amount); screen.x = 0; break;
        case "G": case "`": screen.x = clamp(amount - 1, 0, this.cols - 1); break;
        case "d": screen.y = clamp(amount - 1, 0, this.rows - 1); break;
        case "H": case "f":
          screen.y = clamp((params[0] || 1) - 1, 0, this.rows - 1);
          screen.x = clamp((params[1] || 1) - 1, 0, this.cols - 1);
          break;
        case "J": this._eraseDisplay(first); break;
        case "K": this._eraseLine(first); break;
        case "m": this._sgr(params); break;
        case "L":
          if (screen.y >= screen.scrollTop && screen.y <= screen.scrollBottom) {
            for (let index = 0; index < amount; index += 1) {
              screen.lines.splice(screen.y, 0, blankLine(this.cols));
              screen.styles.splice(screen.y, 0, blankStyleLine(this.cols));
              screen.lines.splice(screen.scrollBottom + 1, 1);
              screen.styles.splice(screen.scrollBottom + 1, 1);
            }
          }
          break;
        case "M":
          if (screen.y >= screen.scrollTop && screen.y <= screen.scrollBottom) {
            for (let index = 0; index < amount; index += 1) {
              screen.lines.splice(screen.y, 1);
              screen.styles.splice(screen.y, 1);
              screen.lines.splice(screen.scrollBottom, 0, blankLine(this.cols));
              screen.styles.splice(screen.scrollBottom, 0, blankStyleLine(this.cols));
            }
          }
          break;
        case "@":
          screen.lines[screen.y].splice(screen.x, 0, ...Array.from({length:amount}, () => " "));
          screen.styles[screen.y].splice(screen.x, 0, ...Array.from({length:amount}, () => ""));
          screen.lines[screen.y].length = this.cols;
          screen.styles[screen.y].length = this.cols;
          break;
        case "P":
          screen.lines[screen.y].splice(screen.x, amount);
          screen.styles[screen.y].splice(screen.x, amount);
          while (screen.lines[screen.y].length < this.cols) screen.lines[screen.y].push(" ");
          while (screen.styles[screen.y].length < this.cols) screen.styles[screen.y].push("");
          break;
        case "X":
          for (let index = 0; index < amount && screen.x + index < this.cols; index += 1) {
            screen.lines[screen.y][screen.x + index] = " ";
            screen.styles[screen.y][screen.x + index] = "";
          }
          break;
        case "S": this._scrollUp(amount); break;
        case "T": this._scrollDown(amount); break;
        case "r":
          screen.scrollTop = clamp((params[0] || 1) - 1, 0, this.rows - 1);
          screen.scrollBottom = clamp((params[1] || this.rows) - 1, screen.scrollTop, this.rows - 1);
          screen.x = 0; screen.y = 0;
          break;
        case "s": screen.savedX = screen.x; screen.savedY = screen.y; break;
        case "u": screen.x = screen.savedX; screen.y = screen.savedY; break;
        case "h": case "l": {
          const enable = final === "h";
          if (privateMode && params.some(value => [47, 1047, 1049].includes(value))) this._alternate(enable);
          if (privateMode && params.includes(25)) this.screen.cursorVisible = enable;
          break;
        }
        default: break;
      }
    }

    write(value) {
      for (const character of String(value || "")) {
        if (this.skipNext) { this.skipNext = false; continue; }
        if (this.parser === "osc") {
          if (character === "\u0007") { this.parser = "normal"; this.oscEscaped = false; }
          else if (this.oscEscaped && character === "\\") { this.parser = "normal"; this.oscEscaped = false; }
          else this.oscEscaped = character === "\u001b";
          continue;
        }
        if (this.parser === "csi") {
          if (/[@-~]/u.test(character)) {
            this._csi(character, this.sequence);
            this.sequence = "";
            this.parser = "normal";
          } else if (this.sequence.length < 128) this.sequence += character;
          else { this.sequence = ""; this.parser = "normal"; }
          continue;
        }
        if (this.parser === "esc") {
          this.parser = "normal";
          if (character === "[") { this.parser = "csi"; this.sequence = ""; continue; }
          if (character === "]") { this.parser = "osc"; this.oscEscaped = false; continue; }
          if (["(", ")", "*", "+"].includes(character)) { this.skipNext = true; continue; }
          if (character === "7") { this.screen.savedX = this.screen.x; this.screen.savedY = this.screen.y; }
          else if (character === "8") { this.screen.x = this.screen.savedX; this.screen.y = this.screen.savedY; }
          else if (character === "D") this._lineFeed();
          else if (character === "M") this._reverseIndex();
          else if (character === "E") { this.screen.x = 0; this._lineFeed(); }
          else if (character === "c") this.reset();
          continue;
        }
        if (character === "\u001b") { this.parser = "esc"; continue; }
        if (character === "\r") { this.screen.x = 0; this.screen.wrapPending = false; continue; }
        if (character === "\n" || character === "\u000b" || character === "\u000c") { this.screen.wrapPending = false; this._lineFeed(); continue; }
        if (character === "\b") { this.screen.wrapPending = false; this.screen.x = Math.max(0, this.screen.x - 1); continue; }
        if (character === "\t") { this.screen.wrapPending = false; this.screen.x = Math.min(this.cols - 1, (Math.floor(this.screen.x / 8) + 1) * 8); continue; }
        if (character < " " || character === "\u007f") continue;
        this._put(character);
      }
      return this.toString();
    }

    toStyledRuns() {
      const trimRecord = (cells, styles) => {
        let cellCount = cells.length;
        while (cellCount > 0 && /^\s*$/u.test(cells[cellCount - 1])) cellCount -= 1;
        return {cells:cells.slice(0, cellCount), styles:(styles || []).slice(0, cellCount)};
      };
      const screenLines = this.screen.lines.map((cells, index) =>
        trimRecord(cells, this.screen.styles[index]));
      while (screenLines.length > 1 && !screenLines[screenLines.length - 1].cells.length) screenLines.pop();
      const records = this.useAlternate
        ? screenLines
        : [...this.scrollbackStyled.map(record => ({
          cells:[...record.cells], styles:[...record.styles],
        })), ...screenLines];
      const runs = [];
      let styleOverflow = false;
      const append = (text, key = "") => {
        if (!text) return;
        if (styleOverflow || (runs.length >= MAX_STYLED_RUNS && runs.at(-1)?.styleKey !== key)) {
          styleOverflow = true;
          const tail = runs.at(-1);
          if (tail?.styleOverflow) tail.text += text;
          else runs.push({text, styleKey:"", style:DEFAULT_STYLE, styleOverflow:true});
          return;
        }
        const previous = runs.at(-1);
        if (previous?.styleKey === key) previous.text += text;
        else runs.push({text, styleKey:key, style:styleFromKey(key)});
      };
      records.forEach((record, lineIndex) => {
        if (lineIndex) append("\n");
        let activeKey = null;
        let text = "";
        record.cells.forEach((cell, cellIndex) => {
          const key = record.styles[cellIndex] || "";
          if (activeKey === null) activeKey = key;
          if (key !== activeKey) {
            append(text, activeKey);
            text = "";
            activeKey = key;
          }
          text += cell;
        });
        append(text, activeKey || "");
      });
      return runs;
    }

    toString() {
      const lines = this.screen.lines.map(rstrip);
      while (lines.length > 1 && !lines[lines.length - 1]) lines.pop();
      return (this.useAlternate ? lines : [...this.scrollback, ...lines]).join("\n");
    }

    cursor() {
      return {x:this.screen.x, y:this.screen.y, visible:this.screen.cursorVisible};
    }
  }

  return {DEFAULT_STYLE, MAX_STYLED_RUNS, TerminalBuffer, segmentStyledRuns};
});
