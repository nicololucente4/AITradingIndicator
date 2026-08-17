type HeaderProps = {
  symbol: string;
  timeframe: string;
};

export default function Header({
  symbol,
  timeframe,
}: HeaderProps) {
  return (
    <div className="border-b border-slate-800 bg-slate-950">
      <div className="flex items-center justify-between px-6 py-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            AI Trading Indicator
          </h1>

          <p className="mt-1 text-sm text-slate-400">
            {symbol} · {timeframe}
          </p>
        </div>

        <div className="rounded-lg border border-yellow-600 bg-yellow-600/10 px-4 py-2 text-sm font-bold text-yellow-400">
          PAPER ONLY
        </div>
      </div>
    </div>
  );
}