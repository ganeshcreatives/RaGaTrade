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
export function expiryFromAccessToken(token:string):Date {
 const part=token.split('.')[1];
 if(!part)throw new Error('Dhan returned an invalid access token');
 let claims:any;
 try{claims=JSON.parse(Buffer.from(part,'base64url').toString('utf8'));}catch{throw new Error('Dhan returned an invalid access token');}
 if(typeof claims.exp!=='number')throw new Error('Dhan access token does not include an expiry');
 return tokenExpiry(new Date(claims.exp*1000).toISOString());
}
export async function verifyDhanWebToken(token:string,clientId:string){
 const response=await fetch('https://api.dhan.co/v2/profile',{headers:{'access-token':token,accept:'application/json'},signal:AbortSignal.timeout(15000)});
 const profile:any=await response.json().catch(()=>({}));
 if(!response.ok)throw new DhanTokenRejected(String(profile.errorCode??response.status).slice(0,32),String(profile.errorMessage??'Dhan rejected this access token. Generate a fresh token from Dhan Web and try again.').slice(0,180));
 if(String(profile.dhanClientId??profile.clientId??'')!==clientId)throw new DhanTokenRejected('CLIENT_MISMATCH','The Dhan token belongs to a different client account.');
 return {expiry:expiryFromAccessToken(token),profile};
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
 if(typeof data.accessToken!=='string'||!data.accessToken)throw new Error('Dhan returned an invalid renewal response');
 if(data.dhanClientId!=null&&String(data.dhanClientId)!==clientId)throw new DhanTokenRejected('CLIENT_MISMATCH','Dhan renewed a token for a different client account.');
 const verified=await verifyDhanWebToken(data.accessToken,clientId);
 const expiry=data.expiryTime?tokenExpiry(data.expiryTime):verified.expiry;
 return {token:data.accessToken,expiry};
}
export async function renewConnections(){
 const pool=new Pool({connectionString:process.env.DATABASE_URL});let failed=0,renewed=0;
 try{
 const users=await pool.query("SELECT user_id FROM dhan_connections WHERE token_origin='WEB' AND expires_at<now()+interval '12 hours' AND expires_at>now() AND (renewal_error IS NULL OR renewal_error NOT LIKE 'Dhan rejected%')");
 for(const user of users.rows){
  const db=await pool.connect();try{
   await db.query('BEGIN');
   const locked=await db.query("SELECT * FROM dhan_connections WHERE user_id=$1 AND token_origin='WEB' AND expires_at<now()+interval '12 hours' AND expires_at>now() AND (renewal_error IS NULL OR renewal_error NOT LIKE 'Dhan rejected%') FOR UPDATE SKIP LOCKED",[user.user_id]);
   if(!locked.rowCount){await db.query('COMMIT');continue;}
   const row=locked.rows[0],cipher=createDecipheriv('aes-256-gcm',Buffer.from(process.env.DHAN_TOKEN_ENCRYPTION_KEY!,'hex'),Buffer.from(row.token_iv,'base64'));
   cipher.setAuthTag(Buffer.from(row.token_tag,'base64'));
   const token=Buffer.concat([cipher.update(Buffer.from(row.encrypted_access_token,'base64')),cipher.final()]).toString('utf8');
   const result=await renewDhanWebToken(token,row.client_id),encoded=encodeToken(result.token);
   await db.query('UPDATE dhan_connections SET encrypted_access_token=$2,token_iv=$3,token_tag=$4,expires_at=$5,last_renewed_at=now(),renewal_error=NULL WHERE user_id=$1',[row.user_id,encoded.encrypted,encoded.iv,encoded.tag,result.expiry]);
   await db.query('COMMIT');renewed++;
  }catch(error){
   await db.query('ROLLBACK');failed++;
   const rejected=error instanceof DhanTokenRejected&&error.code==='DH-906';
   const detail=error instanceof DhanTokenRejected?`${error.code}: ${error.message}`:error instanceof Error?error.message:'Unknown renewal error';
   const safeDetail=detail.replace(/\s+/g,' ').slice(0,220);
   const statusMessage=rejected?`Dhan rejected the saved access token (${safeDetail}). Generate a fresh Dhan Web token and save it here.`:`Automatic renewal failed: ${safeDetail}`;
   console.warn(`Dhan token renewal failed for ${String(user.user_id).slice(0,8)}: ${safeDetail}`);
   await pool.query("UPDATE dhan_connections SET renewal_error=$2 WHERE user_id=$1",[user.user_id,statusMessage]);
  }finally{db.release();}
 }
 console.log(JSON.stringify({renewed,failed}));
 if(failed)process.exitCode=1;
 }finally{await pool.end();}
}
