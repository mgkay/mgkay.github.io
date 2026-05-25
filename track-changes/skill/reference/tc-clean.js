// tc-clean.js — track-changes §4 render-time mark hiding toggle (C12).
//
// When the document URL carries the query parameter `?clean=1` (or a bare
// `?clean`), add the `no-marks` class to <body>. Paired with tc-clean.css,
// this hides track-changes highlights and their <sup>N</sup> reference
// numbers at render time, leaving the source file untouched.
//
// Usage: include tc-clean.css and this script in the rendered HTML, then
// append `?clean=1` to the document URL when sharing a lecture mid-review.
// Parallel to how a Quarto project might use `?present=1` for projection
// mode. No source mutation — toggling is purely a viewing concern.
//
// Defensive: guards against environments without URLSearchParams or document
// (e.g. SSR / non-browser) so including the file never throws.
(function () {
  try {
    if (typeof document === 'undefined' || typeof location === 'undefined') {
      return;
    }
    var params;
    if (typeof URLSearchParams !== 'undefined') {
      params = new URLSearchParams(location.search);
    }
    var clean = false;
    if (params && params.has('clean')) {
      clean = true;
    } else if (location.search && /[?&]clean(=|&|$)/.test(location.search)) {
      // Fallback for very old engines lacking URLSearchParams.
      clean = true;
    }
    if (!clean) {
      return;
    }
    var apply = function () {
      if (document.body) {
        document.body.classList.add('no-marks');
      }
    };
    if (document.body) {
      apply();
    } else if (document.addEventListener) {
      document.addEventListener('DOMContentLoaded', apply);
    }
  } catch (e) {
    // Never let a render-time toggle break the page.
  }
})();
