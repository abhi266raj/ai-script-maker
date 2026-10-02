/* Node unit tests for the #207 theme-detection JS injected by app.py.
 *
 * Extracts the <script> block containing studioSyncTheme from app.py, runs it
 * against a fake DOM, and verifies detection behaviour:
 *   - dark/light classification from Streamlit's rendered icon color
 *   - the icon's direct theme color wins over inherited (poisoned) values
 *   - no probe => no data-theme is set (never a silent OS fallback)
 *   - after the grace period a visible error banner + console.error appear
 *   - recovery clears the banner and sets data-theme
 *
 * Run: node tests/test_theme_detection_207.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

const APP_PY = path.join(__dirname, "..", "app.py");
const src = fs.readFileSync(APP_PY, "utf8");
const m = src.match(/<script>([\s\S]*?studioSyncTheme[\s\S]*?)<\/script>/);
if (!m) {
  console.error("FAIL: studioSyncTheme script block not found in app.py");
  process.exit(1);
}
const SCRIPT_RAW = m[1];
// The script lives inside a Python """ string: collapse Python-level \\
// escapes so node evaluates exactly what the browser receives.
const SCRIPT = SCRIPT_RAW.replace(/\\\\/g, "\\");

// ---------- tiny fake DOM ----------
function makeEl(tag) {
  const el = {
    tagName: (tag || "div").toUpperCase(),
    children: [],
    attributes: {},
    style: {},
    textContent: "",
    parentNode: null,
    id: "",
    _color: null, // stubbed computed color
    _fill: null, // stubbed computed fill
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(this.attributes, name)
        ? this.attributes[name]
        : null;
    },
    setAttribute(name, val) {
      this.attributes[name] = String(val);
    },
    appendChild(child) {
      child.parentNode = this;
      this.children.push(child);
      return child;
    },
    removeChild(child) {
      const i = this.children.indexOf(child);
      if (i !== -1) this.children.splice(i, 1);
      child.parentNode = null;
      return child;
    },
    querySelectorAll(sel) {
      // supports the probe's simple selectors: 'span, svg, path, i'
      const tags = sel.split(",").map((s) => s.trim().toUpperCase());
      const out = [];
      (function walk(n) {
        for (const c of n.children) {
          if (tags.includes(c.tagName)) out.push(c);
          walk(c);
        }
      })(this);
      return out;
    },
  };
  return el;
}

let failures = 0;
function check(name, cond, extra) {
  if (cond) {
    console.log("ok  - " + name);
  } else {
    failures++;
    console.log("FAIL- " + name + (extra ? " :: " + extra : ""));
  }
}

// Captured interval tick (studioSyncTheme re-probe).
let tick = null;
const errorLogs = [];

// Per-test probe stubs, replaced between scenarios.
let probeStubs = {}; // testid -> button stub (or missing)

function buildEnv() {
  const documentElement = makeEl("html");
  const body = makeEl("body");
  const stApp = makeEl("div");
  const bannerHolder = { el: null }; // tracks appended banner

  const document = {
    readyState: "complete",
    documentElement,
    body,
    _listeners: {},
    addEventListener() {},
    querySelector(sel) {
      if (sel === ".stApp") return stApp;
      const mm = sel.match(/\[data-testid="([^"]+)"\]/);
      if (mm && probeStubs[mm[1]]) return probeStubs[mm[1]];
      return null;
    },
    getElementById(id) {
      return bannerHolder.el && bannerHolder.el.id === id ? bannerHolder.el : null;
    },
    createElement(tag) {
      return makeEl(tag);
    },
  };

  const window = {
    document,
    getComputedStyle(el) {
      return { color: el._color, fill: el._fill };
    },
    console: {
      error(...a) {
        errorLogs.push(a.join(" "));
      },
    },
  };

  // body.appendChild tracks the banner so getElementById can find it.
  const origAppend = body.appendChild.bind(body);
  body.appendChild = (child) => {
    if (child.id === "studio-theme-detection-error") bannerHolder.el = child;
    return origAppend(child);
  };
  const origRemove = body.removeChild.bind(body);
  body.removeChild = (child) => {
    if (bannerHolder.el === child) bannerHolder.el = null;
    return origRemove(child);
  };

  return { document, window, documentElement, body, stApp, bannerHolder };
}

function runScript(env) {
  tick = null;
  errorLogs.length = 0;
  const sandbox = {
    document: env.document,
    window: env.window,
    console: env.window.console,
    setInterval: (fn) => {
      tick = fn;
      return 1;
    },
  };
  const names = Object.keys(sandbox);
  const fn = new Function(...names, SCRIPT);
  fn(...names.map((n) => sandbox[n]));
}

function dataTheme(env) {
  return {
    html: env.documentElement.getAttribute("data-theme"),
    body: env.body.getAttribute("data-theme"),
    stApp: env.stApp.getAttribute("data-theme"),
  };
}

// Builds a probe button stub: icon span carries `iconColor`, an optional
// wrapper span carries `wrapperColor` (defaults to the button's inherited
// color), and the button itself carries `btnColor` (the app's own
// data-theme-driven --ink, which must never be read as the theme).
function makeProbeButton({ iconColor, iconFill, wrapperColor, btnColor }) {
  const btn = makeEl("button");
  btn._color = btnColor || "rgb(31, 26, 20)"; // inherited app --ink (must be ignored)
  btn._fill = "";
  const wrapper = makeEl("span");
  wrapper._color = wrapperColor || btn._color;
  wrapper._fill = "";
  const icon = makeEl("span");
  icon._color = iconColor || null;
  icon._fill = iconFill || "";
  icon.textContent = "keyboard_double_arrow_right";
  wrapper.appendChild(icon);
  btn.appendChild(wrapper);
  return btn;
}

// ---------- scenarios ----------
console.log("--- scenario 1: dark rendered theme -> data-theme=dark ---");
probeStubs = {
  stExpandSidebarButton: makeProbeButton({ iconColor: "rgba(250, 250, 250, 0.6)" }),
};
let env = buildEnv();
runScript(env);
let dt = dataTheme(env);
check("html data-theme=dark", dt.html === "dark", JSON.stringify(dt));
check("body data-theme=dark", dt.body === "dark", JSON.stringify(dt));
check("stApp data-theme=dark", dt.stApp === "dark", JSON.stringify(dt));
check("no error banner", env.bannerHolder.el === null);
check("no console.error", errorLogs.length === 0, errorLogs.join("|"));

console.log("--- scenario 2: light rendered theme -> data-theme=light ---");
probeStubs = {
  stExpandSidebarButton: makeProbeButton({ iconColor: "rgba(49, 51, 63, 0.6)" }),
};
env = buildEnv();
runScript(env);
dt = dataTheme(env);
check("html data-theme=light", dt.html === "light", JSON.stringify(dt));
check("body data-theme=light", dt.body === "light", JSON.stringify(dt));

console.log("--- scenario 3: stale data-theme cannot lock itself in ---");
// Simulates the exact circularity the old code feared: data-theme is wrongly
// 'dark', so the button/wrapper inherit a light-looking app --ink, while
// Streamlit actually rendered the light theme (dark icon). The icon's direct
// theme color must win and correct data-theme back to 'light'.
probeStubs = {
  stExpandSidebarButton: makeProbeButton({
    iconColor: "rgb(49, 51, 63)",
    btnColor: "rgb(250, 250, 250)",
  }),
};
env = buildEnv();
env.documentElement.setAttribute("data-theme", "dark"); // stale/wrong value
runScript(env);
dt = dataTheme(env);
check("icon color wins -> light (no lock-in)", dt.html === "light", JSON.stringify(dt));

console.log("--- scenario 4: collapse-button probe used when expand absent ---");
probeStubs = {
  stSidebarCollapseButton: makeProbeButton({ iconColor: "rgb(250, 250, 250)" }),
};
env = buildEnv();
runScript(env);
dt = dataTheme(env);
check("fallback probe -> dark", dt.html === "dark", JSON.stringify(dt));

console.log("--- scenario 5: svg fill fallback ---");
probeStubs = {
  stExpandSidebarButton: (() => {
    const btn = makeEl("button");
    btn._color = "rgb(31, 26, 20)";
    const svg = makeEl("svg");
    svg._color = "rgb(31, 26, 20)"; // inherits, must be skipped
    svg._fill = "rgb(250, 250, 250)"; // direct theme fill
    btn.appendChild(svg);
    return btn;
  })(),
};
env = buildEnv();
runScript(env);
dt = dataTheme(env);
check("fill fallback -> dark", dt.html === "dark", JSON.stringify(dt));

console.log("--- scenario 6: no probe -> loud failure, never silent fallback ---");
probeStubs = {};
env = buildEnv();
runScript(env);
dt = dataTheme(env);
check("data-theme left unset (html)", dt.html === null, JSON.stringify(dt));
check("data-theme left unset (body)", dt.body === null, JSON.stringify(dt));
check("no banner during grace period", env.bannerHolder.el === null);
// exhaust the grace period: 20 ticks
for (let i = 0; i < 20; i++) tick();
check("banner shown after grace", env.bannerHolder.el !== null);
check("banner has role=alert", env.bannerHolder.el.getAttribute("role") === "alert");
check(
  "banner mentions #207",
  (env.bannerHolder.el.textContent || "").includes("#207")
);
check("console.error called", errorLogs.length > 0, errorLogs.join("|"));
check(
  "console.error never mentions OS fallback as a guess",
  !errorLogs.some((l) => /guessing|fallback to the OS value/i.test(l) && !/instead of guessing/.test(l))
);
dt = dataTheme(env);
check("data-theme STILL unset after failure", dt.html === null, JSON.stringify(dt));

console.log("--- scenario 7: recovery clears banner and applies theme ---");
// banner already up from scenario 6; now the probe appears (late render).
probeStubs = {
  stExpandSidebarButton: makeProbeButton({ iconColor: "rgb(49, 51, 63)" }),
};
tick(); // one more probe tick with the probe present
check("banner removed on recovery", env.bannerHolder.el === null);
dt = dataTheme(env);
check("data-theme=light after recovery", dt.html === "light", JSON.stringify(dt));

console.log("--- scenario 8: luminance unit checks via pure functions ---");
// Re-extract the pure helpers and test them directly.
const helpers = new Function(
  SCRIPT.match(/function studioParseRgb[\s\S]*?\n    \}/)[0] +
    "\n" +
    SCRIPT.match(/function studioLuminance[\s\S]*?\n    \}/)[0] +
    "\nreturn { studioParseRgb, studioLuminance };"
)();
check("parse rgb()", JSON.stringify(helpers.studioParseRgb("rgb(49, 51, 63)")) === "[49,51,63]");
check("parse rgba()", JSON.stringify(helpers.studioParseRgb("rgba(250, 250, 250, 0.6)")) === "[250,250,250]");
check("reject garbage", helpers.studioParseRgb("none") === null);
check("reject empty", helpers.studioParseRgb("") === null);
const lum = (s) => helpers.studioLuminance(helpers.studioParseRgb(s));
check("white is luminous", lum("rgb(255, 255, 255)") > 0.9);
check("black is dark", lum("rgb(0, 0, 0)") < 0.05);
check("streamlit light bodyText classifies light", lum("rgb(49, 51, 63)") < 0.5);
check("streamlit dark bodyText classifies dark", lum("rgb(250, 250, 250)") > 0.5);

console.log(failures === 0 ? "\nALL NODE CHECKS PASSED" : `\n${failures} NODE CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
