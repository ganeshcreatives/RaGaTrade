import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDecipheriv} from 'node:crypto';
import {tokenExpiry,encodeToken,renewDhanWebToken} from '../dist/dhan-renew.js';
test('expired and malformed renewal expiries rejected',()=>{assert.throws(()=>tokenExpiry('invalid'));assert.throws(()=>tokenExpiry('2000-01-01T00:00:00'));});
test('IST token expiry is explicit',()=>{assert.equal(tokenExpiry('2099-01-01T12:00:00').toISOString(),'2099-01-01T06:30:00.000Z');});
test('tokens roundtrip through authenticated encryption',()=>{process.env.DHAN_TOKEN_ENCRYPTION_KEY='ab'.repeat(32);const value=encodeToken('test-only-token');const d=createDecipheriv('aes-256-gcm',Buffer.from(process.env.DHAN_TOKEN_ENCRYPTION_KEY,'hex'),Buffer.from(value.iv,'base64'));d.setAuthTag(Buffer.from(value.tag,'base64'));assert.equal(Buffer.concat([d.update(Buffer.from(value.encrypted,'base64')),d.final()]).toString(),'test-only-token');});
test('renewal failures and wrong-account results rejected',async()=>{const original=globalThis.fetch;try{globalThis.fetch=async()=>new Response('{}',{status:401});await assert.rejects(renewDhanWebToken('test','client'),/rejected/);globalThis.fetch=async()=>Response.json({accessToken:'test',dhanClientId:'wrong',expiryTime:'2099-01-01T12:00:00'});await assert.rejects(renewDhanWebToken('test','client'),/Invalid/);globalThis.fetch=async()=>Response.json({accessToken:'renewed',dhanClientId:'client',expiryTime:'2099-01-01T12:00:00'});assert.equal((await renewDhanWebToken('test','client')).token,'renewed');}finally{globalThis.fetch=original;}});
