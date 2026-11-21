const test = require('node:test');
const assert = require('node:assert/strict');
const {CompressionState, needsVisibility} = require('../../static/js/conversations-compression.js');
const item = (id, keepVisible = false) => ({id: String(id), keepVisible, unread: true});

test('900 contributions retain exact order and contiguous ranges', () => {
  const state = new CompressionState();
  const source = Array.from({length: 900}, (_, i) => item(i + 1, [61, 62, 201].includes(i + 1)));
  const before = JSON.stringify(source);
  const rows = state.project(source);
  assert.deepEqual(rows.map(r => r.items.length), [60, 1, 1, 138, 1, 699]);
  assert.deepEqual(rows.flatMap(r => r.items.map(i => i.id)), source.map(i => i.id));
  assert.equal(JSON.stringify(source), before);
  assert.equal(rows.filter(r => !r.foldable).length, 3);
});
test('expansion survives prepend and does not change unread facts', () => {
  const state = new CompressionState();
  let rows = state.project([item(2), item(3), item(4, true), item(5), item(6)]);
  state.expand(rows[0]);
  rows = state.project([item(1), item(2), item(3), item(4, true), item(5), item(6)]);
  assert.equal(rows[0].expanded, true);
  assert.equal(rows[2].expanded, false);
  assert.ok(rows.flatMap(r => r.items).every(i => i.unread));
  state.collapse(rows[0]);
  assert.equal(state.project(rows.flatMap(r => r.items))[0].expanded, false);
});
test('actions split ranges, equal titles never merge owner identities', () => {
  const state = new CompressionState();
  const rows = state.project([item('a'), item('b', true), item('c'), item('d')]);
  assert.deepEqual(rows.map(r => r.items.map(i => i.id)), [['a'], ['b'], ['c', 'd']]);
  assert.equal(state.project([item('a'), item('a'), item('b')])[0].items.length, 2);
});
test('current results stay visible but ordinary unread information folds', () => {
  assert.equal(needsVisibility({kind: 'poll', lifecycle: 'resolved'}, {reason: 'result'}), true);
  assert.equal(needsVisibility({kind: 'information', unread: true, response_mode: 'none'}, {reason: 'information'}), false);
  assert.equal(needsVisibility({kind: 'information'}, {pending: true}), true);
  assert.equal(needsVisibility({kind: 'question', response_mode: 'free_text', can_respond: true}), true);
  assert.equal(needsVisibility({kind: 'question', response_mode: 'free_text', can_respond: true, attention_reason: null}), false);
});
test('scope reset and large input have deterministic projection', () => {
  const source = Array.from({length: 10000}, (_, i) => item(i, i % 127 === 0));
  const state = new CompressionState();
  const first = state.project(source);
  state.expand(first.find(r => r.foldable));
  state.clear();
  assert.deepEqual(state.project(source), first);
});
