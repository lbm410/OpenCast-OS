/* A capability boundary, deliberately disconnected from native TV controls. */
var OpenCastShellCapabilities = (function () {
    var reasons = {
        launchApp: "Application launch is unavailable: no verified NetCast adapter is connected.",
        switchInput: "Input switching is unavailable: no verified TV-control adapter is connected.",
        openUsb: "USB browsing is unavailable: this page has no native file-access adapter.",
        browseNetwork: "Network media browsing is unavailable: no DLNA browser is connected."
    };
    function query(name) {
        return { available: false, reason: typeof reasons[name] === "string" ? reasons[name] : "This TV capability is not implemented." };
    }
    function invoke(name, target) {
        var state = query(name);
        return { ok: false, available: state.available, message: state.reason };
    }
    return { query: query, invoke: invoke };
}());
if (typeof module !== "undefined" && module.exports) { module.exports = OpenCastShellCapabilities; }
