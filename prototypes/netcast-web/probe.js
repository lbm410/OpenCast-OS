/* Local input research only: no native TV APIs, preferences or external requests. */
(function () {
    var VERSION = "input-001-v2", LIMIT = 16, MAX = 1000000000;
    var selected = 0, interactions = 0, lastKey = 0, maxHandlerMs = 0;
    var startedAt = new Date().getTime();
    var loadMs = Math.max(0, startedAt - openCastStarted);
    var counts = { keydown: 0, keyup: 0, keypress: 0, click: 0, focus: 0 };
    var events = [], droppedEvents = 0, cards = [], pending = null, paused = false, i;
    var ids = ["card0", "card1", "card2", "focusButton", "focusInput", "clearReport", "reloadProbe"];
    var canvas = document.createElement("canvas"), canvas2d = false;
    var capture = typeof document.addEventListener === "function";
    try { canvas2d = !!(canvas.getContext && canvas.getContext("2d")); } catch (ignore) {}
    var features = {
        canvas2d: canvas2d,
        requestAnimationFrame: typeof window.requestAnimationFrame === "function",
        webkitRequestAnimationFrame: typeof window.webkitRequestAnimationFrame === "function",
        mozRequestAnimationFrame: typeof window.mozRequestAnimationFrame === "function",
        json: !!(window.JSON && window.JSON.stringify),
        xhr: typeof window.XMLHttpRequest !== "undefined",
        netCastBack: typeof window.NetCastBack === "function",
        netCastExit: typeof window.NetCastExit === "function",
        captureEvents: capture
    };
    function bounded(value) { return Math.max(0, Math.min(MAX, Math.floor(value) || 0)); }
    function text(id, value) {
        var element = document.getElementById(id);
        if (typeof element.textContent !== "undefined") { element.textContent = value; }
        else { element.innerText = value; }
    }
    function label(element) {
        var j, name;
        if (!element) { return "none"; }
        for (j = 0; j < ids.length; j += 1) {
            if (element === document.getElementById(ids[j])) { return ids[j]; }
        }
        name = String(element.tagName || "none").toLowerCase();
        return /^[a-z][a-z0-9_-]{0,23}$/.test(name) ? name : "unknown";
    }
    function active() { return label(document.activeElement); }
    function metrics() {
        text("metrics", "Events: down " + counts.keydown + " / up " + counts.keyup +
             " / press " + counts.keypress + " / click " + counts.click + " / focus " + counts.focus +
             " | Actions " + interactions + " | Retained " + events.length + " / dropped " + droppedEvents);
        text("focusState", "Active element: " + active() + " | Last key: " + lastKey +
             " | Listener: " + (capture ? "capture" : "bubble fallback"));
        if (events.length) {
            var event = events[events.length - 1];
            text("lastEvent", "Last event: " + event.type + " key=" + event.key +
                 " target=" + event.target + " active=" + event.active + " at " + event.elapsedMs + " ms");
        } else { text("lastEvent", "Last event: none"); }
    }
    function select(index) {
        cards[selected].className = "card";
        selected = index;
        cards[selected].className = "card selected";
    }
    function observe(event) {
        if (paused) { return; }
        event = event || window.event;
        if (!event) { return; }
        var began = new Date().getTime();
        var type = event.type === "focusin" ? "focus" : event.type;
        if (typeof counts[type] !== "number") { return; }
        var target = event.target || event.srcElement;
        var code = type === "keydown" || type === "keyup" || type === "keypress" ?
            Math.min(65535, bounded(event.keyCode || event.which || 0)) : 0;
        counts[type] = bounded(counts[type] + 1);
        if (type === "keydown" || type === "keyup" || type === "keypress") { lastKey = code; }
        if (events.length === LIMIT) { events.shift(); droppedEvents = bounded(droppedEvents + 1); }
        events.push({ type: type, key: code, target: label(target), active: active(),
            phase: capture ? "capture" : "bubble", elapsedMs: bounded(began - startedAt) });
        /* Only our card arrows are consumed. Enter uses the browser's native click. */
        if (type === "keydown" && code >= 37 && code <= 40) {
            for (var j = 0; j < cards.length; j += 1) {
                if (target === cards[j]) {
                    select(OpenCastNavigation.move(j, code, cards.length));
                    cards[selected].focus();
                    if (event.preventDefault) { event.preventDefault(); }
                    event.returnValue = false;
                    break;
                }
            }
        }
        maxHandlerMs = Math.max(maxHandlerMs, bounded(new Date().getTime() - began));
        metrics();
    }
    function snapshot() {
        return {
            probeVersion: VERSION, userAgent: navigator.userAgent,
            viewportWidth: bounded(document.documentElement.clientWidth),
            viewportHeight: bounded(document.documentElement.clientHeight),
            loadMs: bounded(loadMs), keyEvents: counts.keydown, lastKey: lastKey,
            interactions: interactions, maxHandlerMs: maxHandlerMs, features: features,
            eventCounts: counts, events: events, droppedEvents: droppedEvents,
            activeElement: active()
        };
    }
    function stopRequest() {
        if (pending) {
            var old = pending;
            pending = null;
            window.clearTimeout(old.timer);
            old.request.onreadystatechange = null;
            try { old.request.abort(); } catch (ignore) {}
        }
    }
    function report() {
        if (paused) { return; }
        if (pending) { text("message", "A local report is already being saved. Please wait."); return; }
        if (!features.xhr || !features.json) {
            text("message", "Upload unavailable. Record the diagnostic values from the screen."); return;
        }
        try {
            var request = new XMLHttpRequest();
            pending = { request: request, timer: null };
            request.onreadystatechange = function () {
                if (request.readyState === 4 && pending && pending.request === request) {
                    var status = 0;
                    try { status = request.status; } catch (ignore) {}
                    window.clearTimeout(pending.timer);
                    pending = null;
                    request.onreadystatechange = null;
                    text("message", status === 201 ? "Report saved on your Mac. This is an input experiment, not an installed OS." : "Report could not be saved: HTTP " + status);
                }
            };
            request.open("POST", "/report", true);
            request.setRequestHeader("Content-Type", "application/json");
            pending.timer = window.setTimeout(function () {
                if (pending && pending.request === request) {
                    stopRequest(); text("message", "Local report timed out. The probe remains usable.");
                }
            }, 5000);
            text("message", "Saving a report to your local Mac…");
            request.send(window.JSON.stringify(snapshot()));
        } catch (error) {
            stopRequest(); text("message", "Local report unavailable. Record the screen values manually.");
        }
    }
    function clear() {
        stopRequest();
        counts = { keydown: 0, keyup: 0, keypress: 0, click: 0, focus: 0 };
        events = []; droppedEvents = 0; interactions = 0; lastKey = 0; maxHandlerMs = 0;
        startedAt = new Date().getTime();
        text("message", "Session cleared. Click Focus test button, then try the arrows and OK. Saved files on your Mac are unchanged.");
        metrics();
    }
    function action(index) {
        select(index);
        interactions = bounded(interactions + 1);
        if (index === 0) { text("message", "Hello World — native button activation received. Actions: " + interactions); }
        else if (index === 1) { report(); }
        else { text("message", "Use the normal browser Back / Exit / Home control when ready. This page does not intercept those keys."); }
        metrics();
    }
    for (i = 0; i < 3; i += 1) {
        cards[i] = document.getElementById("card" + i);
        (function (index) { cards[index].onclick = function () { action(index); }; }(i));
    }
    document.getElementById("focusButton").onclick = function () {
        this.focus();
        interactions = bounded(interactions + 1);
        text("message", "Focus test button activated. Press each arrow once and OK once; then save the report. Native browser key behavior is preserved here.");
        metrics();
    };
    document.getElementById("clearReport").onclick = clear;
    document.getElementById("reloadProbe").onclick = function () {
        stopRequest(); window.location.reload();
    };
    var types = ["keydown", "keyup", "keypress", "click", "focus"];
    for (i = 0; i < types.length; i += 1) {
        if (capture) { document.addEventListener(types[i], observe, true); }
        else if (document.attachEvent) { document.attachEvent("on" + (types[i] === "focus" ? "focusin" : types[i]), observe); }
        else { document["on" + (types[i] === "focus" ? "focusin" : types[i])] = observe; }
    }
    function suspend() { paused = true; stopRequest(); }
    function resume() { paused = false; metrics(); }
    if (window.addEventListener) {
        window.addEventListener("pagehide", suspend, false);
        window.addEventListener("unload", suspend, false);
        window.addEventListener("pageshow", resume, false);
    } else if (window.attachEvent) { window.attachEvent("onunload", suspend); }
    else { window.onunload = suspend; }
    text("agent", navigator.userAgent);
    text("features", "Viewport " + document.documentElement.clientWidth + " × " + document.documentElement.clientHeight +
         " | Canvas2D " + canvas2d + " | rAF " + features.requestAnimationFrame +
         " / WebKit " + features.webkitRequestAnimationFrame + " / Mozilla " + features.mozRequestAnimationFrame +
         " | Initial script " + loadMs + " ms");
    metrics();
}());
