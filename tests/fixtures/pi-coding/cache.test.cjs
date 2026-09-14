const {test} = require('node:test');
const assert = require('node:assert/strict');
const {TTLCache} = require('./cache.cjs');

test('capacity must be a positive integer', () => {
  for (const value of [0, -1, 1.5, NaN, Infinity, '2', null]) {
    assert.throws(() => new TTLCache(value), RangeError);
  }
});
test('TTL must be finite and nonnegative, without mutating on rejection', () => {
  const c = new TTLCache(2, () => 0);
  c.set('a', 1, 20);
  for (const value of [-1, NaN, Infinity, '20', undefined]) {
    assert.throws(() => c.set('a', 2, value), RangeError);
    assert.equal(c.get('a'), 1);
  }
});
test('expiry is inclusive and zero TTL removes an existing key', () => {
  let now = 10;
  const c = new TTLCache(2, () => now);
  c.set('a', 1, 5);
  now = 14; assert.equal(c.get('a'), 1);
  now = 15; assert.equal(c.get('a'), undefined);
  assert.equal(c.size, 0);
  c.set('a', 2, 10); c.set('a', 3, 0);
  assert.equal(c.get('a'), undefined);
});
test('get refreshes recency without extending TTL', () => {
  let now = 0;
  const c = new TTLCache(2, () => now);
  c.set('a', 1, 10); c.set('b', 2, 20);
  now = 5; assert.equal(c.get('a'), 1);
  c.set('c', 3, 20);
  assert.equal(c.get('b'), undefined);
  now = 10; assert.equal(c.get('a'), undefined);
  assert.equal(c.get('c'), 3);
});
test('overwrite becomes most recent, does not grow, and replaces expiry', () => {
  let now = 0;
  const c = new TTLCache(2, () => now);
  c.set('a', 1, 5); c.set('b', 2, 20);
  now = 2; c.set('a', 3, 20);
  assert.equal(c.size, 2);
  c.set('c', 4, 20);
  assert.equal(c.get('b'), undefined);
  now = 6; assert.equal(c.get('a'), 3);
});
test('expired entries are purged before evicting a live LRU entry', () => {
  let now = 0;
  const c = new TTLCache(2, () => now);
  c.set('live', 1, 100); c.set('short', 2, 1);
  now = 2; c.set('new', 3, 100);
  assert.equal(c.get('live'), 1);
  assert.equal(c.get('new'), 3);
  assert.equal(c.size, 2);
});
test('size counts only live entries, with no explicit reads', () => {
  let now = 0;
  const c = new TTLCache(2, () => now);
  c.set('a', 1, 1); c.set('b', 2, 2);
  now = 2; assert.equal(c.size, 0);
});
test('falsy values, undefined and object keys are preserved', () => {
  const c = new TTLCache(6, () => 0), obj = {};
  for (const [k, v] of [[obj, 0], ['f', false], ['empty', ''], ['null', null], ['undefined', undefined]]) c.set(k, v, 10);
  assert.equal(c.get(obj), 0); assert.equal(c.get({}), undefined);
  assert.equal(c.get('f'), false); assert.equal(c.get('empty'), '');
  assert.equal(c.get('null'), null); assert.equal(c.size, 5);
});
