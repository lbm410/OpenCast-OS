/* Pure bounded navigation. System keys, including Home/Back, are not mapped. */
var OpenCastShellNavigation = (function () {
    function move(zone, index, code, count, columns, pageIndex, tabCount) {
        if ((code !== 37 && code !== 38 && code !== 39 && code !== 40) || count < 1) { return null; }
        if (zone === "tabs") {
            if (code === 40) { return { zone: "content", index: 0 }; }
            if (code === 38) { return { zone: "tabs", index: index }; }
            return { zone: "tabs", index: Math.max(0, Math.min(tabCount - 1, index + (code === 37 ? -1 : 1))) };
        }
        if (zone !== "content") { return null; }
        if (code === 38 && index < columns) { return { zone: "tabs", index: pageIndex }; }
        var next = index;
        if (code === 37 && index % columns > 0) { next = index - 1; }
        if (code === 39 && index % columns < columns - 1 && index + 1 < count) { next = index + 1; }
        if (code === 38) { next = Math.max(0, index - columns); }
        if (code === 40 && index + columns < count) { next = index + columns; }
        return { zone: "content", index: next };
    }
    return { move: move };
}());
if (typeof module !== "undefined" && module.exports) { module.exports = OpenCastShellNavigation; }
