/* Static launcher research. Native TV actions remain behind a disconnected adapter. */
(function () {
    var pages = ["home", "apps", "inputs", "media", "settings"];
    var controls = [
        ["home-internet", "home-apps", "home-media", "home-tv", "home-settings"],
        ["apps-browser", "apps-open", "apps-info"],
        ["input-hdmi1", "input-hdmi2", "input-hdmi3", "input-tv"],
        ["media-usb", "media-network"],
        ["setting-accent", "setting-contrast", "setting-storage", "setting-about"]
    ];
    var titles = [
        ["Internet", "Your apps", "Your media", "Live TV", "Settings"],
        ["Internet", "NetCast apps", "App compatibility"],
        ["HDMI 1", "HDMI 2", "HDMI 3", "Live TV"],
        ["USB media", "Home network"],
        ["Accent color", "High contrast", "Remember choices", "About this interface"]
    ];
    var current = 0, selected = [0, 0, 0, 0, 0], accent = "mint", contrast = false, remember = false;
    var preferenceKey = "opencast.shell.preferences.v1", clockTimer = null, paused = false;
    function element(id) { return document.getElementById(id); }
    function text(id, value) {
        var node = element(id);
        if (typeof node.textContent !== "undefined") { node.textContent = value; }
        else { node.innerText = value; }
    }
    function message(value) { text("message", value); }
    function hint() {
        if (current === 4) {
            if (selected[4] === 0) { return (accent === "amber" ? "Amber" : "Mint") + " · Press OK to change"; }
            if (selected[4] === 1) { return (contrast ? "On" : "Off") + " · Press OK to change"; }
            if (selected[4] === 2) { return (remember ? "Saved in this browser" : "This visit only") + " · Press OK to change"; }
        }
        if (current === 2) { return "Press OK to select · Input availability unverified"; }
        return "Press OK to open";
    }
    function details() {
        text("section-label", current === 2 ? "TV / HDMI" : pages[current].toUpperCase());
        text("selection-title", titles[current][selected[current]]);
        text("selection-hint", hint());
    }
    function choose(index, clearMessage) {
        var i;
        selected[current] = index;
        for (i = 0; i < controls[current].length; i += 1) {
            element(controls[current][i]).className = i === index ? "dock-item selected" : "dock-item";
        }
        details();
        if (clearMessage) { message(""); }
    }
    function appearance() {
        document.body.className = (accent === "amber" ? "amber " : "") + (contrast ? "high-contrast" : "");
        element("setting-contrast").setAttribute("aria-pressed", contrast ? "true" : "false");
        element("setting-storage").setAttribute("aria-pressed", remember ? "true" : "false");
        details();
    }
    function save() {
        try {
            if (!window.JSON || !window.JSON.stringify || !window.localStorage) { throw new Error("Unavailable"); }
            window.localStorage.setItem(preferenceKey, window.JSON.stringify({ version: 1, accent: accent, contrast: contrast }));
            return true;
        } catch (ignore) { message("Browser storage is unavailable. Changes last for this visit."); return false; }
    }
    function load() {
        try {
            if (!window.JSON || !window.JSON.parse || !window.localStorage) { return; }
            var raw = window.localStorage.getItem(preferenceKey);
            if (!raw || raw.length > 256) { return; }
            var value = window.JSON.parse(raw);
            if (!value || value.version !== 1 || (value.accent !== "mint" && value.accent !== "amber") || typeof value.contrast !== "boolean") { return; }
            accent = value.accent; contrast = value.contrast; remember = true;
        } catch (ignore) {}
    }
    function changeAppearance(kind) {
        if (kind === "accent") { accent = accent === "mint" ? "amber" : "mint"; }
        else { contrast = !contrast; }
        message("Appearance updated for this page.");
        if (remember && !save()) { remember = false; }
        appearance();
    }
    function toggleStorage() {
        if (remember) {
            try {
                window.localStorage.removeItem(preferenceKey);
                remember = false; message("Saved choices removed. Current appearance lasts for this visit.");
            } catch (ignore) { message("Saved choices could not be removed. Remembering remains on."); }
        } else {
            remember = save();
            if (remember) { message("Appearance saved in this browser only."); }
        }
        appearance();
    }
    function show(index, focusContent) {
        var i;
        current = index;
        for (i = 0; i < pages.length; i += 1) {
            element("panel-" + pages[i]).style.display = i === current ? "block" : "none";
            element("tab-" + pages[i]).className = i === current ? "tab active" : "tab";
            element("tab-" + pages[i]).setAttribute("aria-pressed", i === current ? "true" : "false");
        }
        choose(selected[current], true);
        if (focusContent) { element(controls[current][selected[current]]).focus(); }
    }
    function capability(name, target) { message(OpenCastShellCapabilities.invoke(name, target).message); }
    function activate(id) {
        if (paused) { return; }
        if (id === "home-apps") { show(1, true); }
        else if (id === "home-media") { show(3, true); }
        else if (id === "home-settings") { show(4, true); }
        else if (id === "home-internet" || id === "apps-browser") { capability("launchApp", "browser"); }
        else if (id === "home-tv") { capability("switchInput", "tv"); }
        else if (id === "apps-open") { capability("launchApp", "netcast"); }
        else if (id === "apps-info") { message("TV app support is still being verified. No streaming service compatibility is claimed."); }
        else if (id.indexOf("input-") === 0) { capability("switchInput", id.substring(6)); }
        else if (id === "media-usb") { capability("openUsb", "usb"); }
        else if (id === "media-network") { capability("browseNetwork", "dlna"); }
        else if (id === "setting-accent") { changeAppearance("accent"); }
        else if (id === "setting-contrast") { changeAppearance("contrast"); }
        else if (id === "setting-storage") { toggleStorage(); }
        else if (id === "setting-about") { message("Launcher under development. Not installed on the TV; startup and native controls are not connected."); }
    }
    var i, j;
    for (i = 0; i < pages.length; i += 1) {
        (function (index) {
            element("tab-" + pages[index]).onclick = function () { if (!paused) { show(index, false); this.focus(); } };
        }(i));
        for (j = 0; j < controls[i].length; j += 1) {
            (function (page, index, id) {
                element(id).onfocus = function () { if (!paused && current === page) { choose(index, true); } };
                element(id).onmouseover = function () {
                    if (!paused && current === page && selected[page] !== index) { choose(index, true); }
                };
                element(id).onclick = function () {
                    if (!paused && current === page) { choose(index, false); activate(id); }
                };
            }(i, j, controls[i][j]));
        }
    }
    function keydown(event) {
        if (paused) { return; }
        event = event || window.event;
        if (!event) { return; }
        var code = event.keyCode || event.which, target = event.target || event.srcElement;
        var zone = "", index = -1, next, k;
        /* Enter/Space stay native. Back, Home, Exit and unknown keys are untouched. */
        if (code !== 37 && code !== 38 && code !== 39 && code !== 40) { return; }
        for (k = 0; k < pages.length; k += 1) {
            if (target === element("tab-" + pages[k])) { zone = "tabs"; index = k; break; }
        }
        if (index < 0) {
            for (k = 0; k < controls[current].length; k += 1) {
                if (target === element(controls[current][k])) { zone = "content"; index = k; break; }
            }
        }
        if (index < 0) { return; }
        next = OpenCastShellNavigation.move(zone, index, code, controls[current].length, current, pages.length);
        if (!next) { return; }
        if (next.zone === "tabs") {
            show(next.index, false); element("tab-" + pages[next.index]).focus();
        } else {
            if (zone === "tabs") { show(index, false); next.index = selected[current]; }
            choose(next.index, true); element(controls[current][next.index]).focus();
        }
        if (event.preventDefault) { event.preventDefault(); }
        event.returnValue = false;
    }
    if (document.addEventListener) { document.addEventListener("keydown", keydown, false); }
    else if (document.attachEvent) { document.attachEvent("onkeydown", keydown); }
    else { document.onkeydown = keydown; }
    function clock() {
        if (clockTimer !== null) { window.clearTimeout(clockTimer); clockTimer = null; }
        if (paused) { return; }
        var now = new Date(), hours = now.getHours(), minutes = now.getMinutes();
        var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        var months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        text("clock", (hours < 10 ? "0" : "") + hours + ":" + (minutes < 10 ? "0" : "") + minutes);
        text("date", days[now.getDay()] + ", " + now.getDate() + " " + months[now.getMonth()]);
        clockTimer = window.setTimeout(clock, 60000);
    }
    function suspend() { paused = true; if (clockTimer !== null) { window.clearTimeout(clockTimer); clockTimer = null; } }
    function resume() { paused = false; clock(); }
    if (window.addEventListener) {
        window.addEventListener("pagehide", suspend, false);
        window.addEventListener("unload", suspend, false);
        window.addEventListener("pageshow", resume, false);
    } else if (window.attachEvent) { window.attachEvent("onunload", suspend); }
    else { window.onunload = suspend; }
    load(); appearance(); show(0, true); clock();
}());
