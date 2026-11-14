/* A single horizontal dock and a compact section bar. No system-key mapping. */
var OpenCastShellNavigation = (function () {
    function move(zone, index, code, count, pageIndex, tabCount) {
        if ((code !== 37 && code !== 38 && code !== 39 && code !== 40) || count < 1) { return null; }
        if (zone === "tabs") {
            if (code === 40) { return { zone: "content", index: 0 }; }
            if (code === 38) { return { zone: "tabs", index: index }; }
            return { zone: "tabs", index: Math.max(0, Math.min(tabCount - 1, index + (code === 37 ? -1 : 1))) };
        }
        if (zone !== "content") { return null; }
        if (code === 38) { return { zone: "tabs", index: pageIndex }; }
        if (code === 40) { return { zone: "content", index: index }; }
        return { zone: "content", index: Math.max(0, Math.min(count - 1, index + (code === 37 ? -1 : 1))) };
    }
    return { move: move };
}());
if (typeof module !== "undefined" && module.exports) { module.exports = OpenCastShellNavigation; }
