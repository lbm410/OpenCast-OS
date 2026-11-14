const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

/* A deterministic DOM transport fixture, not a browser or physical-remote emulator. */
function fixture(options = {}) {
  const ids = ['card0', 'card1', 'card2', 'focusButton', 'focusInput',
    'clearReport', 'reloadProbe', 'metrics', 'focusState', 'lastEvent', 'message', 'agent', 'features'];
  const elements = {}, listeners = {}, windowListeners = {}, timers = new Map(), requests = [];
  let timerId = 0, reloads = 0;
  const document = {
    documentElement: { clientWidth: 1276, clientHeight: 603 },
    getElementById(id) { return elements[id]; },
    createElement() { return { getContext() { return {}; } }; }
  };
  function dispatch(type, target, code = 0) {
    const event = { type, target, srcElement: target, keyCode: code, returnValue: true,
      preventDefault() { this.defaultPrevented = true; } };
    for (const entry of listeners[type] || []) entry.fn(event);
    const legacy = document['on' + type];
    if (legacy) legacy(event);
    if (type === 'click' && target.onclick) target.onclick.call(target, event);
    return event;
  }
  if (!options.fallback) document.addEventListener = (type, fn, capture) => {
    (listeners[type] ||= []).push({ fn, capture });
  };
  else if (options.fallback === 'attach') document.attachEvent = (name, fn) => {
    (listeners[name.slice(2)] ||= []).push({ fn, capture: false });
  };
  for (const id of ids) {
    elements[id] = { id, tagName: id === 'focusInput' ? 'INPUT' : 'BUTTON', textContent: '', className: '',
      focus() {
        if (document.activeElement === this) return;
        document.activeElement = this;
        dispatch(options.fallback ? 'focusin' : 'focus', this);
      }
    };
  }
  document.activeElement = { tagName: 'BODY' };
  class Request {
    constructor() { this.readyState = 0; this.status = 0; this.aborted = false; requests.push(this); }
    open(method, url, async) {
      if (options.failOpen) throw new Error('open failed');
      Object.assign(this, { method, url, async });
    }
    setRequestHeader(name, value) { this.header = [name, value]; }
    send(body) { if (options.failSend) throw new Error('send failed'); this.body = body; }
    abort() { this.aborted = true; if (this.onreadystatechange) this.onreadystatechange(); }
    finish(status) { this.status = status; this.readyState = 4; if (this.onreadystatechange) this.onreadystatechange(); }
  }
  const window = {
    JSON: options.noJSON ? undefined : JSON,
    XMLHttpRequest: options.noXHR ? undefined : Request,
    webkitRequestAnimationFrame() {},
    setTimeout(fn) { timers.set(++timerId, fn); return timerId; },
    clearTimeout(id) { timers.delete(id); },
    location: { reload() { reloads++; } },
    addEventListener(type, fn) { (windowListeners[type] ||= []).push(fn); }
  };
  const context = vm.createContext({ window, document, navigator: { userAgent: 'Fixture Chrome/22.0' },
    XMLHttpRequest: window.XMLHttpRequest, openCastStarted: Date.now(), Date, Math });
  for (const filename of ['navigation.js', 'probe.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../prototypes/netcast-web', filename), 'utf8'), context);
  }
  return {
    elements, document, listeners, requests, timers, window,
    dispatch, click(id) { return dispatch('click', elements[id]); },
    report() { dispatch('click', elements.card1); return JSON.parse(requests.at(-1).body); },
    fireWindow(type) { for (const fn of windowListeners[type] || []) fn(); },
    expire() { for (const fn of [...timers.values()]) fn(); },
    get reloads() { return reloads; }
  };
}

test('v2 captures one observer per type and detects prefixed rAF without executing it', () => {
  const f = fixture();
  f.window.webkitRequestAnimationFrame = () => { throw new Error('must not run'); };
  for (const type of ['keydown', 'keyup', 'keypress', 'click', 'focus']) {
    assert.equal(f.listeners[type].length, 1);
    assert.equal(f.listeners[type][0].capture, true);
  }
  const report = f.report();
  assert.equal(report.probeVersion, 'input-001-v2');
  assert.equal(report.features.requestAnimationFrame, false);
  assert.equal(report.features.webkitRequestAnimationFrame, true);
  assert.equal(report.features.captureEvents, true);
  assert.equal(report.keyEvents, 0);
  assert.equal(report.eventCounts.click, 1);
  assert.equal(report.events[0].phase, 'capture');
  assert.equal(f.requests[0].url, '/report');
  assert.equal(f.requests[0].async, true);
});

test('Enter is not synthesized: one native click produces exactly one action', () => {
  const f = fixture(), button = f.elements.card0;
  button.focus();
  const enter = f.dispatch('keydown', button, 13);
  assert.equal(enter.defaultPrevented, undefined);
  assert.match(f.elements.metrics.textContent, /Actions 0/);
  f.dispatch('keypress', button, 13);
  f.dispatch('keyup', button, 13);
  f.click('card0');
  assert.match(f.elements.metrics.textContent, /Actions 1/);
  const r = f.report();
  assert.deepEqual(r.eventCounts, { keydown: 1, keyup: 1, keypress: 1, click: 2, focus: 1 });
  assert.equal(r.interactions, 2); // Hello action plus Save report action.
});

test('only card arrows navigate; test controls and system keys retain native behavior', () => {
  const f = fixture();
  f.elements.card0.focus();
  const arrow = f.dispatch('keydown', f.elements.card0, 39);
  assert.equal(arrow.defaultPrevented, true);
  assert.equal(f.document.activeElement.id, 'card1');
  for (const id of ['focusButton', 'focusInput']) {
    f.elements[id].focus();
    for (const code of [37, 38, 39, 40, 13, 8, 27, 36, 461, 1000]) {
      const event = f.dispatch('keydown', f.elements[id], code);
      assert.equal(event.defaultPrevented, undefined);
      assert.equal(event.returnValue, true);
      assert.equal(f.document.activeElement.id, id);
    }
  }
  for (const code of [8, 27, 36, 461, 1000]) {
    assert.equal(f.dispatch('keydown', f.elements.card0, code).defaultPrevented, undefined);
  }
  const r = f.report();
  assert.equal(r.keyEvents, r.eventCounts.keydown);
  assert.equal(r.activeElement, 'focusInput');
});

test('bounded ring and privacy labels never retain control text, values or unknown IDs', () => {
  const f = fixture();
  const privateElement = { tagName: 'INPUT', id: 'private-secret', value: 'private-value', textContent: 'private-text' };
  f.document.activeElement = privateElement;
  for (let i = 0; i < 40; i++) f.dispatch('keyup', privateElement, 40);
  const r = f.report();
  assert.equal(r.events.length, 16);
  assert.equal(r.droppedEvents, 25);
  assert.equal(r.eventCounts.keyup, 40);
  assert.equal(r.activeElement, 'input');
  assert.equal(r.events[0].target, 'input');
  assert.equal(r.events[0].active, 'input');
  assert.doesNotMatch(JSON.stringify(r), /private-/);
  assert.ok(Buffer.byteLength(JSON.stringify(r)) < 8192);
  for (const event of r.events) {
    assert.match(event.target, /^[A-Za-z][A-Za-z0-9_-]{0,23}$/);
    assert.match(event.active, /^[A-Za-z][A-Za-z0-9_-]{0,23}$/);
  }
});

for (const fallback of ['attach', 'property']) {
  test(`${fallback} fallback counts each event once and normalizes focusin`, () => {
    const f = fixture({ fallback });
    f.elements.focusButton.focus();
    f.dispatch('keydown', f.elements.focusButton, 39);
    const r = f.report();
    assert.equal(r.features.captureEvents, false);
    assert.equal(r.eventCounts.focus, 1);
    assert.equal(r.eventCounts.keydown, 1);
    assert.equal(r.eventCounts.click, 1);
    assert.ok(r.events.every(event => event.phase === 'bubble'));
    assert.equal(r.events[0].type, 'focus');
  });
}

test('clear resets local evidence, aborts pending request and keeps captured snapshots unchanged', () => {
  const f = fixture();
  f.dispatch('keydown', f.elements.focusInput, 39);
  const saved = f.report(), body = f.requests[0].body;
  f.click('clearReport');
  assert.equal(f.requests[0].aborted, true);
  assert.equal(f.requests[0].onreadystatechange, null);
  assert.equal(f.timers.size, 0);
  assert.match(f.elements.metrics.textContent, /down 0.*click 0.*Actions 0.*Retained 0/);
  const fresh = f.report();
  assert.equal(fresh.events.length, 1);
  assert.equal(fresh.keyEvents, 0);
  assert.equal(fresh.droppedEvents, 0);
  assert.equal(saved.keyEvents, 1);
  assert.equal(f.requests[0].body, body);
});

test('single outstanding report, success, timeout and retry are bounded', () => {
  const f = fixture();
  f.report(); f.click('card1');
  assert.equal(f.requests.length, 1);
  assert.equal(f.timers.size, 1);
  f.requests[0].finish(201);
  assert.equal(f.timers.size, 0);
  assert.match(f.elements.message.textContent, /Report saved/);
  f.report(); f.expire();
  assert.equal(f.requests[1].aborted, true);
  assert.equal(f.timers.size, 0);
  assert.match(f.elements.message.textContent, /timed out/);
  f.report();
  assert.equal(f.requests.length, 3);
});

test('pagehide cancels upload, pageshow resumes and reload uses the normal page URL', () => {
  const f = fixture();
  f.report(); f.fireWindow('pagehide');
  assert.equal(f.requests[0].aborted, true);
  assert.equal(f.timers.size, 0);
  f.click('card1');
  assert.equal(f.requests.length, 1);
  f.fireWindow('pageshow'); f.report();
  assert.equal(f.requests.length, 2);
  f.click('reloadProbe');
  assert.equal(f.reloads, 1);
  assert.equal(f.requests[1].aborted, true);
  assert.equal(f.timers.size, 0);
});

for (const option of ['failOpen', 'failSend', 'noJSON', 'noXHR']) {
  test(`${option} fails visibly without an outstanding request timer`, () => {
    const f = fixture({ [option]: true });
    f.click('card1');
    assert.equal(f.timers.size, 0);
    assert.match(f.elements.message.textContent, /unavailable/);
    if (f.requests.length) assert.equal(f.requests[0].aborted, true);
  });
}
