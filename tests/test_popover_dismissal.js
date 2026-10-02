// Behavioral test for the popover outside-click dismissal guard.
// Stubs a minimal DOM and verifies: outside click -> Escape dispatched;
// inside clicks / no popover -> silent.
const fs = require('fs');
const APP = require('path').resolve(__dirname, '..', 'app.py');
const MARK = '_studioPopoverDismissGuard';
const _s = fs.readFileSync(APP, 'utf8');
const _i = _s.indexOf(MARK);
const src = _s.slice(_s.lastIndexOf('<script>', _i) + '<script>'.length, _s.indexOf('</script>', _i));

function makeEnv({ popoverOpen }) {
  const dispatched = [];
  const listeners = {};
  function makeEl(selectors) {
    return {
      _sels: selectors,
      closest(sel) { return this._sels.includes(sel) ? this : null; },
      parentElement: null,
    };
  }
  const body = popoverOpen ? makeEl(['[data-testid="stPopoverBody"]']) : null;
  const document = {
    querySelector(sel) {
      if (sel === '[data-testid="stPopoverBody"]') return body;
      return null;
    },
    addEventListener(type, fn, capture) {
      listeners[type] = listeners[type] || [];
      listeners[type].push({ fn, capture });
    },
    dispatchEvent(ev) { dispatched.push(ev); return true; },
  };
  const window = {};
  function Element() {}
  function KeyboardEvent(type, init) {
    this.type = type; this.key = init.key;
    this.bubbles = init.bubbles; this.cancelable = init.cancelable;
  }
  const sandbox = { document, window, Element, KeyboardEvent, console };
  const vm = require('vm');
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);
  return { dispatched, listeners, makeEl, document };
}

let failures = 0;
function check(name, cond) {
  console.log((cond ? 'PASS' : 'FAIL') + ' - ' + name);
  if (!cond) failures++;
}

// 1. Outside click with popover open -> Escape dispatched
{
  const env = makeEnv({ popoverOpen: true });
  const outside = env.makeEl([]);
  env.listeners.click[0].fn({ target: outside });
  check('outside click dispatches Escape',
    env.dispatched.length === 1 && env.dispatched[0].key === 'Escape' && env.dispatched[0].bubbles === true);
  check('listener attached in capture phase', env.listeners.click[0].capture === true);
}

// 2. Click inside trigger -> silent
{
  const env = makeEnv({ popoverOpen: true });
  const inside = env.makeEl(['[data-testid="stPopover"]']);
  env.listeners.click[0].fn({ target: inside });
  check('trigger click does not dispatch', env.dispatched.length === 0);
}

// 3. Click inside popover body -> silent
{
  const env = makeEnv({ popoverOpen: true });
  const inside = env.makeEl(['[data-testid="stPopoverBody"]']);
  env.listeners.click[0].fn({ target: inside });
  check('body click does not dispatch', env.dispatched.length === 0);
}

// 4. Click inside a nested overlay root (e.g. selectbox dropdown) -> silent
{
  const env = makeEnv({ popoverOpen: true });
  const inside = env.makeEl(['[data-st-overlay-root="true"]']);
  env.listeners.click[0].fn({ target: inside });
  check('overlay-root click does not dispatch', env.dispatched.length === 0);
}

// 5. No popover open -> silent even on outside click
{
  const env = makeEnv({ popoverOpen: false });
  const outside = env.makeEl([]);
  env.listeners.click[0].fn({ target: outside });
  check('no popover open -> silent', env.dispatched.length === 0);
}

// 6. Guard is idempotent: re-running the script does not double-attach
{
  const vm = require('vm');
  const dispatched = [];
  const listeners = {};
  const win = {};
  function makeEl(selectors) {
    return { _sels: selectors, closest(sel) { return this._sels.includes(sel) ? this : null; }, parentElement: null };
  }
  const document = {
    querySelector(sel) { return sel === '[data-testid="stPopoverBody"]' ? makeEl(['[data-testid="stPopoverBody"]']) : null; },
    addEventListener(type, fn, capture) { (listeners[type] = listeners[type] || []).push({ fn, capture }); },
    dispatchEvent(ev) { dispatched.push(ev); return true; },
  };
  function Element() {}
  function KeyboardEvent(type, init) { this.type = type; this.key = init.key; }
  const sb = { document, window: win, Element, KeyboardEvent, console };
  vm.createContext(sb);
  vm.runInContext(src, sb);
  vm.runInContext(src, sb);
  vm.runInContext(src, sb);
  check('triple execution attaches exactly one click listener', (listeners.click || []).length === 1);
}

process.exit(failures ? 1 : 0);
