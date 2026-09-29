/* Pure decision validation and a monotonic, explicitly started session timer. */
(function (root) {
  'use strict';
  function text(value, limit) {
    if (typeof value !== 'string' || !value.trim() || [...value].length > limit ||
        /[\u0000-\u001f\u007f\u0085\u2028\u2029]/u.test(value)) {
      throw new Error(`Use nonempty single-line text of at most ${limit} characters.`);
    }
    return value;
  }
  function canAccept(field) {
    try { text(field.candidate, 200); }
    catch (_) { return false; }
    return field.candidate_status === 'found' && field.engine_status === 'ok';
  }
  function exportToml(payload, decisions) {
    const known = new Map(payload.packet.fields.map(field => [field.id, field]));
    for (const id of decisions.keys()) if (!known.has(id)) throw new Error('Unknown field.');
    const rows = [];
    for (const field of payload.packet.fields) {
      const decision = decisions.get(field.id) || {action:'pending'};
      if (decision.action === 'pending') continue;
      const row = {field_id:field.id, action:decision.action};
      if (decision.action === 'accept') {
        if (!canAccept(field)) throw new Error('Only a nonempty found candidate from successful OCR can be accepted.');
      } else if (decision.action === 'correct') {
        row.value = text(decision.value, 200);
        row.reason = text(decision.reason, 500);
      } else if (decision.action === 'withhold') {
        row.reason = text(decision.reason, 500);
      } else throw new Error('Unknown review action.');
      rows.push(row);
    }
    // JSON escapes are valid TOML basic-string escapes for these validated values.
    const quote = value => JSON.stringify(value).replace(/\u007f/g, '\\u007f');
    let result = `packet_sha256 = ${quote(payload.packet_sha256)}\n`;
    if (!rows.length) return result + 'reviews = []\n';
    for (const row of rows) {
      result += '\n[[reviews]]\n';
      for (const [key,value] of Object.entries(row)) result += `${key} = ${quote(value)}\n`;
    }
    return result;
  }
  class SessionTimer {
    constructor(clock = () => performance.now()) { this.clock=clock; this.total=0; this.since=null; }
    start(visible) { if (visible && this.since === null) this.since=this.clock(); }
    pause() { if (this.since !== null) { this.total += Math.max(0,this.clock()-this.since); this.since=null; } }
    visibility(visible) { if (!visible) this.pause(); }
    elapsed() { return Math.floor(this.total + (this.since === null ? 0 : Math.max(0,this.clock()-this.since))); }
    record(digest) { return {schema_version:1,packet_sha256:digest,measurement:'browser_session_time',provenance:'measured',active_visible_ms:this.elapsed(),authenticated_human_review:false,synthetic_development_only:true}; }
  }
  const api = {canAccept, exportToml, SessionTimer};
  if (typeof module !== 'undefined' && module.exports) module.exports=api;
  else root.ReviewModel=api;
})(globalThis);
