const test = require('node:test');
const assert = require('node:assert/strict');
const nav = require('../prototypes/netcast-web/navigation.js');

test('D-pad clamps at the first and last card', () => {
  assert.equal(nav.move(0, 37, 3), 0);
  assert.equal(nav.move(2, 39, 3), 2);
  assert.equal(nav.move(1, 38, 3), 0);
  assert.equal(nav.move(1, 40, 3), 2);
});
test('Back, Home, Enter and unknown keys do not move focus', () => {
  for (const code of [8, 13, 27, 36, 461, 1000]) assert.equal(nav.move(1, code, 3), 1);
});
test('Empty navigation has a defined index', () => assert.equal(nav.move(0, 39, 0), 0));
