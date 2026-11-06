// Ballot Buddy: serves the app at ballotbuddy.appolis.app and keeps accounts.
// Sign-in is a six-digit code emailed through the Appolis suite mail door (POST /id/mail/send with this app's key),
// the same road Hermes uses. An account holds the voter's picks and district numbers, never a street address.
//
// KV (BALLOT_BUDDY):  otp:<email> {h, n} 10 min · rl:<kind>:<who> counters · acct:<email> {picks, ctx, created, updated}
//                     sess:<sha256(token)> <email> 90 days
const CODE_TTL = 600, SESSION_TTL = 90 * 86400, MAX_TRIES = 5;
import {resultsApi, refresh} from "./results.js";

const ORIGINS = ["https://bucfan56.github.io", "https://ballotbuddy.appolis.app", "https://ballotbuddy.app", "http://localhost:8010"];
const CTX_KEYS = ["st", "cd", "sd", "hd", "county", "city", "zip", "cc", "sb", "ward", "specials", "how"];

const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
const sha = async s => hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
const validEmail = e => { e = String(e || "").trim().toLowerCase(); return /^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,}$/.test(e) ? e : null; };

function cors(req) {
  const o = req.headers.get("origin");
  return o && ORIGINS.includes(o) ? {"access-control-allow-origin": o, "access-control-allow-headers": "content-type, authorization",
    "access-control-allow-methods": "GET, PUT, POST, DELETE, OPTIONS", "access-control-max-age": "86400", vary: "origin"} : {};
}
const J = (req, status, body) => new Response(JSON.stringify(body), {status, headers: {"content-type": "application/json", "cache-control": "no-store", ...cors(req)}});

async function hit(env, key, ttl) {     // a simple fixed-window counter
  const n = (+(await env.BALLOT_BUDDY.get(key)) || 0) + 1;
  await env.BALLOT_BUDDY.put(key, String(n), {expirationTtl: ttl});
  return n;
}

async function sendCode(env, to, code) {
  if (!env.APPOLIS_APP_KEY || !env.APPOLIS) throw new Error("NOT_CONNECTED");
  const text = `Your Ballot Buddy sign-in code is ${code}\n\nIt works for 10 minutes. If you didn't ask for it, you can ignore this email.`;
  const html = `<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:420px;margin:0 auto;padding:24px;color:#0f172a">
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 10px"><tr><td style="vertical-align:middle"><img src="https://ballotbuddy.appolis.app/buddy/icons/icon-192.png" width="48" height="48" alt="Ballot Buddy" style="display:block;border-radius:12px"></td><td style="vertical-align:middle;padding-left:12px;font-size:22px;font-weight:800;color:#1e3a8a">Ballot Buddy</td></tr></table><p style="margin:0 0 18px;color:#475569">Your sign-in code:</p>
    <div style="font-size:34px;font-weight:800;letter-spacing:8px;background:#eef2ff;border-radius:14px;padding:16px;text-align:center">${code}</div>
    <p style="color:#64748b;font-size:13px;margin-top:18px">It works for 10 minutes. If you didn't ask for it, you can ignore this email.</p></div>`;
  const r = await env.APPOLIS.fetch(new Request("https://appolis.app/id/mail/send", {method: "POST",
    headers: {"content-type": "application/json", "x-id-internal": env.APPOLIS_APP_KEY},
    body: JSON.stringify({to, subject: `${code} is your Ballot Buddy code`, text, html, sender_name: "Ballot Buddy", tag: "bb-code", app: "ballot-buddy"})}));
  if (!r.ok) throw new Error("mail door " + r.status + ": " + (await r.text()).slice(0, 200));
}

async function who(req, env) {
  const m = /^Bearer ([a-f0-9]{64})$/.exec(req.headers.get("authorization") || "");
  return m ? await env.BALLOT_BUDDY.get("sess:" + await sha(m[1])) : null;
}

function cleanPicks(p) {
  const out = {};
  if (p && typeof p === "object") for (const [k, v] of Object.entries(p).slice(0, 600))
    if (typeof v === "string" && k.length <= 80 && v.length <= 140) out[k] = v;
  return out;
}
function cleanCtx(c) {
  if (!c || typeof c !== "object") return null;
  const out = {};
  for (const k of CTX_KEYS) if (c[k] != null) out[k] = k === "specials" ? (Array.isArray(c[k]) ? c[k].slice(0, 20).map(x => String(x).slice(0, 80)) : null) : typeof c[k] === "number" ? c[k] : String(c[k]).slice(0, 60);
  return out.county ? out : null;
}

async function api(req, env, url) {
  const p = url.pathname, m = req.method, KV = env.BALLOT_BUDDY;
  if (m === "OPTIONS") return new Response(null, {status: 204, headers: cors(req)});
  const ip = req.headers.get("cf-connecting-ip") || "";

  if (p === "/api/otp/request" && m === "POST") {
    const b = await req.json().catch(() => ({})), email = validEmail(b.email);
    if (!email) return J(req, 400, {error: "That doesn't look like an email address."});
    if (await hit(env, "rl:req:" + email, 900) > 5 || await hit(env, "rl:ip:" + ip, 900) > 30)
      return J(req, 429, {error: "Too many codes asked for. Wait 15 minutes and try again."});
    const n = crypto.getRandomValues(new Uint32Array(1))[0] % 1000000, code = String(n).padStart(6, "0");
    try { await sendCode(env, email, code); }
    catch (e) {
      console.error("code email failed", e && e.message);
      return J(req, 503, {error: e.message === "NOT_CONNECTED" ? "Sign-in emails aren't switched on yet. Your picks are still saved on this phone." : "We couldn't send the email just now. Try again in a minute."});
    }
    await KV.put("otp:" + email, JSON.stringify({h: await sha(email + ":" + code), n: 0}), {expirationTtl: CODE_TTL});
    return J(req, 200, {ok: true});
  }

  if (p === "/api/otp/verify" && m === "POST") {
    const b = await req.json().catch(() => ({})), email = validEmail(b.email), code = String(b.code || "").replace(/\D/g, "");
    const WRONG = {error: "That code is wrong or has expired."};
    if (!email || code.length !== 6) return J(req, 401, WRONG);
    const rec = JSON.parse(await KV.get("otp:" + email) || "null");
    if (!rec) return J(req, 401, WRONG);
    if (rec.h !== await sha(email + ":" + code)) {
      if (++rec.n >= MAX_TRIES) await KV.delete("otp:" + email);
      else await KV.put("otp:" + email, JSON.stringify(rec), {expirationTtl: CODE_TTL});
      return J(req, 401, WRONG);
    }
    await KV.delete("otp:" + email);
    let acct = JSON.parse(await KV.get("acct:" + email) || "null"), created = false;
    if (!acct) { acct = {picks: {}, ctx: null, created: new Date().toISOString()}; created = true; await KV.put("acct:" + email, JSON.stringify(acct)); }
    const token = hex(crypto.getRandomValues(new Uint8Array(32)));
    await KV.put("sess:" + await sha(token), email, {expirationTtl: SESSION_TTL});
    return J(req, 200, {ok: true, token, email, created});
  }

  const email = await who(req, env);
  if (p === "/api/me") {
    if (!email) return J(req, 401, {error: "Signed out."});
    const acct = JSON.parse(await KV.get("acct:" + email) || "null") || {picks: {}, ctx: null};
    if (m === "GET") return J(req, 200, {email, picks: acct.picks || {}, ctx: acct.ctx || null, updated: acct.updated || null});
    if (m === "PUT") {
      const b = await req.json().catch(() => ({}));
      if ("picks" in b) acct.picks = cleanPicks(b.picks);
      if ("ctx" in b) acct.ctx = cleanCtx(b.ctx);
      acct.updated = new Date().toISOString();
      await KV.put("acct:" + email, JSON.stringify(acct));
      return J(req, 200, {ok: true, updated: acct.updated});
    }
    if (m === "DELETE") { await KV.delete("acct:" + email); await KV.delete("sess:" + await sha(/Bearer (\S+)/.exec(req.headers.get("authorization"))[1])); return J(req, 200, {ok: true, deleted: true}); }
  }
  if (p === "/api/logout" && m === "POST") {
    const t = /^Bearer ([a-f0-9]{64})$/.exec(req.headers.get("authorization") || "");
    if (t) await KV.delete("sess:" + await sha(t[1]));
    return J(req, 200, {ok: true});
  }
  if (p === "/api/health") return J(req, 200, {ok: true, mail: !!env.APPOLIS_APP_KEY});
  return J(req, 404, {error: "not found"});
}

export default {
  // Every 5 minutes: pull the five main states, three of the others, and the national view. Keeps the last good copy if a source fails.
  // Awaited, not waitUntil: background work can be cut off, and a run that dies before its last write saves nothing.
  async scheduled(event, env, ctx) { await refresh(env, fetch); },
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname.startsWith("/api/results/") && req.method === "GET") {
      try {
        const res = await resultsApi(env, fetch, url.pathname, ctx);
        const out = new Response(res.body, res);
        out.headers.set("access-control-allow-origin", "*");      // public election numbers
        return out;
      } catch (e) { console.error(e); return J(req, 500, {error: "Something went wrong on our side."}); }
    }
    if (url.pathname.startsWith("/api/")) {
      try { return await api(req, env, url); }
      catch (e) { console.error(e); return J(req, 500, {error: "Something went wrong on our side."}); }
    }
    if (url.pathname === "/") return env.ASSETS.fetch(new Request(new URL("/ballot.html", url), req));
    return env.ASSETS.fetch(req);
  },
};
