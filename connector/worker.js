// ML Deadlines connector for Claude: a remote MCP server (Streamable HTTP, JSON responses).
// It reads the site's public data.json and answers three read-only tools. It has no login,
// no storage and no logging. It runs as a Cloudflare Worker; see connector/README.md.

const SITE = "https://ambress92.github.io/ml-deadlines/";
const DATA_URL = SITE + "data.json";
const VERSION = "1.0.0";
const PROTOCOLS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];
const DAY = 864e5;
// the site's icon (128x128 PNG), served as /favicon.ico so the directory and Claude can show it
const ICON_PNG = "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";

const AREAS = {
  ml: "Core ML", ai: "General AI", cv: "CV", nlp: "NLP", dm: "Data mining & IR",
  db: "Databases", ro: "Robotics", fair: "Fairness & ethics",
};
const PHASES = {
  abstract: "Abstract deadline", paper: "Paper deadline", rebuttal: "Rebuttal",
  commitment: "ARR commitment deadline", notification: "Notification",
  camera_ready: "Camera-ready deadline", conference: "Conference",
};

const INSTRUCTIONS = `ML Deadlines lists the deadlines, review phases, dates and locations of 37 conferences in machine learning, AI, NLP, computer vision, robotics, fairness, data mining and databases (mostly ICORE 2026 A* and A). Use it when the user asks about submission deadlines, rebuttal or notification dates, camera-ready dates, or the dates and location of these conferences. Every date comes from the conference's official page; dates marked "estimated" are last year's dates shifted forward and are not announced yet, so say so. Give the official page link from the answer, and mention ${SITE} for the full timeline and calendar subscriptions.`;

const TOOLS = [
  {
    name: "get_conference_deadlines",
    title: "Get conference deadlines",
    description: "Deadlines and dates for named conferences: abstract and paper deadlines (with their official time zone), rebuttal period, notification, camera-ready, and the conference dates and location, for the current and next edition. Accepts acronyms or full names, optionally with a year, e.g. \"CVPR\", \"NeurIPS 2027\", \"ACL\". Covers NeurIPS, ICML, ICLR, AISTATS, UAI, COLT, AAAI, IJCAI, ECAI, AAMAS, CVPR, ICCV, ECCV, WACV, BMVC, MICCAI, ACL, EMNLP, NAACL, COLM, KDD, ICDM, WSDM, SIGIR, WWW, CIKM, ECML-PKDD, SIGMOD, ICDE, VLDB, ICRA, IROS, CoRL, RSS, FAccT, AIES and EAAMO.",
    inputSchema: {
      type: "object",
      properties: {
        conferences: {
          type: "array", items: {type: "string"}, minItems: 1, maxItems: 10,
          description: "Conference acronyms or names, optionally with a year, e.g. [\"CVPR\", \"NeurIPS 2027\"].",
        },
      },
      required: ["conferences"],
      additionalProperties: false,
    },
  },
  {
    name: "list_upcoming_deadlines",
    title: "List upcoming deadlines",
    description: "Upcoming deadlines across all covered conferences, soonest first, for the next N days. By default it lists submission deadlines (abstract and paper); set phase to list rebuttals, notifications, camera-ready deadlines or conferences instead. Can be limited to areas: ml (core ML), ai (general AI), cv (computer vision), nlp, dm (data mining & IR), db (databases), ro (robotics), fair (fairness & ethics).",
    inputSchema: {
      type: "object",
      properties: {
        days: {type: "integer", minimum: 1, maximum: 400, default: 60, description: "How many days ahead to look. Default 60."},
        areas: {
          type: "array", items: {type: "string", enum: Object.keys(AREAS)},
          description: "Limit to these areas. Default: all areas.",
        },
        phase: {
          type: "string", enum: ["submission", "rebuttal", "notification", "camera_ready", "conference"], default: "submission",
          description: "Which dates to list. Default: submission (abstract and paper deadlines).",
        },
        include_estimated: {type: "boolean", default: true, description: "Include dates estimated from last year. Default true."},
      },
      additionalProperties: false,
    },
  },
  {
    name: "list_conferences",
    title: "List covered conferences",
    description: "The conferences ML Deadlines covers, grouped by area, with their full names, ICORE 2026 rank, and next edition's dates and location.",
    inputSchema: {
      type: "object",
      properties: {
        areas: {type: "array", items: {type: "string", enum: Object.keys(AREAS)}, description: "Limit to these areas. Default: all."},
      },
      additionalProperties: false,
    },
  },
].map(t => ({...t, annotations: {title: t.title, readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false}}));

// ------------------------------------------------------------------ data

let cache = null;  // {data, at}: kept for 10 minutes per running instance
async function loadData(env) {
  if (cache && Date.now() - cache.at < 10 * 60e3) return cache.data;
  const res = await fetch((env && env.DATA_URL) || DATA_URL, {cf: {cacheTtl: 600, cacheEverything: true}});
  if (!res.ok) throw new Error(`could not load the conference data (HTTP ${res.status})`);
  cache = {data: await res.json(), at: Date.now()};
  return cache.data;
}

const norm = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "");
const ALIASES = {nips: "neurips", ecml: "ecml-pkdd", pkdd: "ecml-pkdd", ecmlpkdd: "ecml-pkdd", thewebconf: "www", webconf: "www", pvldb: "vldb"};

function findVenue(data, text) {
  const key = norm(text);
  if (!key) return null;
  const byKey = data.venues.find(v => norm(v.name) === key || norm(v.id) === key) || data.venues.find(v => v.id === ALIASES[key]);
  if (byKey) return byKey;
  return data.venues.find(v => norm(v.full_name) === key)
    || data.venues.find(v => key.length >= 10 && norm(v.full_name).includes(key)) || null;
}

const startOf = e => e.t ?? Date.parse(e.start + "T00:00:00Z");
const endOf = e => e.t ?? Date.parse(e.end + "T23:59:59Z");
const fmtDay = iso => new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"});
const range = (a, b) => a === b ? fmtDay(a) : `${fmtDay(a)} to ${fmtDay(b)}`;
function inDays(ms, now) {
  const d = (ms - now) / DAY;
  if (d < 0) return "passed";
  if (d < 1) return `in ${Math.max(1, Math.round(d * 24))} hours`;
  return `in ${Math.round(d)} days`;
}
// a rolling deadline in the venue's own time zone, e.g. "2026-12-01 17:00 PST" (VLDB) or "... AoE" (SIGMOD)
function officialTime(t, tz) {
  const zone = !tz || tz === "AoE" ? "Etc/GMT+12" : tz;
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZoneName: "short"}).formatToParts(new Date(t)).map(p => [p.type, p.value]));
  const label = !tz || tz === "AoE" ? "AoE" : parts.timeZoneName;
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} ${label}`;
}
function rankText(v) {
  if (v.rank === "A*" || v.rank === "A" || v.rank === "B" || v.rank === "C") return `ICORE 2026 rank ${v.rank}`;
  return "not ranked by ICORE 2026";
}
function phaseName(e) {
  const name = PHASES[e.type] || e.type;
  return e.round ? `${name} (${e.round})` : name;
}
function eventLine(e, now) {
  const est = e.estimated ? ", estimated" : "";
  if (e.t != null) return `- ${phaseName(e)}: ${e.local || e.when} (${inDays(e.t, now)}${est})${e.note ? `. ${e.note}` : ""}`;
  return `- ${phaseName(e)}: ${range(e.start, e.end)}${endOf(e) < now ? " (passed)" : startOf(e) <= now ? " (under way)" : ""}${est ? " (estimated)" : ""}`;
}

// ----------------------------------------------------------------- tools

function venueReport(v, year, now) {
  const editions = v.editions
    .filter(ed => year ? ed.year === year : !ed.end || Date.parse(ed.end + "T23:59:59Z") >= now)
    .sort((a, b) => a.year - b.year);
  const lines = [`## ${v.name}: ${v.full_name}`, `${AREAS[v.area] || v.area_label}, ${rankText(v)}.`];
  if (v.rolling) {
    const r = v.rolling, next = r.dates.map((t, i) => ({t, est: r.est?.[i]})).filter(d => d.t > now).slice(0, 4);
    lines.push(`Rolling submissions (${r.label}). Next deadlines: ${next.map(d => `${officialTime(d.t, r.tz)}${d.est ? " (estimated)" : ""}`).join("; ")}.${r.note ? " " + r.note : ""}`);
  }
  if (!editions.length) lines.push(year ? `No data for ${v.name} ${year}.` : "No upcoming edition in the data.");
  for (const ed of editions) {
    const conf = ed.start ? range(ed.start, ed.end) : "dates not announced";
    lines.push("", `### ${v.name} ${ed.year}${ed.estimated ? " (estimated from " + (ed.based_on || ed.year - 1) + ", not announced yet)" : ""}`,
      `Conference: ${conf}, ${ed.location || "location not announced"}.`);
    const all = v.events.filter(e => e.edition === ed.year && e.type !== "conference").sort((a, b) => startOf(a) - startOf(b));
    const events = all.filter(e => endOf(e) >= now - 30 * DAY);
    const dropNote = e => e.type === "abstract" && all.some(p => p.type === "paper" && p.round === e.round && p.note === e.note);
    if (events.length) lines.push(...events.map(e => eventLine(dropNote(e) ? {...e, note: null} : e, now)));
    else lines.push(all.length ? "- All of this edition's deadlines have passed." : "- No deadlines announced yet.");
    const gone = all.length - events.length;
    if (gone) lines.push(`- (${gone} earlier ${gone === 1 ? "date" : "dates"}, more than 30 days ago, ${gone === 1 ? "is" : "are"} left out.)`);
    if (ed.notes) lines.push(`Note: ${ed.notes}`);
    if (!ed.estimated && ed.url) lines.push(`Official page: ${ed.source || ed.url}${ed.last_verified ? ` (checked ${ed.last_verified})` : ""}`);
  }
  if (v.notes) lines.push("", `Series note: ${v.notes}`);
  return lines.join("\n");
}

function getConferenceDeadlines(data, args, now) {
  const asked = Array.isArray(args.conferences) ? args.conferences.slice(0, 10) : [];
  if (!asked.length) throw new ToolError("Give at least one conference name, e.g. {\"conferences\": [\"CVPR\"]}.");
  const parts = [], missing = [], seen = new Set();
  for (const text of asked) {
    const year = Number((String(text).match(/\b(20\d\d)\b/) || [])[1]) || null;
    const v = findVenue(data, String(text).replace(/\b20\d\d\b/, ""));
    if (v && seen.has(`${v.id} ${year}`)) continue;
    if (v) seen.add(`${v.id} ${year}`);
    if (v) parts.push(venueReport(v, year, now));
    else missing.push(String(text));
  }
  if (missing.length) parts.push(`Not covered by ML Deadlines: ${missing.join(", ")}. Covered: ${data.venues.map(v => v.name).join(", ")}.`);
  parts.push(`Times are in each conference's official time zone (AoE is UTC-12). Full timeline and calendar subscriptions: ${SITE}`);
  return parts.join("\n\n");
}

function listUpcoming(data, args, now) {
  const days = Math.min(400, Math.max(1, Number.isInteger(args.days) ? args.days : 60));
  const areas = Array.isArray(args.areas) && args.areas.length ? args.areas : null;
  const phase = args.phase || "submission";
  const withEst = args.include_estimated !== false;
  const types = {submission: ["abstract", "paper"], rebuttal: ["rebuttal"], notification: ["notification"],
                 camera_ready: ["camera_ready"], conference: ["conference"]}[phase];
  if (!types) throw new ToolError(`Unknown phase "${phase}". Use submission, rebuttal, notification, camera_ready or conference.`);
  const until = now + days * DAY, rows = [];
  for (const v of data.venues) {
    if (areas && !areas.includes(v.area)) continue;
    for (const e of v.events) {
      if (!types.includes(e.type) || (e.estimated && !withEst)) continue;
      const s = startOf(e);
      if (endOf(e) < now || s > until) continue;
      rows.push({s, text: e.t != null
        ? `- ${e.local || e.when} (${inDays(e.t, now)}): ${v.name} ${e.edition} ${phaseName(e).toLowerCase()}${e.estimated ? ", estimated" : ""}`
        : `- ${range(e.start, e.end)}${s <= now ? " (under way)" : ` (${inDays(s, now)})`}: ${v.name} ${e.edition} ${phaseName(e).toLowerCase()}${e.type === "conference" && e.location ? `, ${e.location}` : ""}${e.estimated ? ", estimated" : ""}`});
    }
    // monthly venues (VLDB) have no per-round events: list their rule-based deadlines
    if (phase === "submission" && v.rolling && !v.events.some(e => e.type === "paper")) {
      for (const t of v.rolling.dates) if (t > now && t <= until) {
        rows.push({s: t, text: `- ${officialTime(t, v.rolling.tz)} (${inDays(t, now)}): ${v.name} monthly submission deadline (${v.rolling.label})`});
      }
    }
  }
  rows.sort((a, b) => a.s - b.s);
  const scope = areas ? areas.map(a => AREAS[a]).join(", ") : "all areas";
  const what = {submission: "Submission deadlines", rebuttal: "Rebuttal periods", notification: "Notifications",
                camera_ready: "Camera-ready deadlines", conference: "Conferences"}[phase];
  const head = `${what} in the next ${days} days (${scope}), soonest first. Times are in each conference's official time zone (AoE is UTC-12).`;
  const body = rows.length ? rows.map(r => r.text).join("\n") : "- None in this window.";
  return `${head}\n${body}\n\nUse get_conference_deadlines for one conference's full dates and official link. Full timeline: ${SITE}`;
}

function listConferences(data, args, now) {
  const areas = Array.isArray(args.areas) && args.areas.length ? args.areas : Object.keys(AREAS);
  const out = [];
  for (const a of areas) {
    const vs = data.venues.filter(v => v.area === a);
    if (!vs.length) continue;
    out.push(`## ${AREAS[a]}`);
    for (const v of vs) {
      const ed = v.editions.filter(e => e.end && Date.parse(e.end + "T23:59:59Z") >= now).sort((x, y) => x.year - y.year)[0];
      const next = ed ? `next: ${v.name} ${ed.year}, ${range(ed.start, ed.end)}, ${ed.location || "location not announced"}${ed.estimated ? " (estimated)" : ""}` : "next edition not announced";
      out.push(`- ${v.name}: ${v.full_name} (${rankText(v)}; ${next})`);
    }
  }
  return `${out.join("\n")}\n\nFull timeline: ${SITE}`;
}

class ToolError extends Error {}

// ------------------------------------------------------------- protocol

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Accept, Mcp-Session-Id, Mcp-Protocol-Version, Authorization",
};
const json = (body, status = 200) => new Response(JSON.stringify(body), {status, headers: {"Content-Type": "application/json", ...CORS}});
const rpcError = (id, code, message) => ({jsonrpc: "2.0", id: id ?? null, error: {code, message}});

async function handle(msg, env) {
  if (!msg || msg.jsonrpc !== "2.0" || typeof msg.method !== "string") return rpcError(msg?.id, -32600, "Invalid request");
  const {id, method, params = {}} = msg;
  if (id === undefined) return null;  // notifications (e.g. notifications/initialized) get no response
  switch (method) {
    case "initialize": {
      const asked = params.protocolVersion;
      return {jsonrpc: "2.0", id, result: {
        protocolVersion: PROTOCOLS.includes(asked) ? asked : PROTOCOLS[0],
        capabilities: {tools: {listChanged: false}},
        serverInfo: {name: "ml-deadlines", title: "ML Deadlines", version: VERSION},
        instructions: INSTRUCTIONS,
      }};
    }
    case "ping": return {jsonrpc: "2.0", id, result: {}};
    case "tools/list": return {jsonrpc: "2.0", id, result: {tools: TOOLS}};
    case "resources/list": return {jsonrpc: "2.0", id, result: {resources: []}};
    case "prompts/list": return {jsonrpc: "2.0", id, result: {prompts: []}};
    case "tools/call": {
      const fn = {get_conference_deadlines: getConferenceDeadlines, list_upcoming_deadlines: listUpcoming, list_conferences: listConferences}[params.name];
      if (!fn) return rpcError(id, -32602, `Unknown tool: ${params.name}`);
      try {
        const text = fn(await loadData(env), params.arguments || {}, Date.now());
        return {jsonrpc: "2.0", id, result: {content: [{type: "text", text}], isError: false}};
      } catch (e) {
        // input mistakes and data outages are reported to the model as tool errors it can act on
        return {jsonrpc: "2.0", id, result: {content: [{type: "text", text: `Error: ${e.message}`}], isError: true}};
      }
    }
    default: return rpcError(id, -32601, `Method not found: ${method}`);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, {status: 204, headers: CORS});
    if (url.pathname === "/favicon.ico" || url.pathname === "/icon.png") {
      const bytes = Uint8Array.from(atob(ICON_PNG), c => c.charCodeAt(0));
      return new Response(bytes, {headers: {"Content-Type": "image/png", "Cache-Control": "public, max-age=86400", ...CORS}});
    }
    if (url.pathname !== "/mcp") {
      return new Response(`ML Deadlines connector for Claude. MCP endpoint: ${url.origin}/mcp\nSite: ${SITE}\n`,
        {headers: {"Content-Type": "text/plain; charset=utf-8", ...CORS}});
    }
    // this server sends no server-initiated messages, so there is no event stream to open; the protocol
    // asks for a 405 here, and the body explains the address to someone who opens it in a browser
    if (request.method !== "POST") {
      return new Response(`This is the address of the ML Deadlines connector for Claude.\n\nTo use it, add this address in Claude under Settings > Connectors > Add custom connector:\n${url.origin}/mcp\n\nThe deadlines themselves are at ${SITE}\n`,
        {status: 405, headers: {Allow: "POST, OPTIONS", "Content-Type": "text/plain; charset=utf-8", ...CORS}});
    }
    let body;
    try { body = await request.json(); } catch { return json(rpcError(null, -32700, "Parse error"), 400); }
    if (Array.isArray(body)) {
      const out = (await Promise.all(body.map(m => handle(m, env)))).filter(Boolean);
      return out.length ? json(out) : new Response(null, {status: 202, headers: CORS});
    }
    const out = await handle(body, env);
    return out ? json(out) : new Response(null, {status: 202, headers: CORS});
  },
};
