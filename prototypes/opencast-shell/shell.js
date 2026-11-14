/* Browser-only launcher prototype. All TV actions cross the explicit adapter. */
(function () {
    var pages = ["home", "apps", "inputs", "media", "settings"];
    var controls = [
        ["home-apps", "home-inputs", "home-media", "home-settings"],
        ["apps-open", "apps-info"],
        ["input-hdmi1", "input-hdmi2", "input-hdmi3", "input-tv"],
        ["media-usb", "media-network"],
        ["setting-accent", "setting-contrast", "setting-storage", "setting-about"]
    ];
    var current = 0, accent = "mint", contrast = false, remember = false;
    var preferenceKey = "opencast.shell.preferences.v1", clockTimer = null, paused = false;
    function element(id) { return document.getElementById(id); }
    function text(id, value) {
        var node = element(id);
        if (typeof node.textContent !== "undefined") { node.textContent = value; }
        else { node.innerText = value; }
    }
    function message(value) { text("message", value); }
    function appearance() {
        document.body.className = (accent === "amber" ? "amber " : "") + (contrast ? "high-contrast" : "");
        text("accent-label", accent === "amber" ? "Amber" : "Mint");
        text("contrast-label", contrast ? "On" : "Off");
        text("storage-label", remember ? "On · saved in this browser" : "Off · this visit only");
        element("setting-contrast").setAttribute("aria-pressed", contrast ? "true" : "false");
        element("setting-storage").setAttribute("aria-pressed", remember ? "true" : "false");
    }
    function save() {
        try {
            if (!window.JSON || !window.JSON.stringify || !window.localStorage) { throw new Error("Unavailable"); }
            window.localStorage.setItem(preferenceKey, window.JSON.stringify({ version: 1, accent: accent, contrast: contrast }));
            return true;
        } catch (ignore) {
            message("Browser storage is unavailable. Your appearance changes apply to this visit only.");
            return false;
        }
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
        message("Appearance updated for this page. TV picture settings are unchanged.");
        if (remember && !save()) { remember = false; }
        appearance();
    }
    function toggleStorage() {
        if (remember) {
            try {
                window.localStorage.removeItem(preferenceKey);
                remember = false;
                message("Saved OpenCast choices removed from this browser. Current appearance lasts for this visit.");
            } catch (ignore) { message("Saved choices could not be removed. The saved-preference indicator remains on."); }
        } else {
            remember = save();
            if (remember) { message("Appearance choices saved in this browser only. No TV system setting was changed."); }
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
        message(index === 4 ? "Appearance controls work locally. Remembering choices is optional." : "Choose a section or item. Native TV controls are not connected.");
        if (focusContent) { element(controls[current][0]).focus(); }
    }
    function capability(name, target) {
        var result = OpenCastShellCapabilities.invoke(name, target);
        message(result.message);
    }
    function activate(id) {
        if (paused) { return; }
        if (id === "home-apps") { show(1, true); }
        else if (id === "home-inputs") { show(2, true); }
        else if (id === "home-media") { show(3, true); }
        else if (id === "home-settings") { show(4, true); }
        else if (id === "apps-open") { capability("launchApp", "netcast"); }
        else if (id === "apps-info") { message("This prototype runs its own interface only. Modern streaming apps and their DRM compatibility have not been established."); }
        else if (id.indexOf("input-") === 0) { capability("switchInput", id.substring(6)); }
        else if (id === "media-usb") { capability("openUsb", "usb"); }
        else if (id === "media-network") { capability("browseNetwork", "dlna"); }
        else if (id === "setting-accent") { changeAppearance("accent"); }
        else if (id === "setting-contrast") { changeAppearance("contrast"); }
        else if (id === "setting-storage") { toggleStorage(); }
        else if (id === "setting-about") { message("OpenCast OS is in development. This browser launcher is not installed, does not replace startup, and has no native TV-control connection."); }
    }
    var i, j;
    for (i = 0; i < pages.length; i += 1) {
        (function (index) {
            element("tab-" + pages[index]).onclick = function () { if (!paused) { show(index, false); this.focus(); } };
        }(i));
        for (j = 0; j < controls[i].length; j += 1) {
            (function (id) { element(id).onclick = function () { activate(id); }; }(controls[i][j]));
        }
    }
    function keydown(event) {
        if (paused) { return; }
        event = event || window.event;
        if (!event) { return; }
        var code = event.keyCode || event.which, target = event.target || event.srcElement;
        var zone = "", index = -1, next, k;
        /* Native button Enter/Space activation is intentionally not synthesized. */
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
        next = OpenCastShellNavigation.move(zone, index, code, controls[current].length, 2, current, pages.length);
        if (!next) { return; }
        if (next.zone === "tabs") {
            show(next.index, false);
            element("tab-" + pages[next.index]).focus();
        } else {
            if (zone === "tabs" && current !== index) { show(index, false); }
            element(controls[current][next.index]).focus();
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
        text("clock", (hours < 10 ? "0" : "") + hours + ":" + (minutes < 10 ? "0" : "") + minutes);
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
    load(); appearance(); clock();
    element("tab-home").focus();
}());
