export const ScanlineOverlay = () => {
  // Can be used to inject more complex CRT effects like flicker if needed,
  // otherwise it just mounts the CSS class.
  return <div className="scanline-effect pointer-events-none fixed inset-0 z-50"></div>;
};
