const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('../../experiments/review_screen/model.js');
const field = {id:'p:f', candidate:'Candidate', candidate_status:'found', engine_status:'ok'};
const payload = {packet_sha256:'a'.repeat(64), packet:{fields:[field]}};
test('pending omitted; invalid acceptance and correction refused', () => {
  assert.match(m.exportToml(payload, new Map()), /reviews = \[\]/);
  for (const candidate of [null, '', ' ', 'x\n', 'x'.repeat(201)]) assert.equal(m.canAccept({...field,candidate}), false);
  assert.equal(m.canAccept({...field,engine_status:'failed'}), false);
  for (const value of ['', 'x\n', 'x\u0085', 'x\u2028', 'x'.repeat(201)]) {
    assert.throws(() => m.exportToml(payload,new Map([[field.id,{action:'correct',value,reason:'why'}]])));
  }
  assert.throws(() => m.exportToml(payload,new Map([['unknown',{action:'accept'}]])));
  assert.throws(() => m.exportToml(payload,new Map([[field.id,{action:'withhold',reason:' '}]])));
  assert.throws(() => m.exportToml(payload,new Map([[field.id,{action:'other'}]])));
  assert.equal(m.canAccept({...field,candidate:'🚀'.repeat(200)}), true);
});
test('timer counts only explicitly active visible session; hidden requires restart', () => {
  let now=0; const timer=new m.SessionTimer(() => now);
  now=100; assert.equal(timer.elapsed(),0);
  timer.start(true); now=250; assert.equal(timer.elapsed(),150);
  timer.visibility(false); now=600; assert.equal(timer.elapsed(),150);
  timer.visibility(true); now=800; assert.equal(timer.elapsed(),150);
  timer.start(false); now=900; assert.equal(timer.elapsed(),150);
  timer.start(true); now=950; timer.pause(); now=1100;
  const record=timer.record(payload.packet_sha256);
  assert.equal(record.active_visible_ms,200);
  assert.equal(record.packet_sha256,payload.packet_sha256);
  assert.equal(record.measurement,'browser_session_time');
  assert.equal(record.authenticated_human_review,false);
});
