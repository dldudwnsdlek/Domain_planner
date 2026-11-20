// 커튼콜 플래너 프론트엔드 (순수 JS, 빌드 없음). ?demo 를 붙이면 백엔드 없이 저장된 예시 응답으로 동작한다.
//
// 화면 규칙
//  - 시각·금액·분은 서버 응답 값을 그대로 쓴다. 화면이 직접 계산하는 값은 '귀가 여유'(귀가 마감 − 도착 예정) 하나이고,
//    시작·종료·이동·도착을 모두 확인한 회차에서만 보여 준다.
//  - 확인할 수 없는 값은 지어내지 않고 '확인 필요'로 표시한다.
//  - 서버 데이터는 textContent로만 넣는다(innerHTML을 쓰지 않는다). 외부 링크는 http(s)만 연결한다.
//  - 진행 단계를 실시간으로 받는 API가 없으므로, 기다리는 동안에는 가짜 진행률 대신 경과 시간과 스켈레톤만 보여 준다.

// ?demo 또는 정적 배포본(<html data-mode="demo">, scripts/build_static_demo.py)이면 예시 모드로 동작한다
const DEMO = new URLSearchParams(location.search).has("demo") || document.documentElement.dataset.mode === "demo";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const WIDE = window.matchMedia("(min-width: 1100px)");            // 이 폭부터 오른쪽 관람 계획 패널을 쓴다
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

const SERVICE_LABEL = { kopis: "KOPIS", kakao: "카카오", kma: "기상청", llm: "LLM(GMS)" };
// 서버 판정에서 '판정 불가(UNKNOWN)'로 이어지는 사유 코드 (constraints.py). 나머지 제외 사유는 '조건 미충족'이다
const UNKNOWN_CODES = new Set(["NO_RUNTIME", "NO_TRANSIT", "PRICE_UNPARSED", "SCHEDULE_UNPARSED", "NO_PERIOD"]);
const NEXT_DAY_CUTOFF = 5 * 60;   // 서버와 같은 규칙: 05:00 이전 시각은 다음 날 새벽으로 본다
const TIGHT_MARGIN_MIN = 30;      // 화면 경고 기준: 대중교통 시간은 막차·배차를 반영하지 않으므로 여유가 30분보다 적으면 알린다
const DEFAULT_HINT = "Enter로 찾기, Shift+Enter로 줄바꿈";

// 서울 지하철 노선색. 대중교통 요약 문자열의 노선 이름을 색 칩으로 바꿀 때만 쓴다
const LINE_COLORS = {
  "1호선": "#0052A4", "2호선": "#00A84D", "3호선": "#EF7C1C", "4호선": "#00A5DE", "5호선": "#996CAC",
  "6호선": "#CD7C2F", "7호선": "#747F00", "8호선": "#E6186C", "9호선": "#BDB092", "신분당선": "#D4003B",
  "경의중앙선": "#77C4A3", "공항철도": "#0090D2", "수인분당선": "#F5A200", "경춘선": "#0C8E72", "우이신설선": "#B0CE18",
};
const LIGHT_LINES = new Set(["9호선", "수인분당선", "우이신설선", "경의중앙선"]);

// ── 상태 ──────────────────────────────────────────────────────────────────
const state = {
  sessionId: null,
  exchanges: [],        // { request, fresh, response, error, pending, startedAt }
  board: null,          // 추천 카드·제외 목록을 그리는 마지막 '검색' 응답
  boardVersion: 0,      // 새 검색 응답이 올 때마다 1씩 올린다
  renderedVersion: -1,  // 화면에 그려 둔 보드 버전 (같으면 다시 그리지 않는다)
  selected: 0,          // 관람 계획을 보여 줄 추천 순번 (서버 추천 순서 그대로)
  saved: new Map(),     // performance_id → { overlaps } 또는 { error }
  saving: new Set(),
  savedDirty: false,    // 대화로 저장한 결과를 카드·패널에 반영해야 할 때
  busy: false,
};
try { state.sessionId = localStorage.getItem("cc_session"); } catch (_) { /* 저장소를 못 쓰면 서버가 새로 발급한다 */ }

// ── API ───────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  if (DEMO) return window.demoApi(method, path, body);
  const res = await fetch(path, {
    method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data.error || { code: `HTTP_${res.status}`, message: `서버가 요청을 처리하지 못했어요 (HTTP ${res.status}).` };
  return data;
}

// 서버가 준 오류 문장은 사용자용이다. 연결 실패 같은 브라우저 오류는 기술 문구 대신 안내 문장을 쓴다
function errorText(err) {
  if (err && err.code && err.message) return err.message;
  return "서버에 연결하지 못했어요. 서버가 켜져 있는지 확인한 뒤 다시 시도해 주세요.";
}

// ── DOM 도우미 ────────────────────────────────────────────────────────────
function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false || child === "") continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

const ICON_PATHS = {
  check: "M3.5 8.5l3 3 6-7",
  alert: "M8 2.2l6.3 11.3H1.7zM8 6.6v3.2M8 11.8v.2",
  question: "M8 14.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM6.3 6.3a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.3M8 11.5v.2",
};
function icon(name) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", ICON_PATHS[name]);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.7");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}
function archMark() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  for (const d of ["M3.5 21V10.5a8.5 8.5 0 0 1 17 0V21", "M3.5 10.5c3 .2 5 4 5.2 10.5M20.5 10.5c-3 .2-5 4-5.2 10.5", "M2 21h20"]) {
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.2");
    path.setAttribute("stroke-linecap", "round");
    svg.append(path);
  }
  return svg;
}

// 응답 문장의 **굵게** 표시만 살리고 나머지는 글자 그대로 넣는다
function richText(text) {
  const frag = document.createDocumentFragment();
  for (const part of String(text ?? "").split(/(\*\*[^*]+\*\*)/g)) {
    if (/^\*\*[^*]+\*\*$/.test(part)) frag.append(h("strong", null, part.slice(2, -2)));
    else if (part) frag.append(part);
  }
  return frag;
}
const plainText = (text) => String(text ?? "").replace(/\*\*/g, "");

function announce(text) {
  const live = $("#live");
  live.textContent = "";
  setTimeout(() => { live.textContent = text; }, 60);
}

function scrollToEl(el, block = "start") {
  if (el) el.scrollIntoView({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block });
}

// ── 표시용 변환 (서버 값을 다듬기만 하고 새 값을 만들지 않는다) ─────────────
const WEEK = ["일", "월", "화", "수", "목", "금", "토"];
function parseISODate(iso) {
  const [y, m, d] = String(iso).split("-").map(Number);
  return new Date(y, m - 1, d);
}
function dateShort(iso) {
  const d = parseISODate(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : `${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEK[d.getDay()]})`;
}
function dateLong(iso) {
  const d = parseISODate(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : `${d.getMonth() + 1}월 ${d.getDate()}일 ${WEEK[d.getDay()]}요일`;
}
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function formatTs(ts) {
  const m = String(ts || "").match(/^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return m ? `${Number(m[1])}월 ${Number(m[2])}일 ${m[3]}:${m[4]}` : String(ts || "");
}
const won = (n) => `${Number(n).toLocaleString("ko-KR")}원`;
function clockMinutes(hhmm) {
  const [hour, minute] = String(hhmm).split(":").map(Number);
  const total = hour * 60 + minute;
  return total < NEXT_DAY_CUTOFF ? total + 24 * 60 : total;
}
function durationText(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}분`;
  return rest ? `${hours}시간 ${rest}분` : `${hours}시간`;
}
function regionOf(address) {
  if (!address) return null;
  const [sido, gu] = String(address).split(/\s+/);
  const shortSido = sido.replace(/(특별자치시|특별자치도|특별시|광역시|도)$/, "");
  return gu && /[구시군]$/.test(gu) ? `${shortSido} ${gu}` : shortSido;
}
const safeUrl = (url) => (typeof url === "string" && /^https?:\/\//i.test(url) ? url : null);
const homeLabel = (u) => u.home_location || "집";
const passShow = (rec) => rec.showtimes.find((s) => s.verdict === "PASS") || rec.showtimes[0] || {};
// 카카오에 대중교통 경로가 없으면 서버가 도보 시간을 추정한다(kakao.py: summary "도보 약 N분 …", 근거 "(도보 추정)")
const isWalkEstimate = (rec) => Boolean(rec.transit && (String(rec.transit.summary || "").startsWith("도보")
  || (rec.evidence || []).some((e) => e.includes("도보 추정"))));

// 귀가 여유: 시작·종료·이동·도착을 모두 확인했고(도보 추정 아님) 귀가 마감이 있을 때만 계산한다
function marginOf(rec, show, u) {
  if (!u.home_by || !show.start || !show.end || !show.home_arrival || !rec.transit || isWalkEstimate(rec)) return null;
  const minutes = clockMinutes(u.home_by) - clockMinutes(show.home_arrival);
  if (minutes < 0) return null;  // 조건 충족 회차라면 생기지 않는다. 생기면 보여 주지 않는다
  return { minutes, tight: minutes < TIGHT_MARGIN_MIN };
}

function weatherText(x) {
  const sky = x.pty && x.pty !== "없음" ? x.pty : x.sky;
  return [sky || "하늘 상태 정보 없음", x.tmp != null ? `${x.tmp}℃` : null, x.pop != null ? `강수확률 ${x.pop}%` : null]
    .filter(Boolean).join(", ");
}
function weatherSummary(w) {
  if (!w) return null;
  if (w.status === "ok") return w.summary;
  if (w.status === "out_of_range") return "관람일이 가까워지면 예보를 볼 수 있어요";
  return "날씨 정보를 확인하지 못했어요";
}

function routeChips(summary) {
  return String(summary || "").split("→").map((s) => s.trim()).filter(Boolean).map((name) => {
    if (LINE_COLORS[name]) {
      const chip = h("span", { class: `route-chip${LIGHT_LINES.has(name) ? " light" : ""}` }, name);
      chip.style.backgroundColor = LINE_COLORS[name];
      return chip;
    }
    if (/^[A-Z]?\d+[A-Za-z-]?\d*$/.test(name)) return h("span", { class: "route-chip bus" }, `버스 ${name}`);
    return h("span", { class: "route-chip other" }, name);
  });
}

function poster(rec, { eager = false } = {}) {
  const box = h("div", { class: "poster" });
  const placeholder = () => box.replaceChildren(h("div", { class: "poster-ph" }, archMark(), h("span", null, rec.title)));
  // HTTPS로 배포된 화면에서는 http 포스터가 막힐 수 있어 https로 바꿔 부른다 (KOPIS는 https 지원)
  const raw = safeUrl(rec.poster_url);
  const src = raw && location.protocol === "https:" ? raw.replace(/^http:\/\//i, "https://") : raw;
  if (src) {
    const img = h("img", { src, alt: `${rec.title} 포스터`, loading: eager ? "eager" : "lazy", decoding: "async" });
    img.addEventListener("error", placeholder, { once: true });
    box.append(img);
  } else {
    placeholder();
  }
  return box;
}

// ── 요청 보내기 ───────────────────────────────────────────────────────────
const lastExchange = () => state.exchanges[state.exchanges.length - 1];
const isSearchResult = (res) => (res.recommendations || []).length > 0 || res.status === "limit_reached"
  || (res.excluded || []).length > 0;

// fresh=true: 새 검색. 새 세션으로 보내 앞의 조건을 이어받지 않는다.
// fresh=false: 이어서 요청. 같은 세션으로 보내 서버 Memory(조건·직전 추천)를 그대로 쓴다.
async function send(text, { fresh }) {
  const message = String(text).trim();
  if (!message || state.busy) return;
  if (fresh) resetConversation();
  const ex = { request: message, fresh, response: null, error: null, pending: true, startedAt: Date.now() };
  state.exchanges.push(ex);
  setBusy(true);
  render();
  scrollToEl(fresh ? $("#results") : $("#exchange"));
  try {
    const res = await api("POST", "/api/chat", { session_id: state.sessionId, message });
    ex.response = res;
    absorb(res);
  } catch (err) {
    ex.error = errorText(err);
  } finally {
    ex.pending = false;
    setBusy(false);
    render();
    afterResponse(ex);
  }
}

function absorb(res) {
  state.sessionId = res.session_id || state.sessionId;
  try { localStorage.setItem("cc_session", state.sessionId); } catch (_) { /* 무시 */ }
  if (isSearchResult(res)) {
    state.board = res;
    state.boardVersion += 1;
    state.selected = 0;
    state.saved.clear();
  }
  // "1번 저장해줘"처럼 대화로 저장해도 카드와 관람 계획에 '저장됨'을 표시한다
  if (res.saved_plan && state.board) {
    state.saved.set(res.saved_plan.performance_id, { overlaps: res.overlaps || [] });
    state.savedDirty = true;
  }
}

function afterResponse(ex) {
  if (ex.error) { announce(`요청을 처리하지 못했어요. ${ex.error}`); return; }
  const res = ex.response;
  const count = (res.recommendations || []).length;
  if (res.status === "clarify") {
    announce(plainText(res.reply));
    $("#followup-input").focus({ preventScroll: true });
    scrollToEl($("#exchange"));
  } else if (count) {
    announce(`추천 공연 ${count}편을 찾았어요.`);
  } else if (res.status === "limit_reached") {
    announce("조건에 맞는 공연을 찾지 못했어요.");
  } else {
    announce(plainText(res.reply).split("\n")[0]);
  }
}

function resetConversation() {
  state.sessionId = null;
  state.exchanges = [];
  state.board = null;
  state.selected = 0;
  state.saved.clear();
  const sheet = $("#plan-sheet");
  sheetOpener = null;
  if (sheet.open) sheet.close();
}

function retry(ex) {
  state.exchanges = state.exchanges.filter((e) => e !== ex);
  send(ex.request, { fresh: ex.fresh });
}

let ticker = null;
function setBusy(flag) {
  state.busy = flag;
  const buttons = [
    [$("#search-btn"), searchLabel(), "찾는 중"],
    [$("#followup-btn"), "보내기", "보내는 중"],
  ];
  for (const [btn, idle, busyText] of buttons) {
    btn.setAttribute("aria-busy", String(flag));
    btn.replaceChildren(...(flag ? [h("span", { class: "spinner", "aria-hidden": "true" }), busyText] : [idle]));
  }
  $("#search-input").readOnly = flag;
  $("#followup-input").readOnly = flag;
  clearInterval(ticker);
  if (flag) {
    ticker = setInterval(() => {
      $$(".elapsed[data-since]").forEach((el) => {
        el.textContent = `${Math.floor((Date.now() - Number(el.dataset.since)) / 1000)}초`;
      });
    }, 1000);
  }
}
const searchLabel = () => (state.exchanges.length ? "새로 찾기" : "공연 찾기");

// ── 그리기 ────────────────────────────────────────────────────────────────
function render() {
  const active = state.exchanges.length > 0;
  document.body.classList.toggle("has-conversation", active);
  const results = $("#results");
  if (active && results.classList.contains("hidden")) {
    results.classList.remove("reveal");
    void results.offsetWidth;  // 다시 나타날 때도 짧게 페이드인
    results.classList.add("reveal");
  }
  results.classList.toggle("hidden", !active);
  // 이어서 요청은 서버가 기억하는 대화가 있을 때만 의미가 있다 (첫 요청이 실패하면 숨긴다)
  $("#followup").classList.toggle("hidden", !state.exchanges.some((e) => e.response));
  if (!state.busy) $("#search-btn").replaceChildren(searchLabel());
  renderExchange();
  renderBoard();
  renderFollowup();
  if (state.savedDirty) {
    state.savedDirty = false;
    refreshPlanViews();
  }
}

function renderExchange() {
  const root = $("#exchange");
  const ex = lastExchange();
  if (!ex) { root.replaceChildren(); return; }
  root.replaceChildren(h("article", { class: "exchange", "aria-label": "요청과 답" },
    ex.request && h("p", { class: "you" }, h("span", { class: "you-k" }, "내 요청"), h("span", { class: "you-v" }, ex.request)),
    ex.pending ? workingView(ex) : ex.error ? errorView(ex) : ex.response ? answerView(ex.response) : null));
}

function workingView(ex) {
  return h("div", { role: "status" },
    h("p", { class: "working" }, h("span", { class: "spinner", "aria-hidden": "true" }), "요청을 처리하고 있어요",
      h("span", { class: "elapsed", "data-since": ex.startedAt }, "0초")),
    h("p", { class: "working-desc" },
      "공연을 찾을 때는 그날의 회차, 가격, 귀가 경로를 하나씩 확인해서 시간이 걸려요. 조건을 넓혀 다시 찾으면 조금 더 걸릴 수 있어요."));
}

function errorView(ex) {
  return h("div", { class: "notice error", role: "alert" },
    h("p", null, h("strong", null, "답을 받지 못했어요. "), ex.error),
    h("div", { class: "notice-actions" },
      h("button", { type: "button", class: "btn-secondary", onclick: () => retry(ex) }, "다시 시도")));
}

function answerView(res) {
  const replyClass = res.status === "clarify" ? "reply is-question" : res.status === "error" ? "reply is-error" : "reply";
  return [
    h("p", { class: replyClass }, richText(res.reply)),
    conditionChips(res.understood || {}),
    (res.defaults_applied || []).map((d) => h("p", { class: "notice info" }, d)),
    (res.warnings || []).map((w) => h("p", { class: "notice warn" }, w.message)),
    res.facts ? factsView(res.facts) : null,
    res.saved_plan ? savedView(res.saved_plan) : null,
    res.trace?.length ? traceView(res.trace, res.elapsed_ms) : null,
  ];
}

function conditionChips(u) {
  const items = [
    ["날짜", u.date && dateShort(u.date)],
    ["시작", u.start_after && `${u.start_after} 이후`],
    ["종료", u.end_by && `${u.end_by}까지`],
    ["지역", u.region],
    ["장르", u.genre],
    ["귀가", u.home_by && `${u.home_by}까지 ${homeLabel(u)} 도착`],
    ["도착할 곳", !u.home_by && u.home_location],
    ["예산", u.budget_max != null && `${won(u.budget_max)} 이하`],
    ["작품", u.keyword && `‘${u.keyword}’`],
  ].filter(([, v]) => v);
  if (!items.length) return null;
  return h("div", { class: "understood" }, h("span", { class: "understood-k" }, "이렇게 이해했어요"),
    items.map(([k, v]) => h("span", { class: "cond" }, h("span", { class: "cond-k" }, k), h("span", { class: "cond-v" }, v))));
}

function traceView(trace, totalMs) {
  const replans = trace.filter((s) => s.is_replan).length;
  const total = totalMs ?? trace.reduce((sum, s) => sum + (s.elapsed_ms || 0), 0);
  const summary = `AI가 거친 과정 보기 (${trace.length}단계, ${(total / 1000).toFixed(1)}초${replans ? `, 재계획 ${replans}회 포함` : ""})`;
  const list = h("ol", { class: "trace" }, trace.map((step) => {
    const [head, ...rest] = String(step.label).split(" — ");
    return h("li", { class: step.is_replan ? "replan" : step.ok === false ? "fail" : null },
      h("span", null, h("span", { class: "t-head" }, head), rest.length ? h("span", { class: "t-detail" }, rest.join(" — ")) : null),
      h("span", { class: "t-ms" }, step.elapsed_ms != null ? `${(step.elapsed_ms / 1000).toFixed(1)}초` : ""));
  }));
  return h("details", { class: "trace-box" }, h("summary", null, summary), list,
    h("p", { class: "trace-link" },
      h("button", { type: "button", class: "btn-text", onclick: () => switchView("logs", { session: state.sessionId }) },
        "이 대화의 전체 실행 기록 보기")));
}

function factsView(f) {
  if (!f.found) return h("p", { class: "notice info" }, f.message || "정보를 찾지 못했어요.");
  if (f.kind === "weather") {
    return h("section", { class: "fact-card", "aria-label": "날씨 예보" },
      h("h3", { class: "fact-title" }, `${f.place} 날씨`),
      h("p", { class: "fact-sub" }, [f.date && dateLong(f.date), f.base].filter(Boolean).join(", ")),
      f.address && h("p", { class: "fact-sub" }, f.address),
      h("dl", { class: "facts" }, (f.hours || []).flatMap((x) => [h("dt", null, x.time), h("dd", null, weatherText(x))])),
      h("p", { class: "fact-source" }, "출처: 기상청 단기예보 (공공누리 제1유형)"));
  }
  const rows = [
    ["러닝타임", f.runtime_min ? `${f.runtime_min}분` : null], ["관람 등급", f.age_rating], ["공연장", f.venue_name],
    ["기간", f.period], ["공연 시간", f.schedule_raw], ["가격", f.price_raw],
  ];
  return h("section", { class: "fact-card", "aria-label": "공연 정보" },
    h("h3", { class: "fact-title" }, f.title),
    h("dl", { class: "facts" }, rows.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v || "정보 없음")])),
    h("p", { class: "fact-source" }, "출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr)"));
}

function savedView(p) {
  const when = `${dateShort(p.date)} ${p.start_time}${p.end_time ? `–${p.end_time}` : ""}`;
  return h("section", { class: "saved-card", "aria-label": "저장한 계획" },
    h("p", { class: "saved-k" }, "내 관람 계획에 저장했어요"),
    h("p", { class: "saved-title" }, p.title),
    h("p", { class: "saved-meta" }, p.venue_name ? `${when}, ${p.venue_name}` : when),
    h("button", { type: "button", class: "btn-secondary", onclick: () => switchView("plans") }, "내 관람 계획 보기"));
}

// ── 결과 보드: 추천 카드 + 관람 계획 ─────────────────────────────────────
function renderBoard() {
  const root = $("#board");
  const latest = lastExchange();
  const pending = Boolean(latest && latest.pending);
  root.classList.toggle("is-busy", pending && Boolean(state.board));
  root.setAttribute("aria-busy", String(pending));
  if (!state.board) {
    state.renderedVersion = -1;
    root.replaceChildren(...(pending ? [skeletonBoard()] : []));
    return;
  }
  if (state.renderedVersion !== state.boardVersion) {
    state.renderedVersion = state.boardVersion;
    root.replaceChildren(...boardView(state.board));
    applySelection();
    if (WIDE.matches) renderPlanPanel();
  }
  const tag = $("#board-tag");
  if (tag) {
    const stale = latest && !latest.pending && latest.response && latest.response !== state.board;
    tag.textContent = stale ? "직전 검색 결과예요" : "";
  }
}

function boardView(res) {
  const recs = res.recommendations || [];
  const u = res.understood || {};
  const meta = [];
  if (recs.length) {
    if (recs[0].date) meta.push(`${dateLong(recs[0].date)} 공연이에요.`);
    meta.push("이른 회차부터, 시각이 같으면 가격이 낮은 순서로 보여 드려요.");
    if (res.replan_count) meta.push(`후보가 부족해 조건을 넓혀 ${res.replan_count}번 다시 찾았어요.`);
  }
  const out = [h("div", { class: "board-head" },
    h("div", null,
      h("h2", { class: "board-title", id: "board-title" }, recs.length ? `추천 공연 ${recs.length}편` : "조건에 맞는 공연을 찾지 못했어요"),
      meta.length ? h("p", { class: "board-meta" }, meta.join(" ")) : null),
    h("span", { class: "board-tag", id: "board-tag" }))];
  if (recs.length) {
    out.push(h("div", { class: "board-grid" },
      h("div", { class: "rec-list" }, recs.map((rec, i) => (i === 0 ? featuredCard(rec, u) : rowCard(rec, i, u)))),
      h("aside", { class: "plan-col", "aria-label": "선택한 공연의 관람 계획" }, h("div", { id: "plan-panel" }))));
  } else {
    out.push(emptyView(res));
  }
  if ((res.excluded || []).length) out.push(excludedView(res.excluded));
  if ((res.assumptions || []).length) {
    out.push(h("div", { class: "board-notes" }, h("span", { class: "board-notes-k" }, "참고"),
      h("ul", null, res.assumptions.map((n) => h("li", null, n)))));
  }
  return out;
}

const venueText = (rec) => [rec.venue?.name, regionOf(rec.venue?.address)].filter(Boolean).join(", ");
const savedSlot = (rec) => h("span", { class: "saved-slot", "data-pid": rec.performance_id },
  state.saved.has(rec.performance_id) && !state.saved.get(rec.performance_id).error ? h("span", { class: "saved-tag" }, "저장됨") : null);

function verdictBadges(rec) {
  // 추천 목록에는 서버가 '조건 충족(PASS)'으로 판정한 회차만 들어온다
  return [
    h("span", { class: "verdict ok" }, icon("check"), "조건 충족"),
    isWalkEstimate(rec) ? h("span", { class: "verdict warn" }, icon("alert"), "이동 시간 도보 추정") : null,
  ];
}

function priceView(rec) {
  if (rec.min_price != null) return h("p", { class: "price" }, h("span", { class: "price-k" }, "최저가"), won(rec.min_price));
  return h("p", { class: "price missing" }, rec.price_raw || "가격 확인 필요");
}

function selectButton(index) {
  return h("button", {
    type: "button", class: "btn-secondary select-btn", "aria-pressed": String(index === state.selected && WIDE.matches),
    onclick: (e) => { e.stopPropagation(); selectCard(index, { open: true }); },
  }, "관람 계획 보기");
}

function timeCell(label, value, sub, extra) {
  return h("div", { class: `time-cell${value ? "" : " missing"}${extra ? ` ${extra}` : ""}` },
    h("span", { class: "time-k" }, label),
    h("span", { class: "time-v" }, value || "확인 필요"),
    sub ? h("span", { class: "time-sub" }, sub) : null);
}

function timeCells(rec, show, u) {
  const cells = [
    timeCell("시작", show.start),
    timeCell("종료", show.end, show.end ? null : "러닝타임 정보 없음"),
  ];
  if (u.home_by || show.home_arrival) {
    const m = marginOf(rec, show, u);
    const sub = m && m.tight ? `여유 ${durationText(m.minutes)}` : u.home_by ? `마감 ${u.home_by}` : null;
    cells.push(timeCell(`${homeLabel(u)} 도착`, show.home_arrival, sub, `arrive${m && m.tight ? " tight" : ""}`));
  }
  const box = h("div", { class: "times" }, cells);
  box.style.setProperty("--cells", String(cells.length));
  return box;
}

function bindCardSelect(card, index) {
  card.addEventListener("click", (e) => {
    if (e.target.closest("a, button")) return;
    selectCard(index, { open: true });
  });
}

function featuredCard(rec, u) {
  const show = passShow(rec);
  const card = h("article", { class: "rec rec-featured", "data-index": "0", "aria-labelledby": "rec-title-0" },
    poster(rec, { eager: true }),
    h("div", { class: "rec-head" },
      h("div", { class: "rec-tags" }, h("span", { class: "rank-tag" }, "1순위 추천"),
        rec.genre && h("span", { class: "genre-tag" }, rec.genre), savedSlot(rec)),
      h("h3", { class: "rec-title", id: "rec-title-0" }, rec.title),
      h("p", { class: "rec-venue" }, venueText(rec)),
      h("div", { class: "rec-tags verdict-row" }, verdictBadges(rec))),
    h("div", { class: "rec-body" },
      timeCells(rec, show, u),
      h("div", { class: "rec-foot" }, priceView(rec), selectButton(0)),
      rec.evidence?.length ? h("p", { class: "evidence" }, h("b", null, "추천 근거 "), rec.evidence.join(", ")) : null));
  bindCardSelect(card, 0);
  return card;
}

function rowCard(rec, index, u) {
  const show = passShow(rec);
  const m = marginOf(rec, show, u);
  const sep = () => h("span", { class: "sep", "aria-hidden": "true" }, "→");
  const times = [h("b", null, show.start), " 시작"];
  times.push(sep(), ...(show.end ? [h("b", null, show.end), " 종료"] : ["종료 확인 필요"]));
  if (show.home_arrival) {
    times.push(sep(), h("span", { class: `arrive${m && m.tight ? " tight" : ""}` },
      h("b", null, show.home_arrival), ` ${homeLabel(u)} 도착`));
  }
  const card = h("article", { class: "rec rec-row", "data-index": String(index), "aria-labelledby": `rec-title-${index}` },
    poster(rec),
    h("div", { class: "row-main" },
      h("div", { class: "rec-tags" }, h("span", { class: "rank-num" }, `${index + 1}순위`),
        rec.genre && h("span", { class: "genre-tag" }, rec.genre), savedSlot(rec)),
      h("h3", { class: "rec-title", id: `rec-title-${index}` }, rec.title),
      h("p", { class: "rec-venue" }, venueText(rec)),
      h("p", { class: "mini-times" }, times)),
    h("div", { class: "row-aside" }, h("div", { class: "rec-tags" }, verdictBadges(rec)), priceView(rec), selectButton(index)));
  bindCardSelect(card, index);
  return card;
}

function emptyView(res) {
  const suggestions = res.suggestions || [];
  return h("section", { class: "empty", "aria-labelledby": "board-title" },
    h("p", { class: "empty-title" }, suggestions.length ? "이렇게 바꾸면 볼 수 있는 공연이 있어요" : "조건을 조금 바꿔 다시 요청해 보세요"),
    suggestions.length ? h("ul", { class: "empty-list" }, suggestions.map((s) => h("li", null, s.text))) : null,
    h("p", null, "날짜, 시각, 예산은 직접 정한 조건이라 자동으로 바꾸지 않았어요. 아래 ‘이어서 요청하기’에서 바꿀 조건만 말해 주세요."),
    h("div", { class: "notice-actions" },
      h("button", { type: "button", class: "btn-secondary", onclick: () => focusFollowup() }, "조건 바꿔서 다시 요청하기")));
}

function excludedView(list) {
  const unknown = list.filter((x) => UNKNOWN_CODES.has(x.reason_code));
  const failed = list.filter((x) => !UNKNOWN_CODES.has(x.reason_code));
  const counts = [failed.length && `조건 미충족 ${failed.length}`, unknown.length && `판정 불가 ${unknown.length}`].filter(Boolean).join(", ");
  const item = (x, isUnknown) => h("li", null,
    isUnknown ? h("span", { class: "verdict unknown" }, icon("question"), "판정 불가")
      : h("span", { class: "verdict warn" }, icon("alert"), "조건 미충족"),
    h("span", { class: "ex-title" }, x.title),
    h("span", { class: "ex-reason" }, x.reason));
  return h("details", { class: "excluded" },
    h("summary", null, `추천에서 뺀 공연 ${list.length}편`, h("span", { class: "excluded-counts" }, counts)),
    h("ul", { class: "ex-list" }, unknown.map((x) => item(x, true)), failed.map((x) => item(x, false))));
}

function skeletonBoard() {
  const line = (size) => h("div", { class: `sk sk-line${size ? ` ${size}` : ""}` });
  return h("div", { class: "board-grid", "aria-hidden": "true" },
    h("div", { class: "rec-list" },
      h("div", { class: "sk-card sk-featured" }, h("div", { class: "sk sk-poster" }),
        h("div", null, line("sm"), line("lg"), line("md"), h("div", { class: "sk sk-block" }), line("sm"))),
      [1, 2].map(() => h("div", { class: "sk-card sk-row" }, h("div", { class: "sk sk-poster" }),
        h("div", null, line("md"), line("lg"), line("sm"))))),
    h("div", { class: "plan-col" },
      h("div", { class: "sk-card" }, line("sm"), line("lg"), line("md"), line("md"), line("md"), line("md"), h("div", { class: "sk sk-block" }))));
}

// ── 선택 · 관람 계획 ─────────────────────────────────────────────────────
const currentRec = () => (state.board?.recommendations || [])[state.selected];

function applySelection() {
  $$(".rec").forEach((card) => {
    const on = Number(card.dataset.index) === state.selected && WIDE.matches;
    card.classList.toggle("is-selected", on);
    const btn = card.querySelector(".select-btn");
    if (btn) btn.setAttribute("aria-pressed", String(on));
  });
}

let sheetOpener = null;  // 시트를 닫으면 포커스를 돌려줄 버튼
function selectCard(index, { open = false } = {}) {
  if (!(state.board?.recommendations || [])[index]) return;
  state.selected = index;
  applySelection();
  if (WIDE.matches) renderPlanPanel({ animate: true });
  else if (open) {
    sheetOpener = $(`.rec[data-index="${index}"] .select-btn`);
    openSheet();
  }
}

function renderPlanPanel({ animate = false } = {}) {
  const slot = $("#plan-panel");
  const rec = currentRec();
  if (!slot) return;
  if (!rec) { slot.replaceChildren(); return; }
  const plan = planView(rec, state.selected, state.board);
  if (animate && !REDUCED_MOTION.matches) plan.classList.add("swap");
  slot.replaceChildren(plan);
}

function openSheet() {
  const rec = currentRec();
  if (!rec) return;
  const body = $("#sheet-body");
  body.replaceChildren(planView(rec, state.selected, state.board, { inSheet: true }));
  const sheet = $("#plan-sheet");
  if (!sheet.open) sheet.showModal();
  body.scrollTop = 0;
}

function refreshPlanViews() {
  if (WIDE.matches) renderPlanPanel();
  const sheet = $("#plan-sheet");
  if (sheet.open && currentRec()) {
    const body = $("#sheet-body");
    const top = body.scrollTop;
    body.replaceChildren(planView(currentRec(), state.selected, state.board, { inSheet: true }));
    body.scrollTop = top;
  }
  $$(".saved-slot").forEach((slot) => {
    const info = state.saved.get(slot.dataset.pid);
    slot.replaceChildren(...(info && !info.error ? [h("span", { class: "saved-tag" }, "저장됨")] : []));
  });
}

function planView(rec, index, res, { inSheet = false } = {}) {
  const u = res.understood || {};
  const show = passShow(rec);
  const m = marginOf(rec, show, u);
  const body = h("div", { class: "plan-body" },
    h("p", { class: "plan-k" }, h("span", null, inSheet ? `${index + 1}순위 추천` : "관람 계획"),
      inSheet ? null : h("span", null, `${index + 1}순위`)),
    h("h3", { class: "plan-title" }, rec.title),
    h("p", { class: "plan-sub" }, [rec.date && dateLong(rec.date), venueText(rec)].filter(Boolean).join(", ")),
    timeline(rec, show, u, res.assumptions || []),
    marginView(rec, show, u, m),
    checksView(rec, show, u),
    factsList(rec, show));
  return h("section", { class: "plan", "aria-label": `${rec.title} 관람 계획` }, body, stubView(rec, show));
}

function tlItem(kind, time, label, note, extra) {
  return h("li", { class: `tl-item ${kind}` },
    h("span", { class: "tl-time" }, time),
    h("span", { class: "tl-rail", "aria-hidden": "true" }),
    h("div", { class: "tl-content" }, h("p", { class: "tl-label" }, label), note ? h("p", { class: "tl-note" }, note) : null, extra));
}

function timeline(rec, show, u, assumptions) {
  const hours = rec.weather?.status === "ok" ? rec.weather.hours || [] : [];
  const wx = (time) => {
    const x = hours.find((w) => w.time === time);
    return x ? h("p", { class: "tl-wx" }, `날씨 ${weatherText(x)}`) : null;
  };
  const items = [tlItem("start", show.start, "공연 시작", rec.venue?.name, wx(show.start))];
  items.push(show.end ? tlItem("end", show.end, "공연 종료", null, wx(show.end))
    : tlItem("end missing", "확인 필요", "공연 종료", "러닝타임 정보가 없어 종료 시각을 알 수 없어요"));
  if (u.home_by || show.home_arrival) {
    if (rec.transit) {
      const walk = isWalkEstimate(rec);
      const exitNote = assumptions.find((a) => a.startsWith("퇴장 여유"));
      const chips = walk ? [] : routeChips(rec.transit.summary);
      items.push(tlItem("move", "이동", walk ? String(rec.transit.summary) : `대중교통 ${rec.transit.total_min}분`,
        exitNote || null, chips.length ? h("div", { class: "routes" }, chips) : null));
    } else {
      items.push(tlItem("move missing", "확인 필요", "이동 시간", "대중교통 경로를 확인하지 못했어요"));
    }
    items.push(show.home_arrival ? tlItem("arrive", show.home_arrival, `${homeLabel(u)} 도착 예정`, null, wx(show.home_arrival))
      : tlItem("arrive missing", "확인 필요", `${homeLabel(u)} 도착`));
    if (u.home_by) items.push(tlItem("deadline", u.home_by, "귀가 마감", "직접 정한 시각"));
  }
  return h("ol", { class: "tl", "aria-label": "관람 일정" }, items);
}

function marginView(rec, show, u, m) {
  if (m) {
    return h("p", { class: `margin${m.tight ? " tight" : ""}` }, icon(m.tight ? "alert" : "check"),
      h("span", null, `귀가 마감까지 ${durationText(m.minutes)} 여유`,
        m.tight ? h("small", null, "대중교통 시간은 막차와 배차 간격을 반영하지 않아요. 출발 전에 꼭 확인하세요.") : null));
  }
  if (u.home_by && isWalkEstimate(rec)) {
    return h("p", { class: "plan-hint" }, "대중교통 경로가 없어 도보 시간으로 추정했어요. 그래서 여유 시간은 계산하지 않았어요.");
  }
  if (!u.home_by && !show.home_arrival) {
    return h("p", { class: "plan-hint" }, "도착할 곳과 시각을 알려 주시면 귀가 시각까지 계산해 드려요. ",
      h("button", { type: "button", class: "btn-text", onclick: () => focusFollowup("밤 11시까지 망원역 도착처럼 알려 주세요") }, "이어서 요청하기"));
  }
  return null;
}

function checksView(rec, show, u) {
  const rows = [];
  if (u.start_after) rows.push([`${u.start_after} 이후 시작`, show.start && `${show.start} 시작`]);
  if (u.end_by) rows.push([`${u.end_by}까지 종료`, show.end && `${show.end} 종료`]);
  if (u.home_by) rows.push([`${u.home_by}까지 ${homeLabel(u)} 도착`, show.home_arrival && `${show.home_arrival} 도착`]);
  if (u.budget_max != null) rows.push([`${won(u.budget_max)} 이하`, rec.min_price != null && `최저가 ${won(rec.min_price)}`]);
  if (!rows.length) return null;
  return h("ul", { class: "checks", "aria-label": "조건 확인" }, rows.map(([cond, actual]) =>
    h("li", null, icon(actual ? "check" : "question"), h("span", null, cond), h("span", { class: "check-v" }, actual || "확인 필요"))));
}

function factsList(rec, show) {
  const others = rec.showtimes.filter((s) => s !== show && s.verdict === "PASS").map((s) => s.start);
  const hasHourly = rec.weather?.status === "ok" && (rec.weather.hours || []).length > 0;
  const rows = [
    ["가격", rec.price_raw || (rec.min_price != null ? won(rec.min_price) : "확인 필요")],
    ["관람 등급", rec.age_rating],
    ["다른 가능 회차", others.length ? others.join(", ") : null],
    ["날씨", hasHourly ? null : weatherSummary(rec.weather)],
    ["추천 근거", rec.evidence?.length ? rec.evidence.join(", ") : null],
  ].filter(([, v]) => v);
  return h("dl", { class: "plan-facts" }, rows.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)]));
}

function stubView(rec, show) {
  const pid = rec.performance_id;
  const info = state.saved.get(pid);
  const saved = info && !info.error;
  const saving = state.saving.has(pid);
  const parts = [];
  if (saved) {
    parts.push(h("button", { type: "button", class: "btn-primary is-saved", onclick: () => switchView("plans") },
      icon("check"), "저장했어요, 내 관람 계획 보기"));
    if (info.overlaps?.length) {
      const list = info.overlaps.map((p) => `${p.start_time}${p.end_time ? `–${p.end_time}` : ""} ${p.title}`).join(", ");
      parts.push(h("p", { class: "notice warn" }, `같은 날 겹치는 계획이 있어요: ${list}. 저장은 했어요.`));
    }
  } else {
    parts.push(h("button", {
      type: "button", class: "btn-primary", "aria-busy": String(saving), onclick: () => savePlan(rec, show),
    }, ...(saving ? [h("span", { class: "spinner", "aria-hidden": "true" }), "저장하는 중"] : ["내 관람 계획에 저장"])));
    if (info?.error) parts.push(h("p", { class: "notice error", role: "alert" }, info.error));
  }
  const links = [];
  const ticket = (rec.ticket_links || []).find((t) => safeUrl(t.url));
  if (ticket) links.push(h("a", { class: "btn-secondary", href: ticket.url, target: "_blank", rel: "noopener noreferrer" }, `${ticket.name || "예매처"}에서 예매`));
  const routeUrl = safeUrl(rec.transit?.map_url);
  const venueUrl = safeUrl(rec.venue?.map_url);
  if (routeUrl) links.push(h("a", { class: "btn-secondary", href: routeUrl, target: "_blank", rel: "noopener noreferrer" }, "카카오맵 길찾기"));
  else if (venueUrl) links.push(h("a", { class: "btn-secondary", href: venueUrl, target: "_blank", rel: "noopener noreferrer" }, "공연장 지도"));
  if (links.length) parts.push(h("div", { class: "stub-links" }, links));
  parts.push(h("p", { class: "stub-note" }, "가격과 회차는 바뀔 수 있으니 예매처에서 최종 확인하세요."));
  return h("div", { class: "plan-stub" }, parts);
}

async function savePlan(rec, show) {
  const pid = rec.performance_id;
  if (state.saving.has(pid)) return;
  state.saving.add(pid);
  state.saved.delete(pid);
  refreshPlanViews();
  try {
    const res = await api("POST", "/api/plans", {
      performance_id: pid, title: rec.title, venue_name: rec.venue?.name, venue_address: rec.venue?.address,
      date: rec.date, start_time: show.start, end_time: show.end, price: rec.min_price,
      ticket_url: rec.ticket_links?.[0]?.url, session_id: state.sessionId,
    });
    state.saved.set(pid, { overlaps: res.overlaps || [] });
    announce(`‘${rec.title}’ 공연을 내 관람 계획에 저장했어요.`);
  } catch (err) {
    state.saved.set(pid, { error: errorText(err) });
  } finally {
    state.saving.delete(pid);
    refreshPlanViews();
  }
}

// ── 이어서 요청하기 ───────────────────────────────────────────────────────
function renderFollowup() {
  const latest = lastExchange();
  const clarify = latest?.response?.status === "clarify";
  $("#followup").classList.toggle("is-clarify", clarify);
  $("#followup-title").textContent = clarify ? "답변하기" : "이어서 요청하기";
  $("#followup-desc").textContent = clarify
    ? "위 질문에 답해 주시면 앞에서 말한 조건과 이어서 찾아요."
    : "앞에서 말한 조건을 기억하고 있어요. 바꾸고 싶은 것만 말해 주세요.";
  $("#followup-input").placeholder = clarify ? "망원역" : "같은 날 뮤지컬로 바꿔줘";

  const chips = [];
  if (!clarify && (state.board?.recommendations || []).length) {
    const other = state.board.understood?.genre === "뮤지컬" ? "연극으로" : "뮤지컬로";
    chips.push(`같은 날 ${other} 바꿔줘`, "1번 저장해줘");
  }
  $("#followup-chips").replaceChildren(...chips.map((text) =>
    h("button", { type: "button", class: "chip", onclick: () => fillFollowup(text) }, text)));

  const older = state.exchanges.slice(0, -1).filter((e) => e.response || e.error);
  $("#history").replaceChildren(...(older.length ? [h("details", { class: "history" },
    h("summary", null, `이전 대화 ${older.length}개`),
    h("ol", null, older.map((e) => h("li", null,
      h("p", { class: "h-req" }, e.request || "(예시 요청)"),
      h("p", { class: "h-reply" }, e.error ? `처리하지 못했어요. ${e.error}` : plainText(e.response.reply))))))] : []));
}

function focusFollowup(placeholder) {
  const sheet = $("#plan-sheet");
  sheetOpener = null;  // 포커스를 입력창으로 옮기므로 카드 버튼으로 돌려주지 않는다
  if (sheet.open) sheet.close();
  const input = $("#followup-input");
  if (placeholder) input.placeholder = placeholder;
  scrollToEl(input, "center");
  input.focus({ preventScroll: true });
}

function fillFollowup(text) {
  const input = $("#followup-input");
  input.value = text;
  input.focus();
}

// ── 히어로 검색 · 조건 도우미 ─────────────────────────────────────────────
let hintTimer = null;
function hint(text) {
  const el = $("#search-hint");
  el.textContent = text;
  el.classList.add("is-message");
  clearTimeout(hintTimer);
  hintTimer = setTimeout(resetHint, 7000);
}
function resetHint() {
  const el = $("#search-hint");
  const len = $("#search-input").value.length;
  el.textContent = len > 400 ? `${len}/500자` : DEFAULT_HINT;
  el.classList.toggle("is-message", len > 400);
}

function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
}

function submitHero() {
  const input = $("#search-input");
  if (state.busy) return;
  if (!input.value.trim()) {
    hint("찾고 싶은 공연과 조건을 적어 주세요.");
    input.focus();
    return;
  }
  send(input.value, { fresh: true });
  input.value = "";
  autoGrow(input);
  resetHint();
}

// 고른 조건을 사람이 쓰는 문장으로 바꾼다. 서버에는 지금처럼 자연어 한 문장만 간다
function composeFromHelper() {
  const v = (id) => $(id).value.trim();
  const date = v("#h-date");
  const start = v("#h-start");
  const region = v("#h-region");
  const genre = v("#h-genre");
  const budget = v("#h-budget");
  const home = v("#h-home");
  const homeBy = v("#h-home-by");
  if (!date && !start && !region && !genre && !budget && !home && !homeBy) return { error: "조건을 하나 이상 골라 주세요." };
  if (Boolean(home) !== Boolean(homeBy)) return { error: "귀가 시각을 계산하려면 도착할 곳과 도착 시각을 함께 입력해 주세요." };
  if (budget && !(Number(budget) > 0)) return { error: "예산은 0보다 큰 숫자로 입력해 주세요." };
  const when = [date && dateLong(date), start && `${start} 이후 시작하는`].filter(Boolean).join(" ");
  const what = [region, genre || "공연"].filter(Boolean).join(" ");
  const parts = [[when, what].filter(Boolean).join(" ")];
  if (home) parts.push(`${homeBy}까지 ${home} 도착`);
  if (budget) parts.push(`${Number(budget).toLocaleString("ko-KR")}원 이하`);
  return { text: parts.join(", ") };
}

function setHelperOpen(open) {
  $("#helper").hidden = !open;
  $("#helper-toggle").setAttribute("aria-expanded", String(open));
}

// ── 화면 전환 ─────────────────────────────────────────────────────────────
function switchView(view, { scrollTo, session } = {}) {
  const sheet = $("#plan-sheet");
  sheetOpener = null;
  if (sheet.open) sheet.close();
  $$(".view").forEach((v) => v.classList.toggle("hidden", v.id !== `view-${view}`));
  $$(".nav-link[data-view]").forEach((b) => {
    if (b.dataset.view === view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  if (view === "plans") loadPlans();
  if (view === "logs") loadSessions(session);
  if (scrollTo) scrollToEl($(scrollTo));
  else window.scrollTo({ top: 0 });
}

// ── 내 관람 계획 ─────────────────────────────────────────────────────────
async function loadPlans() {
  const box = $("#plans");
  box.replaceChildren(h("p", { class: "muted" }, "불러오는 중…"));
  let plans;
  try {
    plans = (await api("GET", "/api/plans")).plans;
  } catch (err) {
    box.replaceChildren(h("p", { class: "notice error", role: "alert" }, errorText(err)));
    return;
  }
  if (!plans.length) {
    box.replaceChildren(h("div", { class: "empty-plans" },
      h("p", null, "저장한 계획이 없어요. 추천 공연의 관람 계획에서 [내 관람 계획에 저장]을 누르면 여기에 모여요."),
      h("button", { type: "button", class: "btn-primary", onclick: () => switchView("search") }, "공연 찾으러 가기")));
    return;
  }
  const titles = new Map(plans.map((p) => [p.id, p.title]));
  const byDate = new Map();
  [...plans].sort((a, b) => `${a.date} ${a.start_time}`.localeCompare(`${b.date} ${b.start_time}`)).forEach((p) => {
    if (!byDate.has(p.date)) byDate.set(p.date, []);
    byDate.get(p.date).push(p);
  });
  box.replaceChildren(...[...byDate].map(([date, list]) => h("section", { class: "agenda-day", "aria-label": dateLong(date) },
    h("h2", { class: "agenda-date" }, dateLong(date)),
    list.map((p) => planRow(p, titles)))));
}

function planRow(p, titles) {
  const overlapNames = (p.overlaps || []).map((id) => titles.get(id)).filter(Boolean);
  const ticket = safeUrl(p.ticket_url);
  const row = h("article", { class: `agenda-row${overlapNames.length ? " has-overlap" : ""}` },
    h("p", { class: "agenda-time" }, p.end_time ? `${p.start_time}–${p.end_time}` : `${p.start_time} 시작`),
    h("div", null,
      h("p", { class: "agenda-title" }, p.title),
      h("p", { class: "agenda-meta" }, [p.venue_name, p.price != null ? won(p.price) : null].filter(Boolean).join(", ")),
      p.memo ? h("p", { class: "agenda-meta" }, p.memo) : null,
      overlapNames.length ? h("span", { class: "overlap-tag" }, `시간 겹침: ${overlapNames.join(", ")}`) : null),
    h("div", { class: "row-actions" },
      ticket ? h("a", { class: "btn-secondary", href: ticket, target: "_blank", rel: "noopener noreferrer" }, "예매처") : null,
      h("button", { type: "button", "aria-label": `${p.title} 수정`, onclick: () => editPlan(row, p) }, "수정"),
      h("button", { type: "button", "aria-label": `${p.title} 삭제`, onclick: () => deletePlan(p) }, "삭제")));
  return row;
}

function editPlan(row, p) {
  const field = (type, value, label) => h("input", { type, value: value || "", "aria-label": label });
  const date = field("date", p.date, "날짜");
  const start = field("time", p.start_time, "시작 시각");
  const end = field("time", p.end_time, "종료 시각");
  const memo = field("text", p.memo, "메모");
  memo.placeholder = "메모";
  memo.maxLength = 200;
  const error = h("p", { class: "field-error", role: "alert", hidden: true });
  const save = h("button", { type: "button" }, "저장");
  const cancel = h("button", { type: "button", onclick: loadPlans }, "취소");
  row.className = "agenda-row editing";
  row.replaceChildren(h("p", { class: "agenda-title" }, p.title), h("div", { class: "edit-fields" }, date, start, end, memo),
    error, h("div", { class: "row-actions" }, save, cancel));
  save.addEventListener("click", async () => {
    try {
      await api("PATCH", `/api/plans/${p.id}`, { date: date.value, start_time: start.value, end_time: end.value || null, memo: memo.value });
      loadPlans();
    } catch (err) {
      error.textContent = errorText(err);
      error.hidden = false;
    }
  });
  date.focus();
}

async function deletePlan(p) {
  if (!confirm(`‘${p.title}’ 계획을 삭제할까요?`)) return;
  try {
    await api("DELETE", `/api/plans/${p.id}`);
  } catch (err) {
    $("#plans").prepend(h("p", { class: "notice error", role: "alert" }, errorText(err)));
    return;
  }
  loadPlans();
}

// ── 실행 기록 ─────────────────────────────────────────────────────────────
let currentLogSession = null;
async function loadSessions(selectId) {
  const ul = $("#sessions");
  ul.replaceChildren(h("li", { class: "muted" }, "불러오는 중…"));
  let sessions;
  try {
    ({ sessions } = await api("GET", "/api/logs"));
  } catch (err) {
    ul.replaceChildren(h("li", { class: "notice error", role: "alert" }, errorText(err)));
    return;
  }
  if (!sessions.length) {
    ul.replaceChildren(h("li", { class: "muted" }, "아직 실행 기록이 없어요."));
    return;
  }
  ul.replaceChildren(...sessions.map((s) => h("li", null,
    h("button", { type: "button", "data-sid": s.session_id, onclick: () => loadEvents(s.session_id) },
      s.session_id, h("span", { class: "s-meta" }, `실행 ${s.runs}회, 이벤트 ${s.events}개, ${formatTs(s.last_ts)}`)))));
  if (selectId && sessions.some((s) => s.session_id === selectId)) loadEvents(selectId);
}

async function loadEvents(sid) {
  currentLogSession = sid;
  $$("#sessions button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.sid === sid)));
  $("#log-title").textContent = `이벤트 (${sid})`;
  $("#delete-log").classList.remove("hidden");
  const ol = $("#events");
  ol.replaceChildren(h("li", { class: "muted" }, "불러오는 중…"));
  try {
    const { events } = await api("GET", `/api/logs/${encodeURIComponent(sid)}`);
    ol.replaceChildren(...events.map((ev) => h("li", null, h("details", null,
      h("summary", null, `#${ev.seq} ${ev.type}${ev.node ? `, ${ev.node}` : ""}, ${String(ev.ts).slice(11, 19)}`),
      h("pre", null, JSON.stringify(ev.payload, null, 2))))));
  } catch (err) {
    ol.replaceChildren(h("li", { class: "notice error", role: "alert" }, errorText(err)));
  }
}

async function deleteLog() {
  if (!currentLogSession || !confirm("이 세션의 실행 기록을 삭제할까요? 되돌릴 수 없어요.")) return;
  try {
    await api("DELETE", `/api/logs/${encodeURIComponent(currentLogSession)}`);
  } catch (err) {
    $("#events").prepend(h("li", { class: "notice error", role: "alert" }, errorText(err)));
    return;
  }
  $("#events").replaceChildren(h("li", { class: "muted" }, "삭제했어요. 다른 세션을 골라 보세요."));
  $("#delete-log").classList.add("hidden");
  loadSessions();
}

// ── 서비스 상태 ───────────────────────────────────────────────────────────
async function loadHealth() {
  if (DEMO) {
    // 예시 화면은 저장된 결과를 보여 줄 뿐이라 키 안내 대신, 무엇을 입력해도 같은 결과가 나온다는 점을 알린다
    const banner = $("#health-banner");
    banner.textContent = "예시 화면이에요. 실제 API로 받아 저장해 둔 검색 결과를 보여 드려서, 어떤 문장을 입력해도 같은 결과가 나와요.";
    banner.classList.add("is-demo");
    banner.classList.remove("hidden");
    return;
  }
  try {
    const health = await api("GET", "/api/health");
    const missing = Object.entries(health.services || {}).filter(([, ok]) => !ok).map(([k]) => SERVICE_LABEL[k] || k);
    if (missing.length) {
      const banner = $("#health-banner");
      banner.textContent = `설정이 필요한 서비스: ${missing.join(", ")}. .env에 키를 넣으면 해당 기능이 동작해요. 날씨가 빠져도 추천은 정상으로 나와요.`;
      banner.classList.remove("hidden");
    }
  } catch (_) { /* 상태 확인 실패는 화면을 막지 않는다 */ }
}

// ── demo-data.js 호환 (DEMO_AUTOPLAY(renderReply, addMessage)) ────────────
function addMessage(role, text) {
  if (role === "user") {
    state.exchanges.push({ request: text, fresh: true, response: null, error: null, pending: false, startedAt: Date.now() });
  }
  return h("div");
}

function renderReply(res) {
  let ex = lastExchange();
  if (!ex || ex.response || ex.error) {
    ex = { request: "", fresh: false, response: null, error: null, pending: false, startedAt: Date.now() };
    state.exchanges.push(ex);
  }
  ex.response = res;
  ex.pending = false;
  absorb(res);
  render();
}

// ── 이벤트 연결 ───────────────────────────────────────────────────────────
function init() {
  const searchInput = $("#search-input");
  $("#search-form").addEventListener("submit", (e) => { e.preventDefault(); submitHero(); });
  searchInput.addEventListener("keydown", (e) => {
    // 한글 조합 중 Enter(isComposing, Safari는 keyCode 229)는 글자 확정이므로 보내지 않는다
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      submitHero();
    }
  });
  searchInput.addEventListener("input", () => { autoGrow(searchInput); resetHint(); });

  $$(".chip-example").forEach((chip) => chip.addEventListener("click", () => {
    searchInput.value = `${chip.dataset.fill} `;
    autoGrow(searchInput);
    searchInput.focus();
    searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    hint("날짜, 시작 시각, 도착할 곳을 덧붙이면 더 정확해요. 그대로 찾아도 돼요.");
  }));

  $("#helper-toggle").addEventListener("click", () => {
    const open = $("#helper").hidden;
    setHelperOpen(open);
    if (open) $("#h-date").focus();
  });
  $("#h-date").min = todayISO();
  $$("#helper input, #helper select").forEach((el) => el.addEventListener("input", () => { $("#helper-error").hidden = true; }));
  $("#helper-apply").addEventListener("click", () => {
    const result = composeFromHelper();
    const error = $("#helper-error");
    if (result.error) {
      error.textContent = result.error;
      error.hidden = false;
      return;
    }
    error.hidden = true;
    searchInput.value = result.text;
    autoGrow(searchInput);
    setHelperOpen(false);
    searchInput.focus();
    hint("문장을 확인한 뒤 [공연 찾기]를 눌러 주세요.");
  });

  $("#followup-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#followup-input");
    if (state.busy) return;
    if (!input.value.trim()) { input.focus(); return; }
    send(input.value, { fresh: false });
    input.value = "";
  });
  $("#followup-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.isComposing || e.keyCode === 229)) e.preventDefault();
  });
  $("#reset-btn").addEventListener("click", () => {
    resetConversation();
    render();
    window.scrollTo({ top: 0 });
    searchInput.focus();
  });

  $$("[data-view]").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
  $("[data-guide]").addEventListener("click", () => switchView("search", { scrollTo: "#how" }));
  $("#reload-plans").addEventListener("click", loadPlans);
  $("#delete-log").addEventListener("click", deleteLog);

  const sheet = $("#plan-sheet");
  $(".sheet-close").addEventListener("click", () => sheet.close());
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });  // 배경을 누르면 닫는다
  sheet.addEventListener("close", () => {
    if (sheetOpener && document.contains(sheetOpener)) sheetOpener.focus({ preventScroll: true });
    sheetOpener = null;
  });
  WIDE.addEventListener("change", () => {
    if (WIDE.matches && sheet.open) sheet.close();
    state.renderedVersion = -1;  // 패널 유무가 바뀌므로 보드를 다시 그린다
    renderBoard();
  });

  loadHealth();
  render();
  if (DEMO && window.DEMO_AUTOPLAY) window.DEMO_AUTOPLAY(renderReply, addMessage);
}

init();
