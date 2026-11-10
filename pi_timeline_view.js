(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LLMPiTimelineView = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function browserArtifactUrls(item) {
    if (item?.kind !== "toolResult" || !/^(?:Result|Completed) · browser_check$/.test(item.title || "")) return [];
    let result;
    try { result = JSON.parse(item.text); } catch { return []; }
    const candidates = Array.isArray(result?.results) ? result.results.slice(0, 12) : [result];
    const urls = new Set();
    for (const candidate of candidates) {
      if (candidate?.saved !== true || candidate.mimeType !== "image/png" || typeof candidate.path !== "string") continue;
      // Only references produced inside a launcher run become previews. Never
      // render a tool-supplied URL or expose arbitrary filesystem paths to img.
      const match = /^\/[^\0?#]*\/runs\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\/browser\/(\d{13}-[a-f0-9]{8}\.png)$/.exec(candidate.path);
      if (match) urls.add(`/api/browser-artifact?runId=${encodeURIComponent(match[1])}&name=${encodeURIComponent(match[2])}`);
    }
    return [...urls];
  }

  function createTimelineView({document, core:PiTimelineCore, formatTimestamp:formatChatTimestamp}) {
    let protocol = "pi-rpc";
    let previewsVisible = true;

    function releaseBrowserPreviewResources(parent) {
      // Safari may retain decoded image surfaces after a detached <img> is
      // removed. Clearing the source before removal releases the element's
      // resource while keeping the saved artifact link available to reopen.
      parent?.querySelectorAll?.(".agent-pi-browser-previews img").forEach(image => {
        image.removeAttribute("src");
        image.removeAttribute("srcset");
      });
    }

    function updateBrowserPreviews(parent, item) {
      const urls = browserArtifactUrls(item);
      const existing = parent.querySelector(".agent-pi-browser-previews");
      const key = urls.join("\n");
      if (existing?.dataset.artifacts === key) return;
      if (existing) {
        releaseBrowserPreviewResources(parent);
        existing.remove();
      }
      if (!urls.length) return;
      const previews = document.createElement("div");
      previews.className = "agent-pi-browser-previews";
      previews.dataset.artifacts = key;
      previews.style.padding = "0 12px 12px";
      for (const [index, url] of urls.entries()) {
        const figure = document.createElement("figure");
        figure.style.margin = "8px 0 0";
        const screenshot = document.createElement("img");
        screenshot.dataset.previewUrl = url;
        if (previewsVisible && parent.open) screenshot.src = url;
        screenshot.alt = urls.length > 1 ? `Browser screenshot ${index + 1}` : "Browser screenshot";
        screenshot.loading = "lazy";
        screenshot.decoding = "async";
        screenshot.style.cssText = "display:block;max-width:100%;max-height:480px;object-fit:contain";
        const caption = document.createElement("figcaption");
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = urls.length > 1 ? `Open screenshot ${index + 1}` : "Open screenshot";
        caption.append(link);
        figure.append(screenshot, caption);
        previews.append(figure);
      }
      parent.append(previews);
    }

    function restoreBrowserPreviewResources(parent) {
      parent.querySelectorAll(".agent-pi-browser-previews img").forEach(image => {
        if (!image.hasAttribute("src")) image.src = image.dataset.previewUrl;
      });
    }

    function setVisible(timeline, visible) {
      visible = Boolean(visible);
      if (previewsVisible === visible) return;
      previewsVisible = visible;
      if (!visible) releaseBrowserPreviewResources(timeline);
      else timeline.querySelectorAll("details[open]").forEach(restoreBrowserPreviewResources);
    }

    function clear(timeline) {
      releaseBrowserPreviewResources(timeline);
      timeline.replaceChildren();
      timeline.removeAttribute("data-console-surface");
    }

    function appendPiTimelineTimestamp(parent, value) {
      const formatted = formatChatTimestamp(value);
      if (!formatted) return;
      const time = document.createElement("time");
      time.className = "agent-pi-event-time";
      time.dateTime = formatted.timestamp;
      time.textContent = formatted.short;
      time.title = formatted.long;
      parent.append(time);
    }

    function appendPiTimelineHeading(parent, label, title = "", createdAt = "") {
      const heading = document.createElement("header");
      const kind = document.createElement("strong");
      kind.textContent = label;
      heading.append(kind);
      if (title) {
        const detail = document.createElement("span");
        detail.textContent = title;
        heading.append(detail);
      }
      appendPiTimelineTimestamp(heading, createdAt);
      parent.append(heading);
    }

    function piTimelineBody(text) {
      const body = document.createElement("div");
      body.className = "agent-pi-event-body";
      body.textContent = text || "…";
      return body;
    }

    function updateExpandableBody(details) {
      // Keep the journal as the source of truth. Closed tool results need no
      // duplicate DOM text; reopening uses the latest item, including updates
      // received while the disclosure was closed.
      details.querySelector(".agent-pi-event-body").textContent = details.open
        ? PiTimelineCore.toolDisplayText(details.piTimelineItem) || "…" : "";
    }

    function piTimelineExpandableEvent(item, label, tone, open) {
      const details = document.createElement("details");
      details.className = `agent-pi-event agent-pi-event-${tone}`;
      details.dataset.timelineKey = item.key;
      details.dataset.toolActive = String(PiTimelineCore.toolIsActive(item));
      details.setAttribute("role", "listitem");
      details.open = open;
      details.piTimelineItem = item;
      const summary = document.createElement("summary");
      const icon = document.createElement("span");
      icon.className = "agent-pi-event-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = tone === "thinking" ? "✦" : tone === "tool-result" ? "✓" : "⌘";
      const copy = document.createElement("span");
      const kind = document.createElement("strong");
      kind.textContent = label;
      const title = document.createElement("small");
      title.textContent = item.title || (tone === "thinking" ? "Reasoning trace" : "Details");
      copy.append(kind, title);
      const disclosure = document.createElement("i");
      disclosure.setAttribute("aria-hidden", "true");
      disclosure.textContent = "⌄";
      summary.append(icon, copy, disclosure);
      appendPiTimelineTimestamp(kind, item.createdAt);
      details.append(summary, piTimelineBody(""));
      updateExpandableBody(details);
      details.addEventListener("toggle", () => {
        updateExpandableBody(details);
        if (!previewsVisible || !details.open || !details.isConnected) {
          releaseBrowserPreviewResources(details);
          return;
        }
        restoreBrowserPreviewResources(details);
      });
      updateBrowserPreviews(details, item);
      return details;
    }

    function piTimelineEventElement(item, expanded) {
      if (item.kind === "summary") {
        const summary = document.createElement("div");
        summary.className = "agent-pi-prompt-summary";
        summary.dataset.timelineKey = item.key;
        summary.setAttribute("role", "listitem");
        summary.title = `${PiTimelineCore.agentLabel(protocol)}-reported usage across the model replies and tool steps in this prompt. Input includes cached tokens and repeated conversation context; output includes thinking. Elapsed time includes tools and retries. These totals are not context-window usage.`;
        const label = document.createElement("strong");
        label.textContent = item.title || "Complete";
        summary.append(label);
        appendPiTimelineTimestamp(label, item.createdAt);
        for (const value of item.text.split(" · ")) {
          const metric = document.createElement("span");
          metric.textContent = value;
          summary.append(metric);
        }
        return summary;
      }
      if (item.kind === "thinking") {
        const open = PiTimelineCore.thinkingIsOpen(item.key, expanded);
        return piTimelineExpandableEvent(item, "Thinking", "thinking", open);
      }
      if (item.kind === "toolCall" || item.kind === "toolResult") {
        const tone = item.kind === "toolResult" ? "tool-result" : "tool-call";
        const label = item.kind === "toolResult" ? "Tool result" : "Tool call";
        return piTimelineExpandableEvent(item, label, tone,
          PiTimelineCore.toolIsOpen(item, expanded.tools?.get(item.key)));
      }

      const article = document.createElement("article");
      const tone = {
        user:"user", answer:"answer", notice:"notice", error:"error", queue:"queue",
      }[item.kind] || "notice";
      article.className = `agent-pi-event agent-pi-event-${tone}`;
      article.dataset.timelineKey = item.key;
      article.setAttribute("role", "listitem");
      const label = {
        user:"You", answer:PiTimelineCore.agentLabel(protocol), notice:"Notice", error:"Needs attention", queue:"Queue",
      }[item.kind] || "Update";
      appendPiTimelineHeading(article, label, item.title, item.createdAt);
      article.append(piTimelineBody(item.text));
      return article;
    }

    function agentPiTimelineScrollAnchor(viewport, timeline) {
      const viewportTop = viewport.getBoundingClientRect().top;
      for (const element of timeline.children) {
        if (!element.dataset.timelineKey) continue;
        const bounds = element.getBoundingClientRect();
        if (bounds.bottom <= viewportTop) continue;
        return {
          key:element.dataset.timelineKey,
          top:bounds.top - viewportTop,
        };
      }
      return null;
    }

    function restoreAgentPiTimelineAnchor(viewport, timeline, anchor, previousTop) {
      if (!anchor) {
        viewport.scrollTop = Math.max(0, Number(previousTop) || 0);
        return;
      }
      const viewportTop = viewport.getBoundingClientRect().top;
      const element = [...timeline.children].find(candidate => (
        candidate.dataset.timelineKey === anchor.key
      ));
      if (!element) {
        viewport.scrollTop = Math.max(0, Number(previousTop) || 0);
        return;
      }
      viewport.scrollTop = PiTimelineCore.anchoredScrollTop(
        previousTop,
        anchor.top,
        element.getBoundingClientRect().top - viewportTop,
      );
    }

    function samePresentation(a, b) {
      return a === b || Boolean(a && b && a.kind === b.kind && a.text === b.text
        && a.title === b.title && a.createdAt === b.createdAt);
    }

    function updateNode(node, item) {
      const previous = node?.piTimelineItem;
      if (samePresentation(previous, item)) return node;
      if (previous && previous.kind === item.kind && item.kind !== "summary"
          && previous.title === item.title && previous.createdAt === item.createdAt) {
        // Streaming changes one body. Preserve its disclosure, focus and DOM
        // identity, along with every completed message surrounding it.
        node.piTimelineItem = item;
        if (node.tagName === "DETAILS") updateExpandableBody(node);
        else node.querySelector(".agent-pi-event-body").textContent = PiTimelineCore.toolDisplayText(item) || "…";
        updateBrowserPreviews(node, item);
        return node;
      }
      const expanded = new Map();
      expanded.tools = new Map();
      if (node?.tagName === "DETAILS") {
        expanded.set(item.key, node.open);
        expanded.tools.set(item.key, {
          open:node.open, active:node.dataset.toolActive === "true",
        });
      }
      const replacement = piTimelineEventElement(item, expanded);
      replacement.piTimelineItem = item;
      return replacement;
    }

    function render(timeline, items, {viewport, surfaceId, preserveScroll = true, followTail = true, protocol:nextProtocol = "pi-rpc"}) {
      protocol = nextProtocol;
      const previousTop = viewport.scrollTop;
      const anchor = preserveScroll && !followTail
        ? agentPiTimelineScrollAnchor(viewport, timeline) : null;
      const existing = new Map(timeline.dataset.consoleSurface === surfaceId && timeline.dataset.agentProtocol === protocol
        ? [...timeline.children].map(node => [node.dataset.timelineKey, node]) : []);
      timeline.dataset.consoleSurface = surfaceId;
      timeline.dataset.agentProtocol = protocol;
      let cursor = timeline.firstElementChild;
      for (const item of items) {
        // Queue updates remain in the journal, but an empty queue needs no card.
        if (item.kind === "queue" && item.text === "No queued messages") continue;
        const oldNode = existing.get(item.key);
        const node = updateNode(oldNode, item);
        if (oldNode && node !== oldNode) {
          releaseBrowserPreviewResources(oldNode);
          if (cursor === oldNode) cursor = node;
          oldNode.replaceWith(node);
        }
        if (node !== cursor) timeline.insertBefore(node, cursor);
        cursor = node.nextElementSibling;
      }
      while (cursor) {
        const next = cursor.nextElementSibling;
        releaseBrowserPreviewResources(cursor);
        cursor.remove();
        cursor = next;
      }
      if (followTail) viewport.scrollTop = viewport.scrollHeight;
      else restoreAgentPiTimelineAnchor(viewport, timeline, anchor, previousTop);
    }

    return {render, clear, setVisible};
  }

  return {createTimelineView, browserArtifactUrls};
});
