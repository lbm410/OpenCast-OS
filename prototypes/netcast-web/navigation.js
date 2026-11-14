/* Conservative JavaScript: deliberately avoids modern syntax and dependencies. */
var OpenCastNavigation = (function () {
    function move(index, code, count) {
        if (count < 1) { return 0; }
        if (code === 37 || code === 38) { return Math.max(0, index - 1); }
        if (code === 39 || code === 40) { return Math.min(count - 1, index + 1); }
        return index;
    }
    return { move: move };
}());
if (typeof module !== "undefined" && module.exports) { module.exports = OpenCastNavigation; }
