/*
 * canonical.js
 *
 * Rebuilds the exact bytes that verify.py hashes:
 *   json.dumps(payload, sort_keys=True, separators=(",", ":"))
 * Every number in a ChainProof payload is a Python float (verify.py calls
 * float() on each), so numbers are written the way Python's repr writes
 * floats: 50 becomes "50.0", 1e-05 keeps a two-digit exponent, and so on.
 * Used by the tamper lab, where a visitor edits a decision and the hash is
 * recomputed in the browser.
 */
(function (global) {
  function pyFloat(x) {
    if (Number.isNaN(x)) return "NaN";
    if (x === Infinity) return "Infinity";
    if (x === -Infinity) return "-Infinity";
    if (Object.is(x, -0)) return "-0.0";
    const abs = Math.abs(x);
    if (abs !== 0 && (abs < 1e-4 || abs >= 1e16)) {
      // Python: shortest digits, exponent with sign and at least two digits.
      const [mant, exp] = x.toExponential().split("e");
      const sign = exp[0] === "-" ? "-" : "+";
      const digits = exp.replace(/^[+-]/, "").padStart(2, "0");
      return `${mant}e${sign}${digits}`;
    }
    const s = String(x);
    return Number.isInteger(x) ? `${s}.0` : s;
  }

  function pyString(s) {
    // json.dumps escapes like JSON.stringify, plus ensure_ascii=True.
    return JSON.stringify(s).replace(/[\u007f-\uffff]/g, (c) =>
      "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0")
    );
  }

  function pyJson(value) {
    if (value === null || value === undefined) return "null";
    if (typeof value === "number") return pyFloat(value);
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "string") return pyString(value);
    if (Array.isArray(value)) return "[" + value.map(pyJson).join(",") + "]";
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => pyString(k) + ":" + pyJson(value[k])).join(",") + "}";
  }

  global.ChainProofCanonical = { pyJson, pyFloat };
})(typeof window !== "undefined" ? window : globalThis);
