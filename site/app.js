// Renders the timeline and list views from the data embedded by scripts/build.py.
(function () {
  const DATA = window.__DATA__;
  const AREAS = [["all", "All areas"], ["ml", "Core ML"], ["ai", "General AI"], ["cv", "Vision"],
                 ["nlp", "NLP"], ["dm", "Data mining & IR"], ["db", "Databases"]];
  const SORTS = ["submission", "rebuttal", "decision", "conference"];
  // shown under a venue's name when nothing is coming up for the chosen order
  const NONE = {submission: "No dates announced", rebuttal: "No upcoming rebuttal",
                decision: "No upcoming decision", conference: "No dates announced"};
  const LABEL = {abstract: "Abstract", paper: "Paper", rebuttal: "Rebuttal", commitment: "Commitment", notification: "Notification",
                 camera_ready: "Camera-ready", conference: "Conference"};
  const SUBMISSION = new Set(["abstract", "paper"]);
  const DAY = 864e5;

  const localFmt = new Intl.DateTimeFormat(undefined, {weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"});
  const dayFmt = new Intl.DateTimeFormat(undefined, {month: "short", day: "numeric"});
  const tzName = Intl.DateTimeFormat().resolvedOptions().timeZone;
  // phones get a stacked timeline that fits all 12 months on screen (see style.css)
  const narrowQuery = window.matchMedia("(max-width: 640px)");

  // the search text (q) is not remembered between visits; everything else is
  let state = {view: "timeline", area: "all", showEst: true, sort: "submission", q: ""};
  try {
    const saved = JSON.parse(localStorage.getItem("mld-state") || "{}");
    if (saved.view === "list" || saved.view === "timeline") state.view = saved.view;
    if (AREAS.some(a => a[0] === saved.area)) state.area = saved.area;
    if (typeof saved.showEst === "boolean") state.showEst = saved.showEst;
    if (saved.sort === "deadline") state.sort = "submission";  // the name before the sort menu existed
    else if (SORTS.includes(saved.sort)) state.sort = saved.sort;
  } catch (e) {}
  function save() {
    const {q, ...kept} = state;
    try { localStorage.setItem("mld-state", JSON.stringify(kept)); } catch (e) {}
  }

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const day = iso => new Date(iso + "T12:00:00");
  const endOfDay = iso => new Date(iso + "T23:59:59").getTime();

  function rangeText(a, b) {
    const da = day(a), db = day(b);
    if (a === b) return dayFmt.format(da);
    return da.getMonth() === db.getMonth() ? `${dayFmt.format(da)}–${db.getDate()}` : `${dayFmt.format(da)} – ${dayFmt.format(db)}`;
  }
  function countdown(ms) {
    if (ms <= 0) return "passed";
    const d = Math.floor(ms / DAY), h = Math.floor(ms % DAY / 36e5), m = Math.floor(ms % 36e5 / 6e4);
    if (d >= 10) return `${d}d`;
    return d >= 1 ? `${d}d ${String(h).padStart(2, "0")}h` : `${h}h ${String(m).padStart(2, "0")}m`;
  }
  const urgency = ms => ms < 7 * DAY ? "urgent" : ms < 30 * DAY ? "soon" : "";
  function phaseName(e) {
    if (!e.round) return LABEL[e.type];
    return SUBMISSION.has(e.type) ? `${e.round} ${LABEL[e.type].toLowerCase()}` : `${LABEL[e.type]} (${e.round})`;
  }
  const evEnd = e => e.t ?? endOfDay(e.end);
  const startOfDay = iso => new Date(iso + "T00:00:00").getTime();
  // phases the author has to act on; only these get warning colours
  const ACTIONABLE = new Set(["abstract", "paper", "rebuttal", "commitment", "camera_ready"]);

  // the next moment anything happens: a deadline, or the start (or end, if running) of a range
  function nextMoment(events, now) {
    let best = null;
    for (const e of events) {
      let t = null, ends = false;
      if (e.t != null) { if (e.t > now) t = e.t; }
      else if (startOfDay(e.start) > now) t = startOfDay(e.start);
      else if (endOfDay(e.end) > now) { t = endOfDay(e.end); ends = true; }
      if (t != null && (!best || t < best.t)) best = {e, t, ends};
    }
    return best;
  }
  function momentLabel(m, year) {
    let name = phaseName(m.e);
    // when sorting by decision, notifications are called decisions, as in the sort menu
    if (state.sort === "decision" && m.e.type === "notification") name = name.replace("Notification", "Decision");
    if (m.e.edition !== year) name = `${m.e.edition} ${name.toLowerCase()}`;
    return name + (m.ends ? " ends" : "");
  }
  const tip = text => `data-tip="${esc(text)}" tabindex="0"`;

  // search ignores case and accents, so "montreal" finds Montréal
  const words = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .split(/[^a-z0-9]+/).filter(Boolean);
  // what a search can match: the venue's names, its edition years, and the city and country of its
  // editions that have not ended yet (a past edition's city would match a venue that is not going back there)
  const loaded = Date.now();
  const INDEX = new Map(DATA.venues.map(v => {
    const places = v.editions.filter(e => !e.end || endOfDay(e.end) >= loaded).map(e => e.location || "");
    if (places.some(p => /\bUSA\b/.test(p))) places.push("United States America");
    return [v.id, {acronym: words(v.name).join(""),
                   words: words([v.name, v.full_name, ...v.editions.map(e => e.year), ...places].join(" "))}];
  }));
  // every typed word must start a word of the venue ("us" finds USA but not "autonomous"),
  // or appear anywhere in its acronym ("ml" finds ICML and ECML-PKDD)
  function matches(v, query) {
    const ix = INDEX.get(v.id);
    return words(query).every(w => ix.acronym.includes(w) || ix.words.some(x => x.startsWith(w)));
  }
  const searching = () => words(state.q).length > 0;
  function shown(v) {
    // a search covers every area: the remembered area filter would otherwise hide what was asked for
    if (searching()) return matches(v, state.q);
    return state.area === "all" || v.area === state.area;
  }

  // ---------------------------------------------------------------- model

  // position in the chosen order: a deadline's time, or a range's start; a range already under way
  // (a running rebuttal or conference) comes first, soonest to end first
  function orderKey(r, now) {
    const e = r.key;
    if (!e) return Infinity;
    if (e.t != null) return e.t;
    const s = startOfDay(e.start);
    return s > now ? s : endOfDay(e.end) - 1e13;
  }

  function rows(now) {
    return DATA.venues
      .filter(v => !v.rolling && shown(v))
      .map(v => {
        const events = v.events.filter(e => state.showEst || !e.estimated);
        const first = list => list.sort((a, b) => (a.t ?? startOfDay(a.start)) - (b.t ?? startOfDay(b.start)))[0] || null;
        const next = first(events.filter(e => SUBMISSION.has(e.type) && e.t > now));
        const reb = first(events.filter(e => e.type === "rebuttal" && endOfDay(e.end) > now));
        const dec = first(events.filter(e => e.type === "notification" && e.t > now));
        const conf = first(events.filter(e => e.type === "conference" && endOfDay(e.end) > now));
        // the event the chosen order is based on
        const key = {submission: next, rebuttal: reb, decision: dec, conference: conf}[state.sort];
        // sorted by rebuttal or decision, the countdown shows that phase; otherwise the next event of any kind
        let moment;
        if (state.sort === "rebuttal") {
          moment = reb && (startOfDay(reb.start) > now ? {e: reb, t: startOfDay(reb.start), ends: false}
                                                       : {e: reb, t: endOfDay(reb.end), ends: true});
        } else if (state.sort === "decision") {
          moment = dec && {e: dec, t: dec.t, ends: false};
        } else {
          moment = nextMoment(events, now);
        }
        let year = key && key.edition;
        if (!year) {
          const upcoming = v.editions.filter(e => e.end && endOfDay(e.end) > now && (state.showEst || !e.estimated));
          year = upcoming.length ? upcoming[0].year : v.editions[v.editions.length - 1].year;
        }
        const ed = v.editions.find(e => e.year === year);
        const est = key ? key.estimated : ed.estimated;
        return {v, events, next, key, moment, ed, est};
      })
      .sort((a, b) => (orderKey(a, now) - orderKey(b, now)) || a.v.name.localeCompare(b.v.name));
  }

  // the countdown under each name (rows() decides what it counts down to)
  function countdowns(r, now) {
    const {moment, ed} = r;
    if (!moment) return `<span class="cd">${NONE[state.sort]}</span>`;
    const label = momentLabel(moment, ed.year), ms = moment.t - now;
    const cls = ACTIONABLE.has(moment.e.type) && !moment.ends ? urgency(ms) : "";
    return `<span class="cd ${cls}" data-cd="${moment.t}" data-prefix="${esc(label)} in ">${esc(label)} in ${countdown(ms)}</span>`;
  }

  function nameCell(r) {
    const {v, ed, est} = r;
    return `<div class="vn"><a href="${esc(ed.url || v.url)}" target="_blank" rel="noopener" title="${esc(v.full_name)}">${esc(v.name)}</a>`
      + `<span class="ed">${ed.year}</span>`
      + (v.rank === "unranked" ? "" : `<span class="rank" title="CORE 2023 rank">${esc(v.rank)}</span>`)
      + (est ? `<span class="est-tag" title="Dates estimated from last year's; not announced yet">est.</span>` : "") + `</div>`;
  }

  // ------------------------------------------------------------- timeline

  function renderTimeline(list, now) {
    const today = new Date(now); today.setHours(0, 0, 0, 0);
    // two weeks of lead-in keep today's deadlines off the chart edge
    const START = today.getTime() - 14 * DAY;
    const END = new Date(today.getFullYear() + 1, today.getMonth(), today.getDate()).getTime();
    const pct = ms => ((ms - START) / (END - START)) * 100;
    const nowX = pct(now);
    // nothing is drawn before today: bands that started earlier begin at the today line
    const clamp = x => Math.max(nowX, Math.min(100, x));

    let head = "", grid = "";
    let firstLabel = true;
    for (let m = 0; m <= 12; m++) {
      const d = new Date(today.getFullYear(), today.getMonth() + m, 1);
      if (d.getTime() <= START) continue;
      if (d.getTime() >= END) break;
      const x = pct(d.getTime()), jan = d.getMonth() === 0;
      const narrow = narrowQuery.matches;
      const year = " " + d.getFullYear();
      // on phones January is marked in bold instead of carrying the year, to save space
      const lbl = d.toLocaleString(undefined, {month: "short"}) + (!narrow && (jan || firstLabel) ? year : "");
      if (Math.abs(x - nowX) > 2) {
        head += `<div class="mo${jan ? " jan" : ""}" style="left:${x}%">${lbl}</div>`;
        firstLabel = false;
      }
      grid += `<i style="left:${x}%"></i>`;
    }
    grid += `<i class="now" style="left:${nowX}%"></i>`;

    const body = list.map(r => {
      const {v, events, next, ed} = r;
      let marks = "";
      const cls = e => (e.estimated ? " est" : "") + (evEnd(e) < now ? " past" : "");
      events.filter(e => e.type === "paper").forEach(p => {
        const n = events.filter(q => q.type === "notification" && q.edition === p.edition && q.round === p.round && q.t > p.t)
          .sort((a, b) => a.t - b.t)[0];
        if (!n) return;
        const a = clamp(pct(p.t)), b = clamp(pct(n.t));
        if (b > a) marks += `<span class="band review${cls(n)}" style="left:${a}%;width:${b - a}%" ${tip(`Under review${p.round ? " (" + p.round + ")" : ""}\n${p.when} → ${n.when}`)}></span>`;
      });
      events.forEach(e => {
        if (e.type === "rebuttal" || e.type === "conference") {
          const a = pct(day(e.start).getTime() - 12 * 36e5), b = pct(endOfDay(e.end));
          if (b < nowX || a > 100) return;
          const isConf = e.type === "conference";
          const prefix = isConf && e.edition !== ed.year ? `${v.name} ${e.edition}, ` : "";
          const loc = e.location || "location TBA", city = e.city || "location TBA";
          marks += `<span class="band ${isConf ? "conf" : "rebuttal"}${cls(e)}" style="left:${clamp(a)}%;width:${clamp(b) - clamp(a)}%" ${tip(`${isConf ? `${v.name} ${e.edition}` : phaseName(e)}\n${rangeText(e.start, e.end)}${isConf ? "\n" + loc : ""}${e.estimated ? "\nEstimated" : ""}`)}></span>`;
          if (isConf) {
            const narrow = narrowQuery.matches;
            const pos = b < (narrow ? 72 : 82) ? `left:calc(${clamp(b)}% + 5px)` : `right:calc(${100 - clamp(a)}% + 5px)`;
            const text = narrow ? (e.city || "TBA").split(" / ")[0] : prefix + rangeText(e.start, e.end) + " · " + city;
            marks += `<span class="clabel${cls(e)}" style="${pos}">${esc(text)}</span>`;
          }
          return;
        }
        const x = pct(e.t);
        if (x < nowX || x > 100) return;
        const shape = {abstract: "sub hollow", paper: "sub", commitment: "commit", notification: "notif"}[e.type] || "camera";
        const when = SUBMISSION.has(e.type) ? `${localFmt.format(new Date(e.t))} your time\n${e.when}` : e.when;
        marks += `<span class="mk ${shape}${cls(e)}" style="left:${x}%" ${tip(`${phaseName(e)}${e.estimated ? " (estimated)" : ""}\n${when}${e.note ? "\n" + e.note : ""}`)}></span>`;
      });
      const cd = countdowns(r, now);
      return `<div class="trow"><div class="tname"><div class="row1">${nameCell(r)}${subButton(v, true)}</div>${cd}</div>
        <div class="track">${marks}</div></div>`;
    }).join("");

    return `<p class="swipe-hint">Swipe the timeline sideways to see later months.</p><div class="tl-scroll"><div class="tl">
      <div class="tl-head"><div></div><div class="axis">${head}</div></div>${body}
      <div class="grid">${grid}</div></div></div>`;
  }

  // ----------------------------------------------------------------- list

  function bigCountdown(r, now) {
    const m = r.moment;
    if (!m) return `<div class="big"><span>–</span><small>${NONE[state.sort].toLowerCase()}</small></div>`;
    const ms = m.t - now, cls = ACTIONABLE.has(m.e.type) && !m.ends ? urgency(ms) : "";
    return `<div class="big ${cls}"><span data-cd="${m.t}">${countdown(ms)}</span><small>until ${esc(momentLabel(m, r.ed.year).toLowerCase())}</small></div>`;
  }

  function renderList(list, now) {
    return `<div class="list">` + list.map(r => {
      const {v, events, next, ed} = r;
      // the highlighted date is the one the countdown shows: the rebuttal or decision when sorted by it
      const hl = state.sort === "rebuttal" || state.sort === "decision" ? r.key : next;
      // rounds whose every date has passed are hidden to keep multi-round venues short
      const live = new Set(events.filter(e => e.edition === ed.year && evEnd(e) >= now).map(e => e.round));
      const chips = events.filter(e => e.edition === ed.year && e.type !== "conference" && live.has(e.round))
        .sort((a, b) => (a.t ?? day(a.start).getTime()) - (b.t ?? day(b.start).getTime())).map(e => {
        // deadlines in the visitor's time zone (official time on hover); ranges keep the venue's dates
        const when = e.start ? rangeText(e.start, e.end) : dayFmt.format(new Date(e.t));
        const title = e.t ? ` title="${esc(`${localFmt.format(new Date(e.t))} your time · ${e.when}`)}"` : "";
        return `<span class="ph${evEnd(e) < now ? " done" : ""}${hl === e ? " is-next" : ""}"${title}>${esc(phaseName(e))} ${esc(when)}</span>`;
      }).join("");
      const conf = ed.start ? rangeText(ed.start, ed.end) : "dates TBA";
      const estFrom = ed.based_on || ed.year - 1;
      let src = ed.estimated
        ? `Estimated from the ${estFrom} dates; not announced yet.`
        : ed.last_verified ? `Checked ${dayFmt.format(day(ed.last_verified))} against <a href="${esc(ed.source)}" target="_blank" rel="noopener">the official page</a>.` : "";
      if (!ed.estimated && events.some(e => e.edition === ed.year && e.estimated)) src += ` Dates marked est. are estimated from ${estFrom}.`;
      if (ed.notes) src += " " + esc(ed.notes);
      if (next && next.note) src += " " + esc(next.note);
      return `<div class="lrow${r.est ? " est" : ""}">
        ${bigCountdown(r, now)}
        <div>${nameCell(r)}<div class="meta">${esc(v.area_label)} · ${esc(conf)} · ${esc(ed.location || "location TBA")}</div></div>
        <div class="nextdl">${next ? `<b>${esc(phaseName(next))}</b> <span class="when">${localFmt.format(new Date(next.t))}</span><div class="aoe">${esc(next.when)}</div>` : ""}</div>
        <div class="phases">${chips}</div>
        <div class="act">${subButton(v, false)}</div>
        ${src ? `<div class="meta src">${src}</div>` : ""}</div>`;
    }).join("") + `</div>`;
  }

  // -------------------------------------------------------------- rolling

  function renderRolling(now) {
    const el = document.getElementById("rolling");
    const items = DATA.venues.filter(v => v.rolling && shown(v));
    el.hidden = !items.length;
    el.innerHTML = `<span class="lbl">Rolling submissions</span>` + items.map(v => {
      const r = v.rolling, dates = r.dates.filter(t => t > now);
      if (!dates.length) return "";
      const officialFmt = new Intl.DateTimeFormat(undefined, {month: "short", day: "numeric", timeZone: r.tz === "AoE" ? "Etc/GMT+12" : r.tz});
      const fmt = t => officialFmt.format(new Date(t));
      const ms = dates[0] - now;
      return `<span class="ven"><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.name)}</a><small>${esc(r.label)}</small></span>
        <span class="next" ${tip(`${localFmt.format(new Date(dates[0]))} your time${r.note ? "\n" + r.note : ""}`)}>next <b>${fmt(dates[0])}</b> · <span class="cd ${urgency(ms)}" data-cd="${dates[0]}">${countdown(ms)}</span></span>
        <span class="then">then ${dates.slice(1, 4).map(fmt).join(", ")}</span>${subButton(v, true)}`;
    }).join("");
  }

  // ------------------------------------------------------------ subscribe

  const CAL_ICON = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="2" y="3" width="12" height="11" rx="1.5"/><path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3M8 8.5v4M6 10.5h4"/></svg>`;
  function subButton(v, compact) {
    return compact
      ? `<button class="icon-btn" data-sub="${esc(v.id)}" aria-label="Add ${esc(v.name)} to your calendar" title="Add to calendar">${CAL_ICON}</button>`
      : `<button class="btn ghost" data-sub="${esc(v.id)}">Add to calendar</button>`;
  }
  function openMenu(btn) {
    const id = btn.dataset.sub;
    const v = DATA.venues.find(x => x.id === id);
    const https = new URL(`ics/${id}.ics`, location.href).href;
    const webcal = https.replace(/^https?:/, "webcal:");
    const menu = document.getElementById("menu");
    menu.innerHTML = `<div class="mh">${esc(v.name)}</div>
      <a href="https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcal)}" target="_blank" rel="noopener" data-track="${esc(id)}/google">Google Calendar</a>
      <a href="${esc(webcal)}" data-track="${esc(id)}/webcal">Apple Calendar or Outlook</a>
      <a href="${esc(https)}" download data-track="${esc(id)}/download">Download .ics file</a>
      <button data-copy="${esc(https)}" data-track="${esc(id)}/copy">Copy calendar link</button>
      <div class="note">Subscribing keeps your calendar in sync when dates change.</div>`;
    menu.hidden = false;
    const r = btn.getBoundingClientRect(), w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + "px";
    menu.style.top = (r.bottom + h + 8 < innerHeight ? r.bottom + 6 : Math.max(8, r.top - h - 6)) + "px";
    menu.querySelector("a").focus();
  }
  const closeMenu = () => { document.getElementById("menu").hidden = true; };

  function toast(text) {
    const el = document.getElementById("toast");
    el.textContent = text; el.hidden = false;
    clearTimeout(el._t); el._t = setTimeout(() => { el.hidden = true; }, 2500);
  }

  // ---------------------------------------------------------------- render

  function render() {
    const now = Date.now();
    document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", b.dataset.view === state.view));
    document.getElementById("sort").value = state.sort;
    document.getElementById("area").value = state.area;
    // the area menu is dimmed while a search runs, since the search covers all areas
    document.getElementById("area-pick").classList.toggle("off", searching());
    document.getElementById("show-est").checked = state.showEst;
    renderRolling(now);
    const list = rows(now);
    let empty = "No venues in this area.";
    if (searching()) {
      const rolling = DATA.venues.filter(v => v.rolling && shown(v)).map(v => v.name);
      empty = rolling.length ? `${esc(rolling.join(", "))} takes submissions on a rolling basis, shown below.`
                             : `No conference matches “${esc(state.q.trim())}”.`;
    }
    document.getElementById("view").innerHTML = list.length
      ? (state.view === "timeline" ? renderTimeline(list, now) : renderList(list, now))
      : `<div class="list empty">${empty}</div>`;
    document.getElementById("legend").hidden = state.view !== "timeline";
  }

  function tick() {
    const now = Date.now();
    document.querySelectorAll("[data-cd]").forEach(el => {
      if (el.dataset.cd) el.textContent = (el.dataset.prefix || "") + countdown(+el.dataset.cd - now);
    });
  }

  const gen = new Date(DATA.generated);
  document.getElementById("footer").innerHTML =
    `<span>Data updated ${dayFmt.format(gen)} ${gen.getFullYear()}. Ranks from CORE 2023. Times are in your time zone (${esc(tzName)}).</span>
     <span>Visits are counted anonymously with <a href="https://www.goatcounter.com" target="_blank" rel="noopener">GoatCounter</a>: no cookies, no personal data stored.</span>
     <a href="${esc(DATA.repo)}/issues/new?template=update-dates.yml" target="_blank" rel="noopener">Report a wrong date</a>
     <a href="${esc(DATA.repo)}/issues/new?template=add-conference.yml" target="_blank" rel="noopener">Suggest a conference</a>
     <a href="${esc(DATA.repo)}" target="_blank" rel="noopener">Source on GitHub</a>
     <span>Built by <a href="https://scholar.google.com/citations?user=v-tnmbwAAAAJ" target="_blank" rel="noopener">Antonio Ferrara</a></span>`;

  document.addEventListener("click", e => {
    // calendar subscriptions are counted as GoatCounter events, e.g. "calendar/iclr/google"
    const tracked = e.target.closest("[data-track]");
    if (tracked && window.goatcounter && window.goatcounter.count) {
      window.goatcounter.count({path: `calendar/${tracked.dataset.track}`, title: "Calendar subscription", event: true});
    }
    const copy = e.target.closest("[data-copy]");
    if (copy) {
      navigator.clipboard?.writeText(copy.dataset.copy).then(() => toast("Calendar link copied"), () => toast(copy.dataset.copy));
      closeMenu(); return;
    }
    const sub = e.target.closest("[data-sub]");
    if (sub) { openMenu(sub); return; }
    if (!e.target.closest("#menu")) closeMenu();
    const vb = e.target.closest("[data-view]");
    if (vb) { state.view = vb.dataset.view; save(); render(); }
  });
  document.getElementById("area").innerHTML = AREAS.map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join("");
  document.getElementById("sort").addEventListener("change", e => { state.sort = e.target.value; save(); render(); });
  document.getElementById("area").addEventListener("change", e => { state.area = e.target.value; save(); render(); });
  document.getElementById("show-est").addEventListener("change", e => { state.showEst = e.target.checked; save(); render(); });
  const qEl = document.getElementById("q");
  const setQuery = text => { state.q = text; render(); };
  qEl.addEventListener("input", () => setQuery(qEl.value));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      closeMenu();
      if (document.activeElement === qEl && qEl.value) { qEl.value = ""; setQuery(""); }
    }
    // "/" jumps to the search box, unless the visitor is already typing somewhere
    if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) {
      e.preventDefault(); qEl.focus();
    }
  });

  const tipEl = document.getElementById("tip");
  function showTip(el, x, y) {
    tipEl.textContent = el.dataset.tip; tipEl.hidden = false;
    const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    tipEl.style.left = Math.max(8, Math.min(innerWidth - w - 8, x + 12)) + "px";
    tipEl.style.top = Math.max(8, y - h - 12) + "px";
  }
  document.addEventListener("mousemove", e => {
    const el = e.target.closest("[data-tip]");
    if (el) showTip(el, e.clientX, e.clientY); else tipEl.hidden = true;
  });
  document.addEventListener("focusin", e => {
    const el = e.target.closest("[data-tip]");
    if (el) { const r = el.getBoundingClientRect(); showTip(el, r.left, r.top); }
  });
  document.addEventListener("focusout", () => { tipEl.hidden = true; });

  render();
  narrowQuery.addEventListener("change", render);
  setInterval(tick, 30000);
  setInterval(render, 10 * 60000);
})();
