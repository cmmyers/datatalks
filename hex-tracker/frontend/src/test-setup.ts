import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement scrollTo; the router's scrollRestoration calls it
// on every navigation, which would otherwise spam "not implemented" noise.
window.scrollTo = () => {};
