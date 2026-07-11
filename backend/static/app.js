const API = "/api";
const TOKEN_KEY = "vam_token";

const $ = (sel, root = document) => root.querySelector(sel);

const state = {
  token: localStorage.getItem(TOKEN_KEY) || "",
  user: null,
  scenarioId: null,
  jobId: null,
  copyUnlocked: false,
  copyUnlockCost: 5,
  produceCost: 100,
  discussCost: 10,
  scenarioCost: 15,
  refineCost: 35,
  pricing: null,
  lastScenario: null,
  productAnalysis: null,
  productImageUrl: null,
  catalog: null,
  analyzeCost: 10,
  copyCost: 12,
  visualPerPlatform: 15,
  activeStudio: "scenario",
};

function setError(el, msg) {
  if (!el) return;
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
}

function mediaUrl(path) {
  if (!path) return "";
  const sep = path.includes("?") ? "&" : "?";
  const token = state.token ? `access_token=${encodeURIComponent(state.token)}&` : "";
  return `${path}${sep}${token}t=${Date.now()}`;
}

function setWorking(on, text) {
  const overlay = $("#workOverlay");
  if (!overlay) return;
  overlay.hidden = !on;
  if (text) {
    const label = $("#workOverlayText");
    if (label) label.textContent = text;
  }
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollJob(jobId, { label } = {}) {
  const terminal = new Set(["completed", "failed"]);
  for (let i = 0; i < 90; i++) {
    const job = await api(`/jobs/${jobId}`);
    renderJob(job, { soft: true });
    const statusLabel = label || "Üretiliyor";
    setWorking(true, `${statusLabel}… (${job.status})`);
    if (terminal.has(job.status)) {
      if (job.status === "failed") {
        throw new Error(job.error_message || "Üretim başarısız");
      }
      return job;
    }
    await sleep(2000);
  }
  throw new Error("Üretim zaman aşımı — işler sayfasından tekrar kontrol edin");
}

async function loadHistory() {
  const box = $("#historyList");
  if (!box) return;
  try {
    const rows = await api("/scenarios");
    if (!rows.length) {
      box.innerHTML = `<p class="lede tight">Henüz senaryo yok — ilk brief’ini yaz.</p>`;
      return;
    }
    box.innerHTML = rows
      .slice(0, 12)
      .map((s) => {
        const title = escapeHtml(s.title || s.professional_script?.title || `Senaryo #${s.id}`);
        const meta = escapeHtml(
          `${(s.language || "tr").toUpperCase()} · ${s.duration_seconds || "—"}s · ${s.status || ""}`
        );
        return `<button type="button" class="history-item" data-id="${s.id}"><strong>${title}</strong><span>${meta}</span></button>`;
      })
      .join("");
    box.querySelectorAll(".history-item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        setWorking(true, "Senaryo yükleniyor…");
        try {
          const scenario = await api(`/scenarios/${btn.dataset.id}`);
          renderScenario(scenario);
          const jobs = await api("/jobs");
          const related = (jobs || []).find((j) => j.scenario_id === scenario.id);
          if (related) renderJob(related);
        } catch (err) {
          setError($("#scenarioError"), err.message);
        } finally {
          setWorking(false);
        }
      });
    });
  } catch {
    box.innerHTML = `<p class="lede tight">Geçmiş yüklenemedi.</p>`;
  }
}

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail : JSON.stringify(detail || data);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data;
}

function showAuth() {
  $("#authPanel").hidden = false;
  $("#studioPanel").hidden = true;
  $("#userBar").hidden = true;
}

function showStudio() {
  $("#authPanel").hidden = true;
  $("#studioPanel").hidden = false;
  $("#userBar").hidden = false;
  switchStudioPane(state.activeStudio || "scenario");
}

async function refreshMe() {
  state.user = await api("/auth/me");
  const chip = $("#creditChip");
  if (state.user.unlimited_credits) {
    chip.textContent = "∞ kredi";
  } else {
    chip.textContent = `${state.user.credits} kredi`;
  }
  const adminLink = $("#adminLink");
  if (adminLink) {
    adminLink.hidden = !state.user.is_admin;
  }
  if (state.user.preferred_language) {
    const lang = $("#language");
    if ([...lang.options].some((o) => o.value === state.user.preferred_language)) {
      lang.value = state.user.preferred_language;
    }
  }
}

async function loadPricing() {
  try {
    const p = await api("/credits/pricing", { auth: false });
    state.pricing = p;
    state.scenarioCost = p.scenario;
    state.discussCost = p.discuss;
    state.refineCost = p.refine;
    state.copyUnlockCost = p.copy_unlock;
    const dur = Number($("#scenarioForm")?.duration_seconds?.value || 30);
    state.produceCost = Number(p.produce_by_duration?.[String(dur)] || p.produce_by_duration?.["30"] || 100);
    updateCostLabels();
  } catch {
    /* fiyat tablosu opsiyonel */
  }
}

function produceCostForDuration(seconds) {
  const key = String(seconds);
  const map = state.pricing?.produce_by_duration || {};
  if (map[key] != null) return map[key];
  // En yakın basamak
  const keys = Object.keys(map).map(Number).sort((a, b) => a - b);
  if (!keys.length) return state.produceCost;
  let best = keys[0];
  for (const k of keys) {
    if (seconds >= k) best = k;
  }
  return map[String(best)] || state.produceCost;
}

function updateCostLabels() {
  const convertBtn = $("#convertBtn");
  if (convertBtn && !convertBtn.disabled) {
    convertBtn.textContent = `Reklam senaryosu yaz · ${state.scenarioCost} kredi`;
  }
  const discussBtn = $("#discussBtn");
  if (discussBtn && !discussBtn.disabled) {
    discussBtn.textContent = `Uygula · ${state.discussCost} kredi`;
  }
  const produceBtn = $("#produceBtn");
  if (produceBtn && !produceBtn.disabled) {
    produceBtn.textContent = `Görsel üret · ${state.produceCost} kredi`;
  }
  const refineBtn = $("#refineBtn");
  if (refineBtn && !refineBtn.disabled) {
    refineBtn.textContent = `Revize et · ${state.refineCost} kredi`;
  }
  const unlockBtn = $("#unlockCopyBtn");
  if (unlockBtn && !unlockBtn.hidden && !state.copyUnlocked) {
    unlockBtn.textContent = `Kopyalamayı aç · ${state.copyUnlockCost} kredi`;
  }
}

async function boot() {
  if (!state.token) {
    showAuth();
    await loadPricing();
    return;
  }
  try {
    await refreshMe();
    showStudio();
    await loadPricing();
    await loadCreativeCatalog();
    await loadHistory();
  } catch {
    state.token = "";
    localStorage.removeItem(TOKEN_KEY);
    showAuth();
    await loadPricing();
  }
}

// Auth tabs only
document.querySelectorAll(".auth-panel .tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".auth-panel .tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    $("#loginForm").hidden = tab !== "login";
    $("#registerForm").hidden = tab !== "register";
    setError($("#authError"), "");
  });
});

document.querySelectorAll(".toggle-pass").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = btn.parentElement?.querySelector("input");
    if (!input) return;
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Gizle" : "Göster";
    btn.setAttribute("aria-label", show ? "Şifreyi gizle" : "Şifreyi göster");
  });
});

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#authError"), "");
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/login", {
      method: "POST",
      auth: false,
      body: { email: fd.get("email"), password: fd.get("password") },
    });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY, state.token);
    await refreshMe();
    showStudio();
    await loadHistory();
    await loadCreativeCatalog();
  } catch (err) {
    setError($("#authError"), err.message);
  }
});

$("#registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#authError"), "");
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/register", {
      method: "POST",
      auth: false,
      body: {
        email: fd.get("email"),
        password: fd.get("password"),
        display_name: fd.get("display_name") || null,
        preferred_language: "tr",
      },
    });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY, state.token);
    await refreshMe();
    showStudio();
    await loadHistory();
    await loadCreativeCatalog();
  } catch (err) {
    setError($("#authError"), err.message);
  }
});

$("#logoutBtn").addEventListener("click", () => {
  state.token = "";
  state.user = null;
  localStorage.removeItem(TOKEN_KEY);
  showAuth();
});

// Settings
const dialog = $("#settingsDialog");
$("#settingsBtn").addEventListener("click", async () => {
  setError($("#settingsError"), "");
  try {
    const keys = await api("/api-keys");
    const box = $("#savedKeys");
    if (!keys.length) {
      box.textContent = "Kayıtlı anahtar yok.";
    } else {
      box.innerHTML = keys
        .map((k) => `<div>${k.provider}: <code>${k.key_hint}</code></div>`)
        .join("");
    }
  } catch (err) {
    setError($("#settingsError"), err.message);
  }
  dialog.showModal();
});

$("#closeSettingsBtn").addEventListener("click", () => dialog.close());

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#settingsError"), "");
  const fd = new FormData(e.target);
  const openrouter = String(fd.get("openrouter") || "").trim();
  const elevenlabs = String(fd.get("elevenlabs") || "").trim();
  try {
    if (openrouter) {
      await api("/api-keys", {
        method: "PUT",
        body: { provider: "openrouter", api_key: openrouter },
      });
    }
    if (elevenlabs) {
      await api("/api-keys", {
        method: "PUT",
        body: { provider: "elevenlabs", api_key: elevenlabs },
      });
    }
    e.target.reset();
    const keys = await api("/api-keys");
    $("#savedKeys").innerHTML = keys
      .map((k) => `<div>${k.provider}: <code>${k.key_hint}</code></div>`)
      .join("") || "Kayıtlı anahtar yok.";
  } catch (err) {
    setError($("#settingsError"), err.message);
  }
});

function renderConversionScore(script) {
  const box = $("#conversionScore");
  const score = script.conversion_score;
  if (!box) return;
  if (!score || typeof score !== "object") {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  const total = Number(score.total ?? 0);
  $("#scoreValue").textContent = String(total);
  const ring = $("#scoreRing");
  if (ring) {
    ring.style.setProperty("--score", String(Math.max(0, Math.min(100, total))));
    ring.classList.toggle("is-high", total >= 75);
    ring.classList.toggle("is-mid", total >= 50 && total < 75);
    ring.classList.toggle("is-low", total < 50);
  }
  $("#scoreBreakdown").textContent = [
    `Hook ${score.hook_strength ?? "—"}`,
    `Teklif ${score.offer_clarity ?? "—"}`,
    `CTA ${score.cta_clarity ?? "—"}`,
    score.note ? `· ${score.note}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function renderHookVariants(script) {
  const wrap = $("#hookVariants");
  const list = $("#hookList");
  const emptyHint = $("#hookEmptyHint");
  if (!wrap || !list) return;
  const variants = Array.isArray(script.hook_variants) ? script.hook_variants : [];
  if (!variants.length) {
    list.innerHTML = "";
    if (emptyHint) emptyHint.hidden = false;
    return;
  }
  if (emptyHint) emptyHint.hidden = true;
  const selected = script.hook || (variants[0] && variants[0].text) || "";
  list.innerHTML = variants
    .map((v, i) => {
      const id = escapeHtml(String(v.id || String.fromCharCode(65 + i)));
      const text = escapeHtml(String(v.text || ""));
      const angle = escapeHtml(String(v.angle || ""));
      const active = String(v.text || "") === selected ? " is-active" : "";
      return `<button type="button" class="hook-chip${active}" data-index="${i}">
        <span class="hook-chip-id">${id}</span>
        <span class="hook-chip-text">${text}</span>
        ${angle ? `<span class="hook-chip-angle">${angle}</span>` : ""}
      </button>`;
    })
    .join("");
}

const RESULT_STEP_HINTS = {
  1: "Kampanyanın özeti ve skoru.",
  2: "İlk 3 saniye için kancayı seç.",
  3: "Seslendirme ve sahneleri oku.",
  4: "İstersen kısa bir revize notu bırak.",
  5: "Hazırsan senaryoyu kopyala.",
};

function switchResultStep(step) {
  const n = Number(step) || 1;
  document.querySelectorAll(".result-step").forEach((btn) => {
    const s = Number(btn.dataset.rstep);
    const active = s === n;
    btn.classList.toggle("is-active", active);
    btn.classList.toggle("is-done", s < n);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll(".result-pane").forEach((pane) => {
    const on = Number(pane.dataset.rpane) === n;
    pane.hidden = !on;
    pane.classList.toggle("is-active", on);
  });
  const hint = $("#resultStepHint");
  if (hint) hint.textContent = RESULT_STEP_HINTS[n] || "";
}

async function selectHookVariant(text) {
  if (!state.scenarioId || !text) return;
  setError($("#hookError"), "");
  try {
    const scenario = await api(`/scenarios/${state.scenarioId}/select-hook`, {
      method: "POST",
      body: { hook: text },
    });
    renderScenario(scenario);
  } catch (err) {
    setError($("#hookError"), err.message);
  }
}

const BRIEF_PRESETS = {
  beauty: {
    title: "Cilt bakımı — ilk sipariş",
    style: "ugc",
    offer: "14 günlük cilt bakımı seti — ilk siparişte %20",
    pain_point: "Pahalı kremler işe yaramıyor, cilt aynı kalıyor",
    desired_action: "dm",
    audience: "25–40 yaş, cilt bakımı arayan kadınlar",
    raw_input: "Doğal ton, abartısız vaat. Önce/sonra yorumları var. Rakip: eczane markaları.",
  },
  saas: {
    title: "Ajans otomasyonu — demo",
    style: "pas",
    offer: "14 gün ücretsiz demo — reklam raporu otomatik",
    pain_point: "Raporlara saatler gidiyor, müşteri bekliyor",
    desired_action: "lead_form",
    audience: "Dijital ajans sahipleri ve medya planlamacıları",
    raw_input: "B2B, net fayda. Jargon az. Kanıt: 120+ ajans. CTA form.",
  },
  food: {
    title: "Restoran — bugün rezervasyon",
    style: "offer-urgency",
    offer: "Bugün rezervasyona tatlı ikramı",
    pain_point: "Hafta sonu yer bulamamak, sırada beklemek",
    desired_action: "whatsapp",
    audience: "Şehir merkezinde yemek arayan 25–45 yaş",
    raw_input: "İştah açıcı görseller, sıcak atmosfer. Stok/yer sınırlı vurgusu gerçekçi olsun.",
  },
  fitness: {
    title: "Online fitness — 7 gün deneme",
    style: "before-after",
    offer: "7 gün ücretsiz deneme + antrenör planı",
    pain_point: "Spor salonuna gitmeye zaman yok, motivasyon düşüyor",
    desired_action: "link_click",
    audience: "Evde spor yapmak isteyen yoğun çalışanlar",
    raw_input: "Enerjik ama baskısız. Dönüşüm hikayesi. Link bio’da.",
  },
  ecommerce: {
    title: "E-ticaret — ücretsiz kargo",
    style: "social-proof",
    offer: "Ücretsiz kargo + 2. üründe %15",
    pain_point: "Kargo ücreti sepeti terk ettiriyor",
    desired_action: "buy",
    audience: "Online alışveriş yapan 20–40 yaş",
    raw_input: "Sosyal kanıt: 4.8 puan / 2B+ satış. Net fiyat. Sahte aciliyet yok.",
  },
};

function applyBriefPreset(key) {
  const p = BRIEF_PRESETS[key];
  if (!p) return;
  const form = $("#scenarioForm");
  if (!form) return;
  if (form.title) form.title.value = p.title;
  if (form.style) form.style.value = p.style;
  if (form.offer) form.offer.value = p.offer;
  if (form.pain_point) form.pain_point.value = p.pain_point;
  if (form.desired_action) form.desired_action.value = p.desired_action;
  if (form.audience) form.audience.value = p.audience;
  if (form.raw_input) form.raw_input.value = p.raw_input;
  setError($("#scenarioError"), "");
}

$("#briefPresets")?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-preset]");
  if (!btn) return;
  document.querySelectorAll("#briefPresets .preset-chip").forEach((b) => b.classList.remove("is-active"));
  btn.classList.add("is-active");
  applyBriefPreset(btn.getAttribute("data-preset"));
});

function renderScenario(scenario) {
  state.scenarioId = scenario.id;
  state.lastScenario = scenario;
  state.copyUnlocked = !!scenario.copy_unlocked || !!(state.user && state.user.unlimited_credits);
  state.copyUnlockCost = scenario.copy_unlock_cost || state.copyUnlockCost || 5;
  state.produceCost = scenario.produce_credit_cost || state.produceCost;
  state.discussCost = scenario.discuss_credit_cost || state.discussCost;

  const script = scenario.professional_script || {};
  $("#resultEmpty").hidden = true;
  $("#resultContent").hidden = false;
  $("#resultContent").classList.toggle("is-locked", !state.copyUnlocked);
  $("#resultTitle").textContent = script.title || scenario.title || "Reklam Senaryosu";
  $("#resultHook").textContent = script.hook || "";
  $("#resultMeta").textContent = `${(scenario.language || "tr").toUpperCase()} · ${scenario.duration_seconds || "—"}s · ${scenario.style || "—"}`;
  $("#resultVoice").textContent = script.voiceover_full || "";
  $("#resultMusic").textContent = script.music_mood || "—";
  $("#resultCta").textContent = script.cta || "—";
  $("#resultId").textContent = scenario.id;
  setError($("#produceError"), "");
  setError($("#copyError"), "");

  renderConversionScore(script);
  renderHookVariants(script);
  switchResultStep(1);

  const unlockBtn = $("#unlockCopyBtn");
  const copyBtn = $("#copyScenarioBtn");
  const hint = $("#copyHint");
  if (state.copyUnlocked) {
    unlockBtn.hidden = true;
    copyBtn.hidden = false;
    if (hint) hint.textContent = "Hazırsan senaryoyu panoya al.";
  } else {
    unlockBtn.hidden = false;
    unlockBtn.textContent = `Kopyalamayı aç · ${state.copyUnlockCost} kredi`;
    copyBtn.hidden = true;
    if (hint) hint.textContent = "Kilitli önizleme — kopyalamak için bir kez aç.";
  }

  const badge = $("#resultBadge");
  if (script.mock) {
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }

  const list = $("#resultScenes");
  list.innerHTML = "";
  (script.scenes || []).forEach((scene) => {
    const li = document.createElement("li");
    const role = scene.role ? ` · ${escapeHtml(String(scene.role).toUpperCase())}` : "";
    const cut = scene.cut ? ` · ${escapeHtml(scene.cut)}` : "";
    li.innerHTML = `
      <div class="scene-time">${escapeHtml(scene.timecode || "")}${role}${cut}</div>
      <p class="scene-visual">${escapeHtml(scene.visual || "")}</p>
      <p class="scene-narration">${escapeHtml(scene.narration || "")}</p>
      ${scene.on_screen_text ? `<p class="scene-visual">Ekran: ${escapeHtml(scene.on_screen_text)}</p>` : ""}
    `;
    list.appendChild(li);
  });

  renderDiscussion(scenario.discussion || []);
  updateCostLabels();
  switchStudioPane("scenario");
}

function renderDiscussion(messages) {
  const thread = $("#discussThread");
  if (!thread) return;
  if (!messages.length) {
    thread.innerHTML = `<div class="discuss-bubble director"><span class="discuss-role">İpucu</span>Örn. “Hook daha sert olsun” veya “CTA’yı DM at yap”.</div>`;
    return;
  }
  thread.innerHTML = messages
    .map((m) => {
      const role = m.role === "user" ? "user" : "director";
      const label = role === "user" ? "Sen" : "Yönetmen";
      return `<div class="discuss-bubble ${role}"><span class="discuss-role">${label}</span>${escapeHtml(m.content || "")}</div>`;
    })
    .join("");
  thread.scrollTop = thread.scrollHeight;
}

async function unlockAndCopyFlow() {
  setError($("#copyError"), "");
  if (!state.scenarioId) return;
  const btn = $("#unlockCopyBtn");
  btn.disabled = true;
  try {
    const scenario = await api(`/scenarios/${state.scenarioId}/unlock-copy`, { method: "POST" });
    renderScenario(scenario);
    await refreshMe();
  } catch (err) {
    setError($("#copyError"), err.message);
  } finally {
    btn.disabled = false;
  }
}

async function copyScenarioText() {
  setError($("#copyError"), "");
  if (!state.scenarioId) return;
  try {
    if (!state.copyUnlocked) {
      await unlockAndCopyFlow();
      if (!state.copyUnlocked) return;
    }
    const data = await api(`/scenarios/${state.scenarioId}/copy-text`);
    await navigator.clipboard.writeText(data.text || "");
    const btn = $("#copyScenarioBtn");
    const prev = btn.textContent;
    btn.textContent = "Kopyalandı ✓";
    setTimeout(() => {
      btn.textContent = prev;
    }, 1600);
  } catch (err) {
    setError($("#copyError"), err.message);
  }
}

function renderJob(job, { soft = false } = {}) {
  state.jobId = job.id;
  const player = $("#playerSection");
  if (!player) return;
  player.hidden = false;
  if ($("#jobMeta")) $("#jobMeta").textContent = `İş #${job.id} · rev ${job.revision} · ${job.status}`;
  if ($("#jobBadge")) $("#jobBadge").hidden = !job.is_mock;

  const video = $("#videoPlayer");
  const frame = $("#previewFrame");
  const audio = $("#audioPlayer");
  const dl = $("#downloadVideo");

  if (job.video_url && String(job.video_url).endsWith(".mp4")) {
    video.hidden = false;
    frame.hidden = true;
    video.src = mediaUrl(job.video_url);
    video.load();
    if (dl) {
      dl.hidden = false;
      dl.href = mediaUrl(job.video_url);
    }
  } else if (job.preview_url) {
    video.hidden = true;
    frame.hidden = false;
    frame.src = mediaUrl(job.preview_url);
    if (dl) dl.hidden = true;
  }

  if (job.audio_url) {
    audio.src = mediaUrl(job.audio_url);
  }

  const critiqueBox = $("#critiqueBox");
  if (critiqueBox) {
    const c = job.critique;
    if (c) {
      critiqueBox.hidden = false;
      const list = (arr) =>
        (arr || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("") || "<li>—</li>";
      critiqueBox.innerHTML = `
        <h4>${escapeHtml(c.title || "Eleştiri Raporu")} · <strong>${escapeHtml(c.verdict || "")}</strong></h4>
        <div><strong>Güçlü</strong><ul>${list(c.strengths)}</ul></div>
        <div><strong>Risk</strong><ul>${list(c.risks)}</ul></div>
        <div><strong>Öneri</strong><ul>${list(c.suggestions)}</ul></div>
        <p>${escapeHtml(c.how_to_reply || "")}</p>
      `;
    } else {
      critiqueBox.hidden = true;
      critiqueBox.innerHTML = "";
    }
  }

  const thumbs = $("#sceneThumbs");
  if (thumbs) {
    const imgs = job.scene_images || [];
    thumbs.innerHTML = imgs
      .map(
        (s) =>
          `<img src="${escapeHtml(mediaUrl(s.url))}" alt="Sahne ${s.index}" title="Sahne ${s.index}" />`
      )
      .join("");
  }

  if (!soft && job.script_snapshot) {
    const base = state.lastScenario || {};
    renderScenario({
      id: job.scenario_id,
      language: base.language || "tr",
      duration_seconds: base.duration_seconds || 0,
      style: base.style || "—",
      title: job.script_snapshot.title,
      professional_script: job.script_snapshot,
      copy_unlocked: state.copyUnlocked || !!(state.user && state.user.unlimited_credits),
      copy_unlock_cost: state.copyUnlockCost,
      discussion: base.discussion || [],
      critique: base.critique || null,
    });
    $("#resultMeta").textContent = `Senaryo #${job.scenario_id} · rev ${job.revision}`;
  }

  const revBox = $("#revisionList");
  const revs = job.revisions || [];
  if (!revs.length) {
    revBox.innerHTML = `<div class="revision-item">Henüz geliştirme yok.</div>`;
  } else {
    revBox.innerHTML = revs
      .map((r) => {
        const fields = Array.isArray(r.changed_fields)
          ? r.changed_fields.join(", ")
          : r.changed_fields;
        return `<div class="revision-item"><strong>Rev ${r.revision}</strong> — ${escapeHtml(r.instruction)}<br/><span>${escapeHtml(fields || "")}</span></div>`;
      })
      .join("");
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

$("#scenarioForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#scenarioError"), "");
  const btn = $("#convertBtn");
  btn.disabled = true;
  btn.textContent = "Yazılıyor…";
  setWorking(true, "AI1 reklam senaryosu yazıyor…");
  const fd = new FormData(e.target);
  try {
    const scenario = await api("/scenarios/professionalize", {
      method: "POST",
      body: {
        language: fd.get("language"),
        title: fd.get("title") || null,
        duration_seconds: Number(fd.get("duration_seconds")),
        style: fd.get("style"),
        audience: fd.get("audience") || null,
        offer: fd.get("offer"),
        pain_point: fd.get("pain_point"),
        desired_action: fd.get("desired_action"),
        raw_input: fd.get("raw_input"),
      },
    });
    renderScenario(scenario);
    await refreshMe();
    await loadHistory();
  } catch (err) {
    setError($("#scenarioError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `Reklam senaryosu yaz · ${state.scenarioCost} kredi`;
    setWorking(false);
  }
});

$("#hookList")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".hook-chip");
  if (!btn || !state.lastScenario) return;
  const idx = Number(btn.getAttribute("data-index"));
  const variants = state.lastScenario.professional_script?.hook_variants || [];
  const text = variants[idx]?.text;
  if (text) selectHookVariant(text);
});

$("#resultSteps")?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-rstep]");
  if (!btn) return;
  switchResultStep(btn.dataset.rstep);
});

document.querySelectorAll(".result-next").forEach((btn) => {
  btn.addEventListener("click", () => switchResultStep(btn.dataset.goto));
});

$("#unlockCopyBtn").addEventListener("click", () => {
  unlockAndCopyFlow();
});

$("#copyScenarioBtn").addEventListener("click", () => {
  copyScenarioText();
});

$("#discussBtn").addEventListener("click", async () => {
  setError($("#discussError"), "");
  if (!state.scenarioId) {
    setError($("#discussError"), "Önce senaryo üretin");
    return;
  }
  const message = ($("#discussInput").value || "").trim();
  if (message.length < 2) {
    setError($("#discussError"), "Kısa bir not yaz");
    return;
  }
  const btn = $("#discussBtn");
  btn.disabled = true;
  btn.textContent = "Uygulanıyor…";
  setWorking(true, "Yönetmen senaryoyu güncelliyor…");
  try {
    const scenario = await api(`/scenarios/${state.scenarioId}/discuss`, {
      method: "POST",
      body: { message },
    });
    $("#discussInput").value = "";
    renderScenario(scenario);
    await refreshMe();
  } catch (err) {
    setError($("#discussError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `Uygula · ${state.discussCost} kredi`;
    setWorking(false);
  }
});

$("#produceBtn")?.addEventListener("click", async () => {
  setError($("#produceError"), "");
  if (!state.scenarioId) {
    setError($("#produceError"), "Önce senaryo üretin");
    return;
  }
  const btn = $("#produceBtn");
  btn.disabled = true;
  btn.textContent = "Kuyruğa alındı…";
  setWorking(true, "AI2+AI3 pipeline başlıyor…");
  try {
    const queued = await api("/jobs/produce", {
      method: "POST",
      body: { scenario_id: state.scenarioId },
    });
    renderJob(queued, { soft: true });
    $("#playerSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
    const job = await pollJob(queued.id, { label: "AI2 görsel + AI3 kurgu" });
    renderJob(job);
    await refreshMe();
  } catch (err) {
    setError($("#produceError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `Görsel üret · ${state.produceCost} kredi`;
    setWorking(false);
  }
});

$("#refineBtn")?.addEventListener("click", async () => {
  setError($("#refineError"), "");
  if (!state.jobId) {
    setError($("#refineError"), "Önce video üretin");
    return;
  }
  const instruction = ($("#refineInput")?.value || "").trim();
  if (instruction.length < 3) {
    setError($("#refineError"), "En az 3 karakter yazın");
    return;
  }
  const btn = $("#refineBtn");
  btn.disabled = true;
  btn.textContent = "Revize ediliyor…";
  setWorking(true, "Revizyon uygulanıyor…");
  try {
    const job = await api(`/jobs/${state.jobId}/refine`, {
      method: "POST",
      body: { instruction },
    });
    if ($("#refineInput")) $("#refineInput").value = "";
    renderJob(job);
    await refreshMe();
  } catch (err) {
    setError($("#refineError"), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = `Revize et · ${state.refineCost} kredi`;
    setWorking(false);
  }
});

/* --- Creative: ürün / metin / platform görsel --- */

const STUDIO_COPY = {
  scenario: {
    title: "Senaryo",
    lede: "Brief’i doldur, reklam senaryosunu üret.",
  },
  product: {
    title: "Ürün & Metin",
    lede: "Ürün görselini analiz et, satış metinlerini üret.",
  },
  visuals: {
    title: "Platform Görselleri",
    lede: "Platform seç, ajans kalitesinde reklam görseli üret.",
  },
};

function switchStudioPane(name) {
  const mod = STUDIO_COPY[name] ? name : "scenario";
  state.activeStudio = mod;

  document.querySelectorAll("#studioTabs .tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.studio === mod);
  });

  document.querySelectorAll(".studio-pane").forEach((pane) => {
    const on = pane.dataset.pane === mod;
    pane.hidden = !on;
    pane.style.display = on ? "" : "none";
    if (on) {
      pane.classList.remove("pane-enter");
      void pane.offsetWidth;
      pane.classList.add("pane-enter");
    }
  });

  const title = $("#studioTitle");
  const lede = $("#studioLede");
  if (title) title.textContent = STUDIO_COPY[mod].title;
  if (lede) lede.textContent = STUDIO_COPY[mod].lede;

  document.querySelectorAll(".module-result").forEach((el) => {
    const on = el.dataset.moduleResult === mod;
    el.hidden = !on;
    el.style.display = on ? "" : "none";
  });

  const history = $("#historyBlock");
  if (history) {
    const on = mod === "scenario";
    history.hidden = !on;
    history.style.display = on ? "" : "none";
  }
}

$("#studioTabs")?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-studio]");
  if (!btn) return;
  switchStudioPane(btn.dataset.studio);
});

async function loadCreativeCatalog() {
  try {
    const cat = await api("/creative/catalog");
    state.catalog = cat;
    state.analyzeCost = cat.costs?.analyze || 10;
    state.copyCost = cat.costs?.copy || 12;
    state.visualPerPlatform = cat.costs?.visual_per_platform || 15;
    renderCopyTypeGrid(cat.copy_types || []);
    renderPlatformGrid(cat.platforms || []);
    updateCreativeLabels();
  } catch {
    /* katalog opsiyonel boot */
  }
}

function renderCopyTypeGrid(types) {
  const grid = $("#copyTypeGrid");
  if (!grid) return;
  const legend = grid.querySelector("legend");
  grid.innerHTML = "";
  if (legend) grid.appendChild(legend);
  else {
    const l = document.createElement("legend");
    l.textContent = "Üretilecek metinler";
    grid.appendChild(l);
  }
  types.forEach((t, i) => {
    const id = `copy-type-${t.id}`;
    const label = document.createElement("label");
    label.className = "check-item";
    label.innerHTML = `<input type="checkbox" name="copy_type" value="${escapeHtml(t.id)}" ${i < 3 ? "checked" : ""} /> <span><strong>${escapeHtml(t.label)}</strong><small>${escapeHtml(t.hint || "")}</small></span>`;
    grid.appendChild(label);
  });
}

function renderPlatformGrid(platforms) {
  const grid = $("#platformGrid");
  if (!grid) return;
  const legend = grid.querySelector("legend");
  grid.innerHTML = "";
  if (legend) grid.appendChild(legend);
  else {
    const l = document.createElement("legend");
    l.textContent = "Platformlar";
    grid.appendChild(l);
  }
  platforms.forEach((p, i) => {
    const label = document.createElement("label");
    label.className = "check-item";
    label.innerHTML = `<input type="checkbox" name="platform" value="${escapeHtml(p.id)}" ${i < 2 ? "checked" : ""} /> <span><strong>${escapeHtml(p.label)}</strong><small>${escapeHtml(p.ratio)} · ${p.width}×${p.height}</small></span>`;
    grid.appendChild(label);
  });
}

function updateCreativeLabels() {
  const a = $("#analyzeBtn");
  if (a && !a.disabled) a.textContent = `Ürünü analiz et · ${state.analyzeCost} kredi`;
  const c = $("#copyGenBtn");
  if (c) {
    c.textContent = `Metinleri üret · ${state.copyCost} kredi`;
    c.disabled = !state.productAnalysis;
  }
  const v = $("#visualGenBtn");
  if (v) {
    const n = document.querySelectorAll('#platformGrid input[name="platform"]:checked').length || 1;
    const hasFile = Boolean($("#visualImage")?.files?.[0] || $("#productImage")?.files?.[0]);
    const ready = Boolean(state.productAnalysis || hasFile);
    v.textContent = `Platform görselleri üret · ${state.visualPerPlatform * n} kredi`;
    v.disabled = !ready;
  }
}

function previewImage(file, boxSel, imgSel) {
  const box = $(boxSel);
  const img = $(imgSel);
  if (!file || !box || !img) return;
  img.src = URL.createObjectURL(file);
  box.hidden = false;
  box.style.display = "";
}

async function analyzeProductFile(file, { language = "tr", extra = "" } = {}) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("language", language);
  fd.append("extra_context", extra);
  const res = await fetch(`${API}/creative/analyze-product`, {
    method: "POST",
    headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
    body: fd,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    throw new Error(typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail || data));
  }
  state.productAnalysis = data.analysis;
  state.productImageUrl = data.image_url;
  return data;
}

$("#productImage")?.addEventListener("change", () => {
  const file = $("#productImage").files?.[0];
  previewImage(file, "#productPreview", "#productPreviewImg");
  updateCreativeLabels();
});

$("#visualImage")?.addEventListener("change", () => {
  const file = $("#visualImage").files?.[0];
  previewImage(file, "#visualPreview", "#visualPreviewImg");
  setError($("#visualGenError"), "");
  updateCreativeLabels();
});

$("#analyzeBtn")?.addEventListener("click", async () => {
  setError($("#analyzeError"), "");
  const file = $("#productImage")?.files?.[0];
  if (!file) {
    setError($("#analyzeError"), "Ürün görseli seçin");
    return;
  }
  const btn = $("#analyzeBtn");
  btn.disabled = true;
  setWorking(true, "Ürün görseli analiz ediliyor…");
  try {
    const data = await analyzeProductFile(file, {
      language: $("#productLanguage")?.value || "tr",
      extra: $("#productContext")?.value || "",
    });
    const empty = $("#productResultEmpty");
    const body = $("#productResultBody");
    if (empty) empty.hidden = true;
    if (body) {
      body.hidden = false;
      body.style.display = "";
    }
    const box = $("#analysisBox");
    const pre = $("#analysisJson");
    if (box && pre) {
      box.hidden = false;
      box.style.display = "";
      pre.textContent = JSON.stringify(data.analysis, null, 2);
    }
    if (data.analysis?.product_name && !$("#productOffer")?.value) {
      $("#productOffer").value = data.analysis.product_name;
    }
    if (data.analysis?.product_name && !$("#visualOffer")?.value) {
      $("#visualOffer").value = data.analysis.product_name;
    }
    switchStudioPane("product");
    updateCreativeLabels();
    await refreshMe();
  } catch (err) {
    setError($("#analyzeError"), err.message);
  } finally {
    btn.disabled = false;
    updateCreativeLabels();
    setWorking(false);
  }
});

$("#copyGenBtn")?.addEventListener("click", async () => {
  setError($("#copyGenError"), "");
  if (!state.productAnalysis) {
    setError($("#copyGenError"), "Önce ürünü analiz edin");
    return;
  }
  const types = [...document.querySelectorAll('#copyTypeGrid input[name="copy_type"]:checked')].map((el) => el.value);
  if (!types.length) {
    setError($("#copyGenError"), "En az bir metin türü seçin");
    return;
  }
  const btn = $("#copyGenBtn");
  btn.disabled = true;
  setWorking(true, "Pazarlama metinleri yazılıyor…");
  try {
    const data = await api("/creative/generate-copy", {
      method: "POST",
      body: {
        analysis: state.productAnalysis,
        copy_types: types,
        language: $("#productLanguage")?.value || "tr",
        offer: $("#productOffer")?.value || "",
        pain_point: $("#productPain")?.value || "",
        desired_action: $("#productAction")?.value || "dm",
        extra_brief: $("#productContext")?.value || "",
      },
    });
    renderCopies(data.copies || {});
    await refreshMe();
  } catch (err) {
    setError($("#copyGenError"), err.message);
  } finally {
    updateCreativeLabels();
    setWorking(false);
  }
});

function renderCopies(copies) {
  const out = $("#copiesOut");
  if (!out) return;
  const empty = $("#productResultEmpty");
  const body = $("#productResultBody");
  if (empty) empty.hidden = true;
  if (body) body.hidden = false;
  const entries = Object.entries(copies);
  if (!entries.length) {
    out.innerHTML = `<p class="lede tight">Metin henüz yok — türleri seçip üret.</p>`;
    return;
  }
  out.innerHTML = entries
    .map(([key, val]) => {
      const title = escapeHtml(val.title || key);
      const bodyText = escapeHtml(val.body || "");
      const cta = escapeHtml(val.cta || "");
      const tags = (val.hashtags || []).map((t) => escapeHtml(t)).join(" ");
      const notes = escapeHtml(val.notes || "");
      return `<article class="copy-card">
        <header><strong>${title}</strong><span class="badge">${escapeHtml(key)}</span></header>
        <p class="copy-body">${bodyText}</p>
        ${cta ? `<p><strong>CTA:</strong> ${cta}</p>` : ""}
        ${tags ? `<p class="copy-tags">${tags}</p>` : ""}
        ${notes ? `<p class="lede tight">${notes}</p>` : ""}
        <button type="button" class="ghost-btn copy-one" data-copy="${escapeHtml(val.body || "")}">Kopyala</button>
      </article>`;
    })
    .join("");
  switchStudioPane("product");
}

$("#copiesOut")?.addEventListener("click", async (e) => {
  const btn = e.target.closest(".copy-one");
  if (!btn) return;
  try {
    await navigator.clipboard.writeText(btn.getAttribute("data-copy") || "");
    btn.textContent = "Kopyalandı ✓";
    btn.classList.add("is-copied");
    setTimeout(() => {
      btn.textContent = "Kopyala";
      btn.classList.remove("is-copied");
    }, 1400);
  } catch {
    /* ignore */
  }
});

$("#platformGrid")?.addEventListener("change", () => updateCreativeLabels());

$("#visualGenBtn")?.addEventListener("click", async () => {
  setError($("#visualGenError"), "");
  const file = $("#visualImage")?.files?.[0] || $("#productImage")?.files?.[0];
  if (!state.productAnalysis && !file) {
    setError($("#visualGenError"), "Önce bir ürün görseli seçin");
    return;
  }
  const platforms = [...document.querySelectorAll('#platformGrid input[name="platform"]:checked')].map((el) => el.value);
  if (!platforms.length) {
    setError($("#visualGenError"), "En az bir platform seçin");
    return;
  }
  const btn = $("#visualGenBtn");
  btn.disabled = true;
  setWorking(true, "Platform görselleri üretiliyor…");
  try {
    if (!state.productAnalysis) {
      setWorking(true, "Görsel analiz ediliyor…");
      await analyzeProductFile(file, {
        language: $("#productLanguage")?.value || "tr",
        extra: $("#visualOffer")?.value || "",
      });
      await refreshMe();
    }
    setWorking(true, "Platform görselleri üretiliyor…");
    const data = await api("/creative/generate-visuals", {
      method: "POST",
      body: {
        analysis: state.productAnalysis,
        platforms,
        language: $("#productLanguage")?.value || "tr",
        offer: $("#visualOffer")?.value || $("#productOffer")?.value || "",
        style: $("#visualStyle")?.value || "pas",
      },
    });
    renderVisuals(data.visuals || []);
    await refreshMe();
  } catch (err) {
    setError($("#visualGenError"), err.message);
  } finally {
    updateCreativeLabels();
    setWorking(false);
  }
});

function renderVisuals(items) {
  const out = $("#visualsOut");
  if (!out) return;
  const empty = $("#visualResultEmpty");
  if (empty) empty.hidden = items.length > 0;
  out.hidden = false;
  if (!items.length) {
    out.innerHTML = `<p class="lede tight">Görsel henüz yok — platform seçip üret.</p>`;
    return;
  }
  out.innerHTML = items
    .map((v) => {
      const url = mediaUrl(v.url);
      return `<figure class="visual-card">
        <img src="${escapeHtml(url)}" alt="${escapeHtml(v.label || v.platform)}" />
        <figcaption><strong>${escapeHtml(v.label || v.platform)}</strong><span>${escapeHtml(v.ratio || "")} · ${v.width}×${v.height}</span>
        <a class="ghost-btn" href="${escapeHtml(url)}" download target="_blank" rel="noopener">İndir</a></figcaption>
      </figure>`;
    })
    .join("");
  switchStudioPane("visuals");
}

const durationInput = $("#scenarioForm")?.querySelector('[name="duration_seconds"]');
if (durationInput) {
  durationInput.addEventListener("change", () => {
    const dur = Number(durationInput.value || 30);
    state.produceCost = produceCostForDuration(dur);
    updateCostLabels();
  });
}

boot();
