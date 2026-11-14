const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../prototypes/netcast-startup/index.html'), 'utf8');
const source = html.match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1];

function fixture(mode = 'modern') {
  const elements = {}, events = {}, life = {};
  for (const match of html.matchAll(/<div id="([^"]+)">([^<]*)<\/div>/g)) {
    elements[match[1]] = mode === 'legacy' ? {innerText: match[2]} : {textContent: match[2]};
  }
  const document = {getElementById(id) { return elements[id]; }};
  const window = {};
  for (const name of ['XMLHttpRequest', 'fetch', 'localStorage', 'sessionStorage', 'location', 'NetCastExit', 'NetCastBack']) {
    Object.defineProperty(window, name, {get() { throw Error(`Unexpected access: ${name}`); }});
  }
  if (mode === 'modern') {
    document.addEventListener = (name, handler) => { assert.equal(events[name], undefined); events[name] = handler; };
    window.addEventListener = (name, handler) => { life[name] = handler; };
  } else if (mode === 'attach') {
    document.attachEvent = (name, handler) => { events[name.substring(2)] = handler; };
  }
  vm.runInNewContext(source, {window, document}, {timeout: 1000});
  return {window, document, life,
    text(id) { return elements[id].textContent === undefined ? elements[id].innerText : elements[id].textContent; },
    event(name, value) { return (events[name] || document['on' + name])(value); }
  };
}

test('HTML marker and independent color precede the only inline script', () => {
  const beforeScript = html.split('<script')[0];
  assert.match(beforeScript, /<h1[^>]*>HTML LOADED<\/h1>/);
  assert.match(beforeScript, /bgcolor="#006060" text="#ffffff"/);
  assert.match(beforeScript, /JS NOT CONFIRMED/);
  assert.doesNotMatch(html, /<(link|img|svg|iframe)\b|\bsrc=|url\(/i);
  assert.equal((html.match(/<script\b/g) || []).length, 1);
});

test('actual inline code independently marks script, load and lifecycle events', () => {
  const f = fixture();
  assert.equal(f.text('script-state'), 'JS LOADED');
  assert.equal(f.text('load-state'), 'WINDOW LOAD NOT CONFIRMED');
  f.window.onload();
  assert.equal(f.text('load-state'), 'WINDOW LOAD RECEIVED');
  f.life.pageshow(); f.life.pagehide(); f.life.pageshow();
  assert.equal(f.text('life-state'), 'Page shows: 2 | Page hides: 1');
});

test('legacy DOM/event fallbacks execute and count exactly once', () => {
  for (const mode of ['legacy', 'attach']) {
    const f = fixture(mode);
    f.window.event = {keyCode: 13};
    f.event('keydown'); f.event('click'); f.window.onload();
    assert.equal(f.text('script-state'), 'JS LOADED');
    assert.equal(f.text('event-state'), 'Keys: 1 | Last code: 13 | Clicks: 1');
    assert.equal(f.text('load-state'), 'WINDOW LOAD RECEIVED');
  }
});

test('system keys are observed without cancellation or synthetic actions; counts saturate', () => {
  const f = fixture();
  for (const keyCode of [8, 27, 36, 461, 1000]) {
    const event = {keyCode, returnValue: true, preventDefault() { assert.fail('Key intercepted'); }, stopPropagation() { assert.fail('Propagation changed'); }};
    assert.equal(f.event('keydown', event), undefined);
    assert.equal(event.returnValue, true);
  }
  for (let i = 0; i < 1200; i++) { f.event('keydown', {which: 37}); f.event('click'); }
  assert.equal(f.text('event-state'), 'Keys: 999 | Last code: 37 | Clicks: 999');
});

test('event values and error details cannot become arbitrary displayed text', () => {
  const f = fixture();
  for (const value of ['private', NaN, Infinity, -1, 65536, 1.5]) f.event('keydown', {keyCode: value});
  assert.match(f.text('event-state'), /Last code: unknown/);
  assert.equal(f.window.onerror('private message', 'private URL', 42), false);
  assert.equal(f.text('error-state'), 'Script errors: 1 | Last line: 42');
  f.window.onerror('private', 'private', 'private');
  assert.equal(f.text('error-state'), 'Script errors: 2 | Last line: unknown');
});
