//#region lib/index.js
/**
 * Host half of @juzi/dsh-model-version-badge.
 *
 * Pure browser-side decoration plugin: this half exists only so the Loader can
 * see the package and request the browser bundle declared through
 * package.json `dsh.client`. It intentionally declares NO host-side `inject`,
 * because the services used by the browser half (`slots`) live in the Browser
 * assembly only; declaring them here would park the fiber as inactive and the
 * client bundle would never be requested (same constraint as the upstream
 * 1017 label plugin).
 */

/** Host plugin body — no host-side behaviour for this surface plugin. */
function apply() {}
//#endregion

export { apply };
