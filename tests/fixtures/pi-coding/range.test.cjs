const {test} = require('node:test');
const assert = require('node:assert/strict');
const {sumRange} = require('./range.cjs');
test('inclusive positive endpoints',()=>assert.equal(sumRange(2,5),14));
test('single value',()=>assert.equal(sumRange(7,7),7));
test('negative endpoints',()=>assert.equal(sumRange(-4,-2),-9));
test('crosses zero',()=>assert.equal(sumRange(-2,3),3));
test('empty descending range',()=>assert.equal(sumRange(4,2),0));
test('integer validation remains',()=>assert.throws(()=>sumRange(1.5,2),TypeError));
