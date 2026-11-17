type QueryablePool = {
  query: (sql: string, values?: unknown[]) => Promise<{ rows: any[]; rowCount?: number | null }>;
  connect: () => Promise<any>;
};

export type HistoryImportResult = { received: number; stored: number; rejected: number };

/** Fetch one supported NSE equity's licensed Dhan 1-minute history and persist validated bars. */
export async function importDhanHistory(
  pool: QueryablePool,
  input: { instrumentId: string; securityId: string; token: string; from: Date; to: Date },
): Promise<HistoryImportResult> {
  const { instrumentId, securityId, token, from, to } = input;
  if (!Number.isFinite(from.valueOf()) || !Number.isFinite(to.valueOf()) || to <= from || to.getTime() - from.getTime() > 90 * 86400000) {
    throw new Error("History range must be valid and no longer than 90 days");
  }
  const ist = (date: Date) => new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).format(date);
  const response = await fetch("https://api.dhan.co/v2/charts/intraday", {
    method: "POST",
    headers: { "Content-Type": "application/json", accept: "application/json", "access-token": token },
    body: JSON.stringify({ securityId, exchangeSegment: "NSE_EQ", instrument: "EQUITY", interval: "1", oi: false, fromDate: ist(from), toDate: ist(to) }),
    signal: AbortSignal.timeout(60000),
  });
  const payload: any = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(`Dhan history request failed (${response.status})`);
    (error as any).status = response.status;
    throw error;
  }
  const keys = ["timestamp", "open", "high", "low", "close", "volume"];
  const count = Array.isArray(payload.timestamp) ? payload.timestamp.length : -1;
  if (count < 0 || count > 120000 || keys.some(key => !Array.isArray(payload[key]) || payload[key].length !== count)) {
    throw new Error("Dhan returned an invalid or oversized candle response");
  }
  const rows: unknown[][] = [];
  let rejected = 0;
  for (let index = 0; index < count; index++) {
    const timestamp = Number(payload.timestamp[index]);
    const open = Number(payload.open[index]), high = Number(payload.high[index]);
    const low = Number(payload.low[index]), close = Number(payload.close[index]), volume = Number(payload.volume[index]);
    const eventTime = new Date(timestamp * 1000);
    if (!Number.isFinite(timestamp) || !Number.isFinite(eventTime.valueOf()) || eventTime < from || eventTime > to ||
        ![open, high, low, close].every(value => Number.isFinite(value) && value > 0) || !Number.isFinite(volume) || volume < 0 ||
        low > Math.min(open, close) || high < Math.max(open, close)) {
      rejected++;
      continue;
    }
    rows.push([instrumentId, eventTime.toISOString(), open, high, low, close, Math.trunc(volume), "DHAN_HISTORICAL"]);
  }
  const client = await pool.connect();
  let stored = 0;
  try {
    await client.query("BEGIN");
    for (let offset = 0; offset < rows.length; offset += 500) {
      const batch = rows.slice(offset, offset + 500), params: unknown[] = [];
      const values = batch.map(row => {
        const base = params.length;
        params.push(...row);
        return `(${Array.from({ length: 8 }, (_, column) => `$${base + column + 1}`).join(",")})`;
      });
      const result = await client.query(
        `INSERT INTO market_bars_1m(instrument_id,event_time,open,high,low,close,volume,source) VALUES ${values.join(",")} ` +
        "ON CONFLICT(instrument_id,event_time) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,volume=excluded.volume,source=excluded.source,ingested_at=now(),quality_status='VALID'",
        params,
      );
      stored += result.rowCount ?? 0;
    }
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
  return { received: count, stored, rejected };
}
