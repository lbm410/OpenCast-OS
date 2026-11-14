/* Disconnected native capability boundary. These results never claim execution. */
var OpenCastShellCapabilities = (function () {
    var reasons = {
        launchApp: "This TV app is not connected yet.",
        switchInput: "TV input control is not connected yet.",
        openUsb: "USB browsing is not connected yet.",
        browseNetwork: "Network media is not connected yet."
    };
    function query(name) {
        return { available: false, reason: typeof reasons[name] === "string" ? reasons[name] : "This feature is not available yet." };
    }
    function invoke(name, target) {
        var state = query(name);
        return { ok: false, available: state.available, message: state.reason };
    }
    return { query: query, invoke: invoke };
}());
if (typeof module !== "undefined" && module.exports) { module.exports = OpenCastShellCapabilities; }
