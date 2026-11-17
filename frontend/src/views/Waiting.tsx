// Deliberately shows no participant counts or progress: that would reveal how many humans are expected.
export default function Waiting() {
  return (
    <div className="text-center">
      <div className="relative mx-auto mb-6 flex h-12 w-12 items-center justify-center">
        <span className="absolute h-12 w-12 animate-ping rounded-full bg-indigo-200 motion-reduce:animate-none" />
        <span className="relative h-4 w-4 rounded-full bg-indigo-500" />
      </div>
      <h1 className="text-2xl font-semibold">Waiting room</h1>
      <p className="mt-2 text-slate-500">
        You will be matched with other participants shortly. The session starts automatically.
      </p>
      <p className="mt-4 text-sm text-slate-400">Please keep this tab open.</p>
    </div>
  );
}
