// Operator-only history import, run inside the API container. No secrets emitted.
const {Pool}=require('pg');
const {createDecipheriv}=require('node:crypto');
const pool=new Pool({connectionString:process.env.DATABASE_URL});
const ist=d=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(d);
(async()=>{
 const con=await pool.query('SELECT * FROM dhan_connections WHERE expires_at>now() ORDER BY connected_at DESC LIMIT 1');
 if(!con.rowCount)throw Error('Connect Dhan first');
 const row=con.rows[0], cipher=createDecipheriv('aes-256-gcm',Buffer.from(process.env.DHAN_TOKEN_ENCRYPTION_KEY,'hex'),Buffer.from(row.token_iv,'base64'));
 cipher.setAuthTag(Buffer.from(row.token_tag,'base64'));
 const token=Buffer.concat([cipher.update(Buffer.from(row.encrypted_access_token,'base64')),cipher.final()]).toString('utf8');
 const instruments=await pool.query('SELECT d.instrument_id,d.security_id,i.symbol FROM dhan_instruments d JOIN instruments i ON i.id=d.instrument_id ORDER BY i.symbol');
 const to=new Date(),from=new Date(to.getTime()-30*86400000);
 for(const instrument of instruments.rows){
  const response=await fetch('https://api.dhan.co/v2/charts/intraday',{method:'POST',headers:{'Content-Type':'application/json','access-token':token},body:JSON.stringify({securityId:instrument.security_id,exchangeSegment:'NSE_EQ',instrument:'EQUITY',interval:'1',oi:false,fromDate:ist(from),toDate:ist(to)}),signal:AbortSignal.timeout(60000)});
  if(!response.ok){console.log(JSON.stringify({symbol:instrument.symbol,status:response.status,imported:0}));continue;}
  const data=await response.json(); const arrays=['timestamp','open','high','low','close','volume'];
  if(!arrays.every(k=>Array.isArray(data[k])&&data[k].length===data.timestamp?.length))throw Error('Invalid provider arrays');
  const records=[];let rejected=0;
  for(let i=0;i<data.timestamp.length;i++){
   const [ts,o,h,l,c,v]=arrays.map(k=>Number(data[k][i]));
   if(![ts,o,h,l,c,v].every(Number.isFinite)||Math.min(o,h,l,c)<=0||v<0||l>Math.min(o,c)||h<Math.max(o,c)||ts*1000<from.getTime()||ts*1000>to.getTime()){rejected++;continue;}
   records.push([instrument.instrument_id,new Date(ts*1000).toISOString(),o,h,l,c,Math.trunc(v),'DHAN_HISTORICAL']);
  }
  const db=await pool.connect();try{
   await db.query('BEGIN');
   for(let offset=0;offset<records.length;offset+=500){
    const batch=records.slice(offset,offset+500),params=batch.flat();
    const values=batch.map((_,i)=>'('+Array.from({length:8},(_,j)=>'$'+(i*8+j+1)).join(',')+')').join(',');
    await db.query('INSERT INTO market_bars_1m(instrument_id,event_time,open,high,low,close,volume,source) VALUES '+values+" ON CONFLICT(instrument_id,event_time) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,volume=excluded.volume,source=excluded.source,quality_status='VALID',ingested_at=now()",params);
   }
   await db.query('COMMIT');
  }catch(error){await db.query('ROLLBACK');throw error;}finally{db.release();}
  console.log(JSON.stringify({symbol:instrument.symbol,imported:records.length,rejected,source:'DHAN_HISTORICAL'}));
  await new Promise(resolve=>setTimeout(resolve,1100));
 }
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>pool.end());
