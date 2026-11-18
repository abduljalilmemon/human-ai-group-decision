// Deliberately shows no participant counts, seats, or progress: that would reveal how many humans
// are expected. The loop is one turning arc with a breathing core, nothing countable.
export default function Waiting() {
  return (
    <div className="py-4 text-center">
      <div className="relative mx-auto mb-8 h-28 w-28" aria-hidden>
        <span className="absolute inset-0 rounded-full bg-accent-soft" />
        <span className="orbit-ring absolute inset-0 animate-orbit rounded-full" />
        <span className="absolute inset-7 animate-breathe rounded-full bg-[radial-gradient(circle,oklch(49%_0.2_272/0.35),transparent_70%)]" />
        <span className="absolute top-1/2 left-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent" />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight text-balance">Waiting room</h1>
      <p className="mx-auto mt-2 max-w-[38ch] text-muted">
        You will be matched with other participants shortly. The session starts automatically.
      </p>
      <p className="mt-5 text-sm text-muted">Please keep this tab open.</p>
    </div>
  );
}
