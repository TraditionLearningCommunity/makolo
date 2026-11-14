/* Client-only chronological presentation. No read receipt or mutation here. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MakoloConversationCompression = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  class CompressionState {
    constructor() { this.expandedIds = new Set(); }
    clear() { this.expandedIds.clear(); }
    expand(segment) { segment.items.forEach(item => this.expandedIds.add(item.id)); }
    collapse(segment) { segment.items.forEach(item => this.expandedIds.delete(item.id)); }
    project(orderedItems) {
      const result = [], seen = new Set();
      let run = [];
      const flush = () => {
        if (!run.length) return;
        const items = Object.freeze(run.slice());
        result.push(Object.freeze({
          id: `range:${items[0].id}`, items,
          foldable: items.length > 1,
          expanded: items.length === 1 || items.some(item => this.expandedIds.has(item.id)),
        }));
        run = [];
      };
      for (const item of orderedItems) {
        if (!item || typeof item.id !== 'string' || !item.id || seen.has(item.id)) continue;
        seen.add(item.id);
        if (item.keepVisible) {
          flush();
          result.push(Object.freeze({
            id: `item:${item.id}`, items: Object.freeze([item]),
            foldable: false, expanded: true,
          }));
        } else run.push(item);
      }
      flush();
      return Object.freeze(result);
    }
  }

  function needsVisibility(point, options = {}) {
    if (options.pending || options.editing || options.focused) return true;
    const reason = options.reason ?? point.attention_reason;
    if (['respond', 'acknowledge', 'form', 'resolve', 'result', 'upcoming'].includes(reason)) return true;
    if (point.can_acknowledge === true && point.acknowledged !== true) return true;
    if (point.kind === 'form_request' && point.form_request?.can_respond === true) return true;
    const interactive = point.response_mode != null && point.response_mode !== 'none';
    if (interactive && !Object.prototype.hasOwnProperty.call(point, 'attention_reason') && reason == null) {
      const allowed = options.representedSpaceId == null ? point.can_respond : point.response_window_open;
      if (allowed !== false) return true;
    }
    return false;
  }
  return {CompressionState, needsVisibility};
});
