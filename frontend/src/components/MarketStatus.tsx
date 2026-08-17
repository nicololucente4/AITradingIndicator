type Props = {
  online: boolean;
};

export default function MarketStatus({
  online,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <div className="text-sm text-slate-400">
        Backend Status
      </div>

      <div
        className={
          online
            ? "mt-2 text-lg font-bold text-green-400"
            : "mt-2 text-lg font-bold text-red-400"
        }
      >
        {online ? "ONLINE" : "OFFLINE"}
      </div>
    </div>
  );
}