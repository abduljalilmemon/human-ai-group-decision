// Deliberately shows no participant counts or progress: that would reveal how many humans are expected.
export default function Waiting() {
  return (
    <div className="text-center">
      <div className="relative mx-auto mb-7 flex h-16 w-16 items-center justify-center" aria-hidden>
        <span className="absolute inset-0 animate-breathe rounded-full bg-accent" />
        <span className="relative h-4 w-4 rounded-full bg-accent" />
      </div>
      <h1 className="text-2xl font-semibold text-balance">Waiting room</h1>
      <p className="mx-auto mt-2 max-w-[38ch] text-muted">
        You will be matched with other participants shortly. The session starts automatically.
      </p>
      <p className="mt-5 text-sm text-muted">Please keep this tab open.</p>
    </div>
  );
}
