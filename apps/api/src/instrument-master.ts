import { Readable } from 'node:stream';
import { parse } from 'csv-parse';
import type { Pool } from 'pg';

// Public instrument reference data only; no broker token is used here.
export async function syncNseMaster(pool: Pool) {
  const response = await fetch('https://images.dhan.co/api-data/api-scrip-master.csv', {signal: AbortSignal.timeout(90000)});
  if (!response.ok || !response.body) throw new Error('Dhan instrument master unavailable');
  const existing = await pool.query('SELECT id,symbol,sector FROM instruments WHERE exchange=$1', ['NSE']);
  const bySymbol = new Map(existing.rows.map(row => [row.symbol, row]));
  const rows: any[] = [];
  const seen = new Set<string>();
  const parser = Readable.fromWeb(response.body as any).pipe(parse({columns:true,bom:true,skip_empty_lines:true}));
  for await (const row of parser) {
    if (row.SEM_EXM_EXCH_ID !== 'NSE' || row.SEM_SEGMENT !== 'E' || row.SEM_INSTRUMENT_NAME !== 'EQUITY' || row.SEM_SERIES !== 'EQ') continue;
    const securityId = String(row.SEM_SMST_SECURITY_ID), symbol = String(row.SEM_TRADING_SYMBOL);
    if (!/^\d+$/.test(securityId) || !/^[A-Z][A-Z0-9&.-]{0,24}$/.test(symbol) || seen.has(symbol)) continue;
    seen.add(symbol);
    const old = bySymbol.get(symbol);
    rows.push({id:old?.id ?? `nse-${securityId}`,symbol,name:row.SEM_CUSTOM_SYMBOL || symbol,sector:old?.sector || 'Unclassified',security_id:securityId});
  }
  if (rows.length < 100) throw new Error('Incomplete Dhan master; keeping last known catalogue');
  const db = await pool.connect();
  try {
    await db.query('BEGIN');
    await db.query("UPDATE instruments SET active=false WHERE exchange='NSE'");
    for (let start=0; start<rows.length; start+=250) {
      const data = JSON.stringify(rows.slice(start,start+250));
      await db.query("INSERT INTO instruments(id,symbol,name,exchange,sector,active) SELECT id,symbol,name,'NSE',sector,true FROM jsonb_to_recordset($1::jsonb) AS x(id text,symbol text,name text,sector text) ON CONFLICT(id) DO UPDATE SET symbol=excluded.symbol,name=excluded.name,sector=excluded.sector,active=true,updated_at=now()",[data]);
      await db.query("INSERT INTO dhan_instruments(instrument_id,security_id,exchange_segment) SELECT id,security_id,'NSE_EQ' FROM jsonb_to_recordset($1::jsonb) AS x(id text,security_id text) ON CONFLICT(instrument_id) DO UPDATE SET security_id=excluded.security_id,synced_at=now()",[data]);
    }
    await db.query('COMMIT');
  } catch (error) { await db.query('ROLLBACK'); throw error; } finally { db.release(); }
  return rows.length;
}
