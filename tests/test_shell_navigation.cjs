const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const navigation = require('../prototypes/opencast-shell/navigation.js');
const capabilities = require('../prototypes/opencast-shell/capabilities.js');
const root = path.join(__dirname, '../prototypes/opencast-shell');

function fixture(options = {}) {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const elements = {}, listeners = {}, lifecycle = {}, timers = new Map(), storage = new Map();
  let timerSequence = 0, writes = 0;
  if (options.saved) storage.set('opencast.shell.preferences.v1', options.saved);
  const document = { body: { className: '' }, activeElement: null,
    getElementById(id) { assert.ok(elements[id], `Element ${id} exists`); return elements[id]; } };
  for (const match of html.matchAll(/id="([^"]+)"/g)) {
    const id = match[1];
    elements[id] = { id, textContent: '', style: {}, attributes: {}, className: '',
      setAttribute(key, value) { this.attributes[key] = value; },
      focus() { document.activeElement = this; if (this.onfocus) this.onfocus(); } };
  }
  if (!options.legacy) document.addEventListener = (name, fn) => { listeners[name] = fn; };
  const window = { JSON,
    setTimeout(fn) { const id = ++timerSequence; timers.set(id, fn); return id; },
    clearTimeout(id) { timers.delete(id); },
    addEventListener(name, fn) { lifecycle[name] = fn; },
    localStorage: {
      getItem(key) { if (options.blockStorage) throw new Error('blocked'); return storage.get(key) || null; },
      setItem(key, value) { if (options.blockStorage) throw new Error('blocked'); writes++; storage.set(key, value); },
      removeItem(key) { if (options.blockRemoval) throw new Error('blocked'); storage.delete(key); }
    }
  };
  const sandbox = vm.createContext({ window, document, Date, Math, Error });
  for (const file of ['navigation.js', 'capabilities.js', 'shell.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), sandbox);
  }
  return { elements, document, window, storage, timers, lifecycle,
    get writes() { return writes; },
    click(id) { const node = elements[id]; node.onclick.call(node); },
    key(id, code) {
      const event = { target: elements[id] || { id }, keyCode: code, returnValue: true,
        preventDefault() { this.defaultPrevented = true; } };
      (listeners.keydown || document.onkeydown)(event);
      return event;
    }
  };
}

test('pure horizontal navigation clamps edges and returns to the section bar', () => {
  const move = (index, key, count = 5) => navigation.move('content', index, key, count, 3, 5);
  assert.deepEqual(move(0, 37), { zone: 'content', index: 0 });
  assert.deepEqual(move(4, 39), { zone: 'content', index: 4 });
  assert.deepEqual(move(1, 39), { zone: 'content', index: 2 });
  assert.deepEqual(move(3, 40), { zone: 'content', index: 3 });
  assert.deepEqual(move(2, 38), { zone: 'tabs', index: 3 });
  assert.equal(navigation.move('content', 0, 39, 0, 0, 5), null);
});

test('native activation and system keys remain outside the arrow mapping', () => {
  for (const key of [undefined, NaN, 0, 8, 13, 27, 32, 36, 461, 1000]) {
    assert.equal(navigation.move('content', 0, key, 5, 0, 5), null);
  }
  assert.deepEqual(navigation.move('tabs', 4, 39, 4, 4, 5), { zone: 'tabs', index: 4 });
});

test('default adapter never reports an available native action', () => {
  for (const action of ['launchApp', 'switchInput', 'openUsb', 'browseNetwork', 'unknown', 'toString', 'constructor']) {
    assert.equal(capabilities.query(action).available, false);
    const result = capabilities.invoke(action, 'test');
    assert.equal(result.ok, false);
    assert.equal(result.available, false);
    assert.match(result.message, /not connected|not available/);
  }
});

test('live dock arrows update focus and the selected title, Up reaches the tabs', () => {
  const f = fixture();
  assert.equal(f.document.activeElement.id, 'home-internet');
  assert.equal(f.elements['selection-title'].textContent, 'Internet');
  assert.equal(f.key('home-internet', 39).defaultPrevented, true);
  assert.equal(f.document.activeElement.id, 'home-apps');
  assert.equal(f.elements['selection-title'].textContent, 'Your apps');
  f.key('home-apps', 38);
  assert.equal(f.document.activeElement.id, 'tab-home');
  f.key('tab-home', 39);
  assert.equal(f.document.activeElement.id, 'tab-apps');
  assert.equal(f.elements['panel-apps'].style.display, 'block');
  f.key('tab-apps', 40);
  assert.equal(f.document.activeElement.id, 'apps-browser');
});

test('Down opens the tab actually focused through native tab traversal', () => {
  const f = fixture();
  f.elements['tab-media'].focus();
  f.key('tab-media', 40);
  assert.equal(f.elements['panel-media'].style.display, 'block');
  assert.equal(f.elements['panel-home'].style.display, 'none');
  assert.equal(f.document.activeElement.id, 'media-usb');
});

test('returning to a section preserves its last dock selection', () => {
  const f = fixture();
  f.key('home-internet', 39);
  f.key('home-apps', 38);
  f.key('tab-home', 39);
  f.key('tab-apps', 37);
  f.key('tab-home', 40);
  assert.equal(f.document.activeElement.id, 'home-apps');
});

test('live Enter has no synthetic action; native click updates appearance once', () => {
  const f = fixture();
  f.click('home-settings');
  assert.equal(f.document.activeElement.id, 'setting-accent');
  assert.equal(f.key('setting-accent', 13).defaultPrevented, undefined);
  assert.match(f.elements['selection-hint'].textContent, /^Mint/);
  f.click('setting-accent');
  assert.match(f.elements['selection-hint'].textContent, /^Amber/);
  assert.equal(f.writes, 0);
});

test('system keys, missing codes, and unrelated targets are not intercepted', () => {
  const f = fixture({ legacy: true });
  for (const key of [undefined, NaN, 0, 8, 13, 27, 32, 36, 461, 1000]) {
    const event = f.key('home-internet', key);
    assert.equal(event.defaultPrevented, undefined);
    assert.equal(event.returnValue, true);
  }
  assert.equal(f.key('unrelated', 39).defaultPrevented, undefined);
  f.key('home-internet', 39);
  assert.equal(f.document.activeElement.id, 'home-apps');
});

test('activation displays a short truthful capability notice, never success', () => {
  const f = fixture();
  for (const [section, id] of [['home', 'home-internet'], ['home', 'home-tv'], ['apps', 'apps-open'], ['inputs', 'input-hdmi1'], ['media', 'media-usb'], ['media', 'media-network']]) {
    f.click('tab-' + section);
    assert.equal(f.elements.message.textContent, '');
    f.click(id);
    assert.match(f.elements.message.textContent, /not connected/);
  }
  assert.equal(f.writes, 0);
});

test('pointer selection updates context without stealing keyboard focus or activating', () => {
  const f = fixture();
  f.elements['home-media'].onmouseover();
  assert.equal(f.elements['selection-title'].textContent, 'Your media');
  assert.equal(f.document.activeElement.id, 'home-internet');
  assert.equal(f.elements['panel-home'].style.display, 'block');
  assert.equal(f.elements.message.textContent, '');
});

test('hidden section controls cannot perform an action', () => {
  const f = fixture();
  f.click('setting-accent');
  assert.equal(f.document.body.className, '');
  assert.equal(f.elements['selection-title'].textContent, 'Internet');
  assert.equal(f.key('setting-accent', 39).defaultPrevented, undefined);
});

test('preferences write only after explicit opt-in and remove only the project key', () => {
  const f = fixture();
  f.storage.set('unrelated', 'keep');
  f.click('home-settings');
  f.click('setting-accent');
  f.click('setting-contrast');
  assert.equal(f.writes, 0);
  f.click('setting-storage');
  assert.equal(f.writes, 1);
  assert.deepEqual(JSON.parse(f.storage.get('opencast.shell.preferences.v1')), { version: 1, accent: 'amber', contrast: true });
  f.click('setting-accent');
  assert.equal(f.writes, 2);
  f.click('setting-storage');
  assert.equal(f.storage.has('opencast.shell.preferences.v1'), false);
  assert.equal(f.storage.get('unrelated'), 'keep');
});

test('saved choices are validated and loaded without an automatic write', () => {
  const valid = fixture({ saved: '{"version":1,"accent":"amber","contrast":true}' });
  assert.match(valid.document.body.className, /amber high-contrast/);
  assert.equal(valid.writes, 0);
  for (const saved of ['{', 'x'.repeat(257), '{"version":1,"accent":"evil-class","contrast":true}', '{"version":1,"accent":"mint","contrast":"yes"}']) {
    const f = fixture({ saved });
    assert.equal(f.document.body.className, '');
    assert.equal(f.writes, 0);
  }
});

test('storage errors and failed removal preserve truthful visible state', () => {
  const blocked = fixture({ blockStorage: true });
  blocked.click('home-settings'); blocked.click('setting-storage');
  assert.match(blocked.elements['selection-hint'].textContent, /^This visit only/);
  assert.match(blocked.elements.message.textContent, /unavailable/);
  const removal = fixture({ blockRemoval: true, saved: '{"version":1,"accent":"mint","contrast":false}' });
  removal.click('home-settings'); removal.click('setting-storage');
  assert.match(removal.elements['selection-hint'].textContent, /^Saved in this browser/);
  assert.match(removal.elements.message.textContent, /could not be removed/);
});

test('clock timer is single and suspend/resume does not activate controls', () => {
  const f = fixture();
  assert.equal(f.timers.size, 1);
  f.lifecycle.pageshow(); assert.equal(f.timers.size, 1);
  f.click('home-settings');
  f.lifecycle.pagehide(); assert.equal(f.timers.size, 0);
  f.click('setting-accent');
  assert.match(f.elements['selection-hint'].textContent, /^Mint/);
  f.lifecycle.pageshow(); assert.equal(f.timers.size, 1);
  assert.match(f.elements.date.textContent, /Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday/);
});
