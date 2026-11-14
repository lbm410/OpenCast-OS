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
      focus() { document.activeElement = this; } };
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

test('pure navigation respects rows, edges, and the content-to-tabs boundary', () => {
  const move = (index, key, count = 4) => navigation.move('content', index, key, count, 2, 3, 5);
  assert.deepEqual(move(0, 37), { zone: 'content', index: 0 });
  assert.deepEqual(move(1, 39), { zone: 'content', index: 1 });
  assert.deepEqual(move(1, 40), { zone: 'content', index: 3 });
  assert.deepEqual(move(3, 40), { zone: 'content', index: 3 });
  assert.deepEqual(move(2, 38), { zone: 'content', index: 0 });
  assert.deepEqual(move(0, 38), { zone: 'tabs', index: 3 });
  assert.deepEqual(move(0, 40, 1), { zone: 'content', index: 0 });
  assert.equal(navigation.move('content', 0, 39, 0, 2, 0, 5), null);
});

test('native activation and system keys are outside the arrow mapping', () => {
  for (const key of [undefined, NaN, 0, 8, 13, 27, 32, 36, 461, 1000]) {
    assert.equal(navigation.move('content', 0, key, 4, 2, 0, 5), null);
  }
  assert.deepEqual(navigation.move('tabs', 4, 39, 4, 2, 4, 5), { zone: 'tabs', index: 4 });
});

test('default adapter never reports or invokes an available native TV action', () => {
  for (const action of ['launchApp', 'switchInput', 'openUsb', 'browseNetwork', 'unknown', 'toString', 'constructor']) {
    assert.equal(capabilities.query(action).available, false);
    const result = capabilities.invoke(action, 'test');
    assert.equal(result.ok, false);
    assert.equal(result.available, false);
    assert.match(result.message, /unavailable|not implemented/);
  }
});

test('live arrows move between tabs and visible content without wrapping rows', () => {
  const f = fixture();
  assert.equal(f.document.activeElement.id, 'tab-home');
  assert.equal(f.key('tab-home', 39).defaultPrevented, true);
  assert.equal(f.document.activeElement.id, 'tab-apps');
  assert.equal(f.elements['panel-apps'].style.display, 'block');
  f.key('tab-apps', 40);
  assert.equal(f.document.activeElement.id, 'apps-open');
  f.key('apps-open', 39);
  assert.equal(f.document.activeElement.id, 'apps-info');
  f.key('apps-info', 40);
  assert.equal(f.document.activeElement.id, 'apps-info');
  f.key('apps-info', 38);
  assert.equal(f.document.activeElement.id, 'tab-apps');
});

test('Down enters the tab actually focused by native tab traversal', () => {
  const f = fixture();
  f.elements['tab-media'].focus();
  f.key('tab-media', 40);
  assert.equal(f.elements['panel-media'].style.display, 'block');
  assert.equal(f.elements['panel-home'].style.display, 'none');
  assert.equal(f.document.activeElement.id, 'media-usb');
});

test('live Enter has no synthetic action and native click changes a setting once', () => {
  const f = fixture();
  f.click('home-settings');
  assert.equal(f.document.activeElement.id, 'setting-accent');
  assert.equal(f.key('setting-accent', 13).defaultPrevented, undefined);
  assert.equal(f.elements['accent-label'].textContent, 'Mint');
  f.click('setting-accent');
  assert.equal(f.elements['accent-label'].textContent, 'Amber');
  assert.equal(f.writes, 0);
});

test('system keys and unrelated page targets are not intercepted', () => {
  const f = fixture({ legacy: true });
  for (const key of [undefined, NaN, 0, 8, 13, 27, 32, 36, 461, 1000]) {
    const event = f.key('tab-home', key);
    assert.equal(event.defaultPrevented, undefined);
    assert.equal(event.returnValue, true);
  }
  assert.equal(f.key('unrelated', 39).defaultPrevented, undefined);
  f.key('tab-home', 39);
  assert.equal(f.document.activeElement.id, 'tab-apps');
});

test('native-action cards explain unavailability without invented success', () => {
  const f = fixture();
  for (const id of ['apps-open', 'input-hdmi1', 'input-tv', 'media-usb', 'media-network']) {
    f.click(id);
    assert.match(f.elements.message.textContent, /unavailable/);
  }
  assert.equal(f.writes, 0);
});

test('preferences write only after explicit opt-in and remove only the namespaced key', () => {
  const f = fixture();
  f.storage.set('unrelated', 'keep');
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

test('stored choices are validated and loaded without an automatic write', () => {
  const valid = fixture({ saved: '{"version":1,"accent":"amber","contrast":true}' });
  assert.match(valid.document.body.className, /amber high-contrast/);
  assert.equal(valid.writes, 0);
  for (const saved of ['{', 'x'.repeat(257), '{"version":1,"accent":"evil-class","contrast":true}', '{"version":1,"accent":"mint","contrast":"yes"}']) {
    const f = fixture({ saved });
    assert.equal(f.document.body.className, '');
    assert.equal(f.writes, 0);
  }
});

test('blocked storage and failed removal remain truthful in the visible indicator', () => {
  const blocked = fixture({ blockStorage: true });
  blocked.click('setting-storage');
  assert.match(blocked.elements['storage-label'].textContent, /^Off/);
  assert.match(blocked.elements.message.textContent, /unavailable/);
  const removal = fixture({ blockRemoval: true, saved: '{"version":1,"accent":"mint","contrast":false}' });
  removal.click('setting-storage');
  assert.match(removal.elements['storage-label'].textContent, /^On/);
  assert.match(removal.elements.message.textContent, /could not be removed/);
});

test('clock timer is single, stopped on pagehide and resumed on pageshow', () => {
  const f = fixture();
  assert.equal(f.timers.size, 1);
  f.lifecycle.pageshow();
  assert.equal(f.timers.size, 1);
  f.lifecycle.pagehide();
  assert.equal(f.timers.size, 0);
  f.click('setting-accent');
  assert.equal(f.elements['accent-label'].textContent, 'Mint');
  f.lifecycle.pageshow();
  assert.equal(f.timers.size, 1);
});
