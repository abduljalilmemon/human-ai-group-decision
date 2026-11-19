/** The shared background on every screen: three slow blurred blobs (transform-only drift) plus film grain. */
export default function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="blob blob-a" />
      <div className="blob blob-b" />
      <div className="blob blob-c" />
      <div className="grain" />
    </div>
  );
}
