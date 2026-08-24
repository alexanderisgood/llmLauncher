(function installWorkspaceContext(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.LLMWorkspaceContextCore = api;
})(typeof globalThis === "object" ? globalThis : this, function workspaceContextFactory() {
  "use strict";

  function normalisePath(file, maximumName = 320) {
    const raw = String(file?.webkitRelativePath || "").replace(/\\/g, "/").trim();
    const parts = raw.split("/");
    if (
      raw.startsWith("/") || parts.length < 2
      || parts.some(part => !part || part === "." || part === "..")
    ) return null;
    const root = parts.shift().trim();
    const name = parts.join("/");
    if (
      !root || root === "~" || /^[a-z]:$/i.test(root) || !name
      || `${root}/${name}`.length > maximumName
      || /[\u0000-\u001f\u007f]/.test(`${root}/${name}`)
    ) return null;
    return {root, name};
  }

  function pathPolicy(name, file, options = {}) {
    const lower = String(name || "").toLocaleLowerCase();
    const segments = lower.split("/");
    const base = segments.at(-1) || "";
    const ignoredSegments = options.ignoredSegments || new Set();
    if (segments.some(segment => ignoredSegments.has(segment))) return "ignored";
    if (
      /^\.env(?:\.|$)/.test(base)
      || /^(?:id_rsa|id_ed25519|id_ecdsa)(?:\.|$)/.test(base)
      || /^(?:credentials|service[-_.]?account|secrets?|auth)\.(?:json|ya?ml|toml|ini|cfg)$/.test(base)
      || /\.(?:pem|key|p12|pfx|jks|keystore|kdbx)$/.test(base)
      || new Set([".npmrc", ".pypirc", ".netrc"]).has(base)
    ) return "sensitive";
    if (
      new Set([
        "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock", "poetry.lock",
        "cargo.lock", "gemfile.lock",
      ]).has(base) || /\.min\.(?:js|css)$/.test(base)
    ) return "generated";
    if (typeof options.supported === "function" && !options.supported(file)) return "unsupported";
    const size = Number(file?.size);
    if (!Number.isFinite(size) || size <= 0) return "empty";
    if (size > Number(options.maximumFileBytes || 512 * 1024)) return "large";
    return "ready";
  }

  function candidatePriority(name) {
    const lower = String(name || "").toLocaleLowerCase();
    const base = lower.split("/").at(-1) || "";
    let score = Math.max(0, 8 - lower.split("/").length);
    if (/^readme(?:\.|$)/.test(base)) score += 90;
    if (/^(?:architecture|contributing|agents|changelog)(?:\.|$)/.test(base)) score += 60;
    if (new Set([
      "package.json", "pyproject.toml", "cargo.toml", "go.mod", "requirements.txt",
      "makefile", "dockerfile",
    ]).has(base)) score += 55;
    if (/(?:^|\/)(?:src|app|lib|server|client|tests?)\//.test(lower)) score += 12;
    return score;
  }

  function queryTerms(value, stopWords = new Set(), maximumTerms = 24) {
    const expanded = String(value || "")
      .normalize("NFKC")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .toLocaleLowerCase();
    return [...new Set((expanded.match(/[a-z0-9_$.-]{2,}/g) || [])
      .map(term => term.replace(/^[._-]+|[._-]+$/g, ""))
      .filter(term => term.length >= 2 && !stopWords.has(term)))]
      .slice(0, maximumTerms);
  }

  function fileScore(file, query) {
    const terms = query || [];
    let score = Number(file?.priority || 0) * (terms.length ? .12 : 1);
    const path = String(file?.name || "").toLocaleLowerCase();
    const searchText = String(file?.searchText || "");
    for (const term of terms) {
      if (path === term || path.endsWith(`/${term}`)) score += 80;
      else if (path.includes(term)) score += 40;
      let cursor = searchText.indexOf(term);
      for (let matches = 0; cursor >= 0 && matches < 3; matches += 1) {
        score += matches === 0 ? 18 : 5;
        cursor = searchText.indexOf(term, cursor + term.length);
      }
    }
    return score;
  }

  function excerpt(file, query, characterLimit, format = value => String(value)) {
    const content = String(file?.content || "");
    const searchText = String(file?.searchText || content.toLocaleLowerCase());
    const limit = Math.max(256, Math.floor(characterLimit));
    if (content.length <= limit) return {content, truncated:false};
    let anchor = -1;
    for (const term of query || []) {
      const index = searchText.indexOf(term);
      if (index >= 0 && (anchor < 0 || index < anchor)) anchor = index;
    }
    const bodyLimit = Math.max(128, limit - 180);
    const start = Math.max(0, Math.min(
      content.length - bodyLimit,
      (anchor < 0 ? 0 : anchor) - Math.floor(bodyLimit * .25),
    ));
    const end = Math.min(content.length, start + bodyLimit);
    const marker = `[Launcher excerpt: characters ${format(start + 1)}–${format(end)} of ${format(content.length)}. Omitted text is not available in this request.]\n`;
    return {content:`${marker}${content.slice(start, end)}`, truncated:true};
  }

  function availableContextCharacters(options = {}) {
    const contextTokens = Math.max(2_048, Number(options.contextTokens || 16_384));
    const outputTokens = Math.max(0, Number(options.outputTokens || 4_096));
    const historyCharacters = Math.max(0, Number(options.historyCharacters || 0));
    return Math.max(0, (contextTokens * 3) - (outputTokens * 3) - historyCharacters - 6_000);
  }

  function requestCharacterBudget(options = {}) {
    const contextTokens = Math.max(2_048, Number(options.contextTokens || 16_384));
    const estimatedCapacity = contextTokens * 3;
    const available = Math.max(0, availableContextCharacters(options) - Math.max(0, Number(options.manualCharacters || 0)));
    return Math.max(0, Math.floor(Math.min(
      Number(options.maximumCharacters || 96_000),
      estimatedCapacity * Number(options.contextShare || .22),
      available,
    )));
  }

  return Object.freeze({
    normalisePath,
    pathPolicy,
    candidatePriority,
    queryTerms,
    fileScore,
    excerpt,
    availableContextCharacters,
    requestCharacterBudget,
  });
});
