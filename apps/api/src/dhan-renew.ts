import pg from 'pg';
import {createCipheriv,createDecipheriv,randomBytes} from 'node:crypto';
const {Pool}=pg;
export class DhanTokenRejected extends Error {
 readonly code: string;
 constructor(code:string,message:string){super(message);this.name='DhanTokenRejected';this.code=code;}
}
export function tokenExpiry(value: unknown): Date {
 const text=String(value??'');
 const date=new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(text)?text:`${text}+05:30`);
 if(!Number.isFinite(date.getTime())||date.getTime()<=Date.now())throw new Error('Dhan did not provide a valid token expiry');
 return date;
}
export function encodeToken(token:string){
 const key=process.env.DHAN_TOKEN_ENCRYPTION_KEY??'';
 if(!/^[a-f0-9]{64}$/i.test(key))throw new Error('Token encryption not configured');
 const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',Buffer.from(key,'hex'),iv);
 return {encrypted:Buffer.concat([cipher.update(token,'utf8'),cipher.final()]).toString('base64'),iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64')};
}
export async function renewDhanWebToken(token:string,clientId:string){
 const response=await fetch('https://api.dhan.co/v2/RenewToken',{method:'GET',headers:{'access-token':token,dhanClientId:clientId,accept:'application/json'},signal:AbortSignal.timeout(15000)});
 const data:any=await response.json().catch(()=>({}));
 if(!response.ok)throw new DhanTokenRejected(String(data.errorCode??response.status).slice(0,32),String(data.errorMessage??'Dhan rejected this token. Generate a fresh access token from Dhan Web and try again.').slice(0,180));
 if(typeof data.accessToken!=='string'||!data.accessToken||String(data.dhanClientId)!==clientId)throw new Error('Invalid Dhan renewal response');
 return {token:data.accessToken,expiry:tokenExpiry(data.expiryTime)};
}
export async function renewConnections(){
 const pool=new Pool({connectionString:process.env.DATABASE_URL});let failed=0,renewed=0;
 try{
 const users=await pool.query("SELECT user_id FROM dhan_connections WHERE token_origin='WEB' AND expires_at<now()+interval '12 hours' AND expires_at>now()");
 for(const user of users.rows){
  const db=await pool.connect();try{
   await db.query('BEGIN');
   const locked=await db.query("SELECT * FROM dhan_connections WHERE user_id=$1 AND token_origin='WEB' AND expires_at<now()+interval '12 hours' AND expires_at>now() FOR UPDATE SKIP LOCKED",[user.user_id]);
   if(!locked.rowCount){await db.query('COMMIT');continue;}
   const row=locked.rows[0],cipher=createDecipheriv('aes-256-gcm',Buffer.from(process.env.DHAN_TOKEN_ENCRYPTION_KEY!,'hex'),Buffer.from(row.token_iv,'base64'));
   cipher.setAuthTag(Buffer.from(row.token_tag,'base64'));
   const token=Buffer.concat([cipher.update(Buffer.from(row.encrypted_access_token,'base64')),cipher.final()]).toString('utf8');
   const result=await renewDhanWebToken(token,row.client_id),encoded=encodeToken(result.token);
   await db.query('UPDATE dhan_connections SET encrypted_access_token=$2,token_iv=$3,token_tag=$4,expires_at=$5,last_renewed_at=now(),renewal_error=NULL WHERE user_id=$1',[row.user_id,encoded.encrypted,encoded.iv,encoded.tag,result.expiry]);
   await db.query('COMMIT');renewed++;
  }catch{await db.query('ROLLBACK');failed++;await pool.query("UPDATE dhan_connections SET renewal_error='Automatic renewal failed; verify or reconnect Dhan' WHERE user_id=$1",[user.user_id]);}finally{db.release();}
 }
 console.log(JSON.stringify({renewed,failed}));
 if(failed)process.exitCode=1;
 }finally{await pool.end();}
}
