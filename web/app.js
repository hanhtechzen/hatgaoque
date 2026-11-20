// ===== Hạt Gạo Quê Studio - giao diện quản lý =====
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.body && !(o.body instanceof FormData)) {
    o.headers = { "Content-Type": "application/json" };
    o.body = JSON.stringify(o.body);
  }
  const r = await fetch(path, o);
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(data.error || data || r.statusText);
  return data;
}
function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  $("#toast").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}
async function act(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg, "ok"); return r; }
  catch (e) { toast(e.message, "err"); }
}

// ---------- điều hướng ----------
const loaders = {
  home: loadHome, growth: loadGrowth, videos: loadVideos, scripts: loadScripts, topics: loadTopics, chars: loadChars,
  voices: loadVoices, audio: loadAudio, settings: loadSettings, jobs: loadJobs,
};
let currentTab = "home";
function showTab(tab) {
  currentTab = tab;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + tab));
  location.hash = tab;
  loaders[tab]?.();
}
document.querySelectorAll("#nav a").forEach((a) => (a.onclick = () => showTab(a.dataset.tab)));

// ---------- theo dõi tác vụ ----------
const watching = new Map(); // id -> callback khi xong
function watchJob(job, onDone) {
  toast(`Đã thêm vào hàng đợi: ${job.label}`);
  if (onDone) watching.set(job.id, onDone);
  pollJobs();
}
let lastJobsJSON = "";
async function pollJobs() {
  let jobs;
  try { jobs = await api("/api/jobs"); } catch { return; }
  const active = jobs.filter((j) => j.status === "running" || j.status === "queued");
  const b = $("#jobBadge");
  b.textContent = active.length; b.classList.toggle("hidden", !active.length);
  const run = jobs.find((j) => j.status === "running");
  const bar = $("#jobbar");
  if (run) {
    const d = await api(`/api/jobs/${run.id}?tail=1`).catch(() => ({}));
    bar.innerHTML = `<div class="spin"></div><b>${esc(run.label)}</b><span class="last">${esc(d.log_text || "")}</span>`;
    bar.onclick = () => { showTab("jobs"); openJob(run.id); };
    bar.classList.remove("hidden");
  } else bar.classList.add("hidden");
  for (const j of jobs) {
    if (watching.has(j.id) && ["done", "failed", "canceled"].includes(j.status)) {
      const cb = watching.get(j.id); watching.delete(j.id);
      toast(`${j.label}: ${j.status === "done" ? "xong ✓" : "lỗi ✗ (xem tab Tác vụ)"}`, j.status === "done" ? "ok" : "err");
      try { cb(j); } catch {}
    }
  }
  const js = JSON.stringify(jobs);
  if (js !== lastJobsJSON) { lastJobsJSON = js; if (currentTab === "jobs") renderJobs(jobs); if (currentTab === "home") loadHome(); }
}
setInterval(pollJobs, 2500);

// ---------- TỔNG QUAN ----------
async function loadHome() {
  const s = await api("/api/summary");
  $("#stats").innerHTML = [
    ["🎬", s.videos, "video đã tạo"],
    ["📝", `${s.scripts_unused}/${s.scripts_total}`, "kịch bản chưa dùng"],
    ["🔑", s.has_key ? "Có" : "Chưa", "key Pollinations"],
    ["📘", s.facebook ? "Bật" : "Tắt", "đăng Facebook tự động"],
    ["💰", s.budget_vnd.toLocaleString("vi-VN") + "đ", "ngân sách / video"],
  ].map(([i, n, l]) => `<div class="card"><div class="lbl">${i} ${l}</div><div class="num">${esc(n)}</div></div>`).join("");
  const todo = [];
  if (!s.has_key) todo.push(`<li class="err">Chưa có key Pollinations → vào <a onclick="showTab('settings')">Cài đặt</a>.</li>`);
  if (!s.music) todo.push(`<li class="warn">Chưa có nhạc nền → vào <a onclick="showTab('audio')">Âm thanh</a> tải lên vài bài.</li>`);
  if (s.sfx.length < 3) todo.push(`<li class="warn">Mới có ${s.sfx.length}/8 âm thanh không khí (tiếng ve, mưa, bếp củi...) → <a onclick="showTab('audio')">Âm thanh</a>.</li>`);
  if (!s.facebook) todo.push(`<li>Facebook đang tắt: video chỉ được tạo ra, chưa tự đăng → <a onclick="showTab('settings')">Cài đặt</a>.</li>`);
  if (s.scripts_unused < 3) todo.push(`<li class="warn">Sắp hết kịch bản có sẵn (AI sẽ tự viết theo chủ đề). Muốn duyệt trước thì vào <a onclick="showTab('scripts')">Kịch bản</a>.</li>`);
  if (!todo.length) todo.push(`<li class="ok">Mọi thứ đã sẵn sàng ✓</li>`);
  $("#todo").innerHTML = todo.join("");
}
function runNow(count) {
  const no_post = $("#noPost").checked;
  act(async () => watchJob(await api("/api/run", { method: "POST", body: { count, no_post } }), () => loadVideos()));
}

// ---------- TĂNG TRƯỞNG ----------
let growthData = null;
async function loadGrowth() {
  const g = (growthData = await api("/api/growth"));
  $("#growthPlan").innerHTML = `
    <h2>📈 Chiến lược đang chạy</h2>
    <div class="plan">
      <div><b>Nhịp đăng</b><span>${g.videos_per_run} video/ngày</span>
        <div class="row"><input id="g-count" type="number" min="1" max="10" value="${g.videos_per_run}" style="width:70px"> video mỗi lần chạy</div></div>
      <div><b>Giờ đăng Facebook</b><span>${g.fb_enabled ? g.fb_times.join(" · ") : "Facebook đang tắt"}</span>
        <div class="row"><input id="g-fb" value="${esc(g.fb_times.join(", "))}" style="width:150px"></div></div>
      <div><b>Giờ gợi ý TikTok</b><span>${g.tiktok_times.join(" · ")}</span>
        <div class="row"><input id="g-tk" value="${esc(g.tiktok_times.join(", "))}" style="width:150px"></div></div>
      <div><b>Mùa nội dung</b><span>${g.seasons.length ? g.seasons.join(", ") : "Không có mùa đặc biệt"}</span>
        <div class="muted">Đúng mùa thì ưu tiên tập hợp mùa</div></div>
      <div><b>Trả lời bình luận</b><span>${g.auto_reply ? "Tự động gửi" : "AI soạn, bạn duyệt"}</span>
        <label class="check"><input type="checkbox" id="g-auto" ${g.auto_reply ? "checked" : ""}> Tự gửi không cần duyệt</label></div>
    </div>
    <div class="row" style="margin-top:10px"><button onclick="saveGrowth()">💾 Lưu chiến lược</button>
      <span class="muted">Khung giờ cách nhau bằng dấu phẩy, vd: 11:30, 19:30</span></div>`;
  $("#tkInfo").textContent = `${g.tiktok_queue.length} video chờ · đã đăng ${g.tiktok_posted.length}`;
  $("#tkQueue").innerHTML = g.tiktok_queue.map((q, i) => `<div class="tkitem">
      <div class="tkthumb" style="background-image:url('${q.cover || ""}')"></div>
      <div class="tkbody"><b>${esc(q.title)}</b>
        <div class="muted">Gợi ý đăng: <b>${esc(q.suggest || "")}</b></div>
        <div class="row">
          <button onclick="copyTk(${i})">📋 Copy nội dung</button>
          <a class="btn" href="${q.video}" download="${esc(q.folder)}.mp4">⬇ Tải video</a>
          <a class="btn" href="https://www.tiktok.com/tiktokstudio/upload" target="_blank">🎵 Mở TikTok Studio</a>
          <button class="primary" onclick="markTk(${i})">✓ Đã đăng</button>
          <button onclick="skipTk(${i})" title="Không đăng video này lên TikTok">Bỏ qua</button>
        </div></div></div>`).join("") || `<div class="muted">Không còn video chờ đăng TikTok 🎉</div>`;
  $("#cmInfo").textContent = `${g.comments.length} chờ duyệt · đã trả lời ${g.comments_replied}`;
  $("#cmList").innerHTML = g.comments.map((c, i) => `<div class="cm">
      <div class="cmq"><b>${esc(c.from)}</b> <span class="muted">· ${esc(c.title || "")}</span><div>${esc(c.message)}</div></div>
      <textarea id="cm-${i}" rows="2">${esc(c.draft || "")}</textarea>
      <div class="row"><button class="primary" onclick="sendCm(${i})">➤ Gửi</button><button onclick="skipCm(${i})">Bỏ qua</button></div></div>`).join("")
    || `<div class="muted">${g.fb_enabled ? "Chưa có bình luận mới. Bấm “Đồng bộ” để kiểm tra." : "Bật Facebook trong Cài đặt để nhận bình luận."}</div>`;
  const n = (x) => (x ? Number(x).toLocaleString("vi-VN") : "–");
  $("#lbTable").innerHTML = `<tr><th>#</th><th>Video</th><th>FB xem</th><th>FB xem TB (s)</th><th>FB bình luận</th><th>FB chia sẻ</th><th>TikTok xem</th><th>TikTok thích</th><th>Điểm</th><th></th></tr>` +
    g.leaderboard.map((r, i) => `<tr><td>${i + 1}</td><td><b>${esc(r.title)}</b><div class="muted">${esc(r.hook || "")}</div></td>
      <td>${n(r.fb.blue_reels_play_count || r.fb.fb_reels_total_plays)}</td><td>${r.fb.post_video_avg_time_watched ? (r.fb.post_video_avg_time_watched / 1000).toFixed(1) : "–"}</td>
      <td>${n(r.fb["post_video_social_actions.comment"])}</td><td>${n(r.fb["post_video_social_actions.share"])}</td>
      <td><input class="num" id="tv-${i}" value="${r.tiktok.views ?? ""}" placeholder="0"></td>
      <td><input class="num" id="tl-${i}" value="${r.tiktok.likes ?? ""}" placeholder="0"></td>
      <td><b>${n(Math.round(r.score))}</b></td><td><button onclick="saveTkStats(${i})">Lưu</button></td></tr>`).join("")
    || `<tr><td class="muted">Chưa có video nào được ghi nhận.</td></tr>`;
}
function saveGrowth() {
  const split = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
  act(() => api("/api/growth/settings", { method: "PUT", body: {
    videos_per_run: +$("#g-count").value, fb_times: split($("#g-fb").value), tiktok_times: split($("#g-tk").value),
    auto_reply: $("#g-auto").checked } }), "Đã lưu chiến lược").then(loadGrowth);
}
function growthSync() { act(async () => watchJob(await api("/api/growth/sync", { method: "POST" }), loadGrowth)); }
function copyTk(i) { navigator.clipboard.writeText(growthData.tiktok_queue[i].caption); toast("Đã copy nội dung", "ok"); }
function markTk(i) {
  const q = growthData.tiktok_queue[i];
  const url = prompt(`Đánh dấu "${q.title}" đã đăng TikTok.\nDán link video TikTok (không bắt buộc):`, "");
  if (url === null) return;
  act(() => api(`/api/tiktok/${encodeURIComponent(q.folder)}`, { method: "POST", body: { posted: true, url } }), "Đã đánh dấu").then(loadGrowth);
}
function skipTk(i) {
  const q = growthData.tiktok_queue[i];
  act(() => api(`/api/tiktok/${encodeURIComponent(q.folder)}`, { method: "POST", body: { skip: true } }), "Đã bỏ khỏi hàng chờ").then(loadGrowth);
}
function saveTkStats(i) {
  const r = growthData.leaderboard[i];
  act(() => api(`/api/tiktok/${encodeURIComponent(r.folder)}`, { method: "POST", body: { views: $("#tv-" + i).value, likes: $("#tl-" + i).value } }), "Đã lưu số liệu TikTok").then(loadGrowth);
}
function sendCm(i) {
  const c = growthData.comments[i], text = $("#cm-" + i).value.trim();
  if (!text) return toast("Câu trả lời trống", "err");
  act(() => api(`/api/comments/${encodeURIComponent(c.id)}/send`, { method: "POST", body: { text } }), "Đã gửi trả lời").then(loadGrowth);
}
function skipCm(i) {
  act(() => api(`/api/comments/${encodeURIComponent(growthData.comments[i].id)}/skip`, { method: "POST" })).then(loadGrowth);
}

// ---------- VIDEO ----------
let videosCache = [];
async function loadVideos() {
  videosCache = await api("/api/videos");
  $("#videoGrid").innerHTML = videosCache.length ? videosCache.map((v, i) => {
    const fb = v.facebook_error ? `<span class="tag err" title="${esc(v.facebook_error)}">FB lỗi</span>`
      : v.facebook?.scheduled ? `<span class="tag ok">FB hẹn ${esc(v.facebook.scheduled)}</span>`
      : v.facebook?.posted ? `<span class="tag ok">Đã đăng FB</span>` : `<span class="tag">Chưa đăng</span>`;
    return `<div class="vcard">
      <div class="thumb" style="background-image:url('${v.cover || ""}')" onclick="openVideo(${i})"></div>
      <div class="body">
        <div class="title">${esc(v.title)}</div>
        <div class="meta">${esc(v.created)} · ${esc(v.cost || "")}</div>
        <div>${fb}</div>
        <div class="acts">
          <button onclick="openVideo(${i})">▶ Xem</button>
          <a class="btn" href="${v.video}" download="${esc(v.folder)}.mp4">⬇ Tải</a>
          <button onclick="postVideo(${i})">📘 Đăng</button>
          <button class="danger" onclick="archiveVideo(${i})" title="Chuyển vào thư mục lưu trữ">🗄</button>
        </div>
      </div></div>`;
  }).join("") : `<div class="empty">Chưa có video. Vào Tổng quan bấm "Tạo 1 video ngay", hoặc vào Kịch bản bấm "Dựng video".</div>`;
}
function openVideo(i) {
  const v = videosCache[i];
  openModal(`<div class="player">
    <video src="${v.video}" controls autoplay></video>
    <div><h2>${esc(v.title)}</h2>
      <p class="muted">${esc(v.created)} · ${esc(v.cost)}</p>
      <div class="lbl muted">Nội dung đăng (copy cho TikTok):</div>
      <pre id="capText">${esc(v.caption)}</pre>
      <div class="row">
        <button class="primary" onclick="navigator.clipboard.writeText($('#capText').textContent);toast('Đã copy','ok')">📋 Copy nội dung</button>
        <a class="btn" href="${v.video}" download="${esc(v.folder)}.mp4">⬇ Tải video</a>
        <a class="btn" href="https://www.tiktok.com/tiktokstudio/upload" target="_blank">🎵 Mở TikTok Studio</a>
      </div>
    </div></div>`);
}
function postVideo(i) {
  const v = videosCache[i];
  if (!confirm(`Đăng "${v.title}" lên Facebook Page?\n(Theo cài đặt: hẹn giờ hoặc đăng ngay)`)) return;
  act(async () => watchJob(await api(`/api/videos/${encodeURIComponent(v.folder)}/post`, { method: "POST" }), loadVideos));
}
function archiveVideo(i) {
  const v = videosCache[i];
  if (!confirm(`Chuyển "${v.title}" vào thư mục lưu trữ (output/_luu_tru)? Không xóa file.`)) return;
  act(() => api(`/api/videos/${encodeURIComponent(v.folder)}/archive`, { method: "POST" }), "Đã lưu trữ").then(loadVideos);
}

// ---------- KỊCH BẢN ----------
let scriptsCache = [], currentScript = null;
const AMB = { ve_sau: "Tiếng ve trưa hè", mua: "Mưa", bep_cui: "Bếp củi", dem_que: "Đêm quê (dế)", san_truong: "Sân trường", lang_que: "Làng quê buổi sáng", gio_dong: "Gió đồng", pho_cu: "Phố cũ" };
const SPK = { "": "🎙 Người kể", ba: "👵 Bà nói", ong: "👴 Ông nói", me: "👩 Mẹ nói", bo: "👨 Bố nói" };
async function loadScripts() { scriptsCache = await api("/api/scripts"); renderScripts(); }
function renderScripts() {
  const q = $("#scriptSearch").value.toLowerCase(), f = $("#scriptFilter").value;
  const list = scriptsCache.filter((s) => (f === "all" || (f === "used") === s.used) && (s.title + s.id).toLowerCase().includes(q));
  $("#scriptList").innerHTML = list.map((s) => `<div class="sitem ${currentScript?.id === s.id ? "active" : ""}" onclick="openScript('${s.id}')">
    <div class="t">${esc(s.title)}</div>
    <div class="s">${s.scenes} cảnh · ${esc(s.updated)} ${s.used ? '<span class="tag">đã dùng</span>' : '<span class="tag new">chưa dùng</span>'}</div></div>`).join("") || `<div class="muted">Không có kịch bản.</div>`;
}
async function openScript(id) {
  currentScript = await api(`/api/scripts/${id}`);
  renderScripts(); renderEditor();
}
function renderEditor() {
  const d = currentScript, used = scriptsCache.find((s) => s.id === d.id)?.used;
  const scenes = (d.scenes || []).map((s, i) => `<div class="scene ${s.speaker ? "dialog" : ""}">
    <div class="shead"><b>Cảnh ${i + 1}</b>
      <select onchange="setScene(${i},'speaker',this.value);renderEditor()">${Object.entries(SPK).map(([k, v]) => `<option value="${k}" ${(s.speaker || "") === k ? "selected" : ""}>${v}</option>`).join("")}</select>
      <span class="sp"><button onclick="moveScene(${i},-1)" title="Lên">↑</button><button onclick="moveScene(${i},1)" title="Xuống">↓</button><button class="danger" onclick="delScene(${i})" title="Xóa cảnh">✕</button></span></div>
    <textarea rows="2" oninput="setScene(${i},'text',this.value)" placeholder="Lời kể / lời thoại">${esc(s.text)}</textarea>
    <div class="lbl">Mô tả ảnh (tiếng Anh, mỗi dòng 1 ảnh; dùng {BIN} {BA} {ONG} {ME} {BO} {BANBE})</div>
    <textarea rows="2" oninput="setScene(${i},'images',this.value.split('\\n').filter(x=>x.trim()))">${esc((s.images || []).join("\n"))}</textarea>
    <div class="lbl">Cử động (tùy chọn, tiếng Anh - cảnh có dòng này được ưu tiên làm clip chuyển động)</div>
    <input style="width:100%" value="${esc(s.motion || "")}" oninput="setScene(${i},'motion',this.value)" placeholder="vd: Bin jumps up and down cheering, grandma laughs">
  </div>`).join("");
  $("#scriptEditor").innerHTML = `<div class="panel">
    <div class="head"><h2>${esc(d.title)}</h2>
      <div class="row">
        <button class="primary" onclick="saveScript()">💾 Lưu</button>
        <button onclick="buildScript()">🎬 Dựng video</button>
        <button onclick="toggleUsed(${!used})">${used ? "↺ Đánh dấu chưa dùng" : "✓ Đánh dấu đã dùng"}</button>
        <button class="danger" onclick="archiveScript()">🗄 Lưu trữ</button>
      </div></div>
    <div class="form">
      <div class="field"><label>Tiêu đề</label><input value="${esc(d.title)}" oninput="currentScript.title=this.value"></div>
      <div class="field"><label>Âm thanh nền</label><select onchange="currentScript.ambience=this.value">${Object.entries(AMB).map(([k, v]) => `<option value="${k}" ${d.ambience === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      <div class="field full"><label>Câu móc (chữ to 3 giây đầu)</label><input value="${esc(d.hook)}" oninput="currentScript.hook=this.value"></div>
      <div class="field full"><label>Nội dung đăng kèm</label><textarea rows="2" oninput="currentScript.caption=this.value">${esc(d.caption)}</textarea></div>
      <div class="field full"><label>Hashtag (cách nhau bằng dấu cách)</label><input value="${esc((d.hashtags || []).join(" "))}" oninput="currentScript.hashtags=this.value.split(/\\s+/).filter(Boolean)"></div>
    </div></div>
    <div class="panel"><div class="head"><h2>Các cảnh (${(d.scenes || []).length})</h2><button onclick="addScene()">＋ Thêm cảnh</button></div>${scenes}</div>`;
}
function setScene(i, k, v) { const s = currentScript.scenes[i]; if (v === "" || (Array.isArray(v) && !v.length && k !== "images")) delete s[k]; else s[k] = v; }
function moveScene(i, d) { const a = currentScript.scenes, j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; renderEditor(); }
function delScene(i) { if (confirm("Xóa cảnh " + (i + 1) + "?")) { currentScript.scenes.splice(i, 1); renderEditor(); } }
function addScene() { currentScript.scenes.push({ text: "", images: ["{BIN} ..."] }); renderEditor(); }
async function saveScript() {
  await act(() => api(`/api/scripts/${currentScript.id}`, { method: "PUT", body: currentScript }), "Đã lưu kịch bản");
  await loadScripts();
}
async function buildScript() {
  await saveScript();
  act(async () => watchJob(await api(`/api/scripts/${currentScript.id}/build`, { method: "POST" }), () => loadVideos()));
}
async function toggleUsed(used) {
  await act(() => api(`/api/scripts/${currentScript.id}/used`, { method: "POST", body: { used } }));
  await loadScripts(); renderEditor();
}
async function archiveScript() {
  if (!confirm("Chuyển kịch bản này vào lưu trữ (data/scripts_luu_tru)?")) return;
  await act(() => api(`/api/scripts/${currentScript.id}/archive`, { method: "POST" }), "Đã lưu trữ");
  currentScript = null; $("#scriptEditor").innerHTML = `<div class="empty">Chọn một kịch bản bên trái.</div>`; loadScripts();
}
async function newScript() {
  const title = prompt("Tên tập mới:", "Bin ...");
  if (!title) return;
  const d = await act(() => api("/api/scripts", { method: "POST", body: { title } }), "Đã tạo tập mới");
  if (d) { await loadScripts(); openScript(d.id); }
}
function aiWrite(topic) {
  topic = topic || $("#aiTopic").value.trim();
  if (!topic) return toast("Nhập chủ đề trước", "err");
  act(async () => watchJob(await api("/api/scripts/write", { method: "POST", body: { topic } }), async () => { await loadScripts(); if (scriptsCache[0]) openScript(scriptsCache[0].id); }));
}

// ---------- CHỦ ĐỀ ----------
let topicsCache = [];
async function loadTopics() { topicsCache = await api("/api/topics"); renderTopics(); }
function renderTopics() {
  $("#topicList").innerHTML = topicsCache.map((t, i) => `<div class="topic ${t.used ? "used" : ""}"><span>${esc(t.topic)}</span>
    <button title="AI viết kịch bản cho chủ đề này" onclick="aiWriteTopic(${i})">✨</button><button class="danger" onclick="topicsCache.splice(${i},1);renderTopics()">✕</button></div>`).join("");
}
function addTopic() { const v = $("#newTopic").value.trim(); if (!v) return; topicsCache.unshift({ topic: v, used: false }); $("#newTopic").value = ""; renderTopics(); }
function saveTopics() { act(() => api("/api/topics", { method: "PUT", body: topicsCache.map((t) => t.topic) }), "Đã lưu chủ đề"); }
function aiWriteTopic(i) { showTab("scripts"); aiWrite(topicsCache[i].topic); }

// ---------- NHÂN VẬT ----------
async function loadChars() {
  const list = await api("/api/characters");
  $("#charGrid").innerHTML = list.map((c) => `<div class="ccard">
    ${c.image ? `<img src="${c.image}">` : `<div class="noimg">Chưa có ảnh mẫu</div>`}
    <div class="field"><label>Tên</label><input id="cn-${c.key}" value="${esc(c.name)}"></div>
    <div class="field"><label>Mã trong kịch bản: {${c.key}}</label><textarea id="cl-${c.key}" rows="4">${esc(c.look)}</textarea></div>
    <div class="row"><button onclick="saveChar('${c.key}')">💾 Lưu</button><button class="primary" onclick="redrawChar('${c.key}')">🎨 Vẽ lại</button></div></div>`).join("");
}
async function saveChar(k) {
  return act(() => api(`/api/characters/${k}`, { method: "PUT", body: { name: $("#cn-" + k).value, look: $("#cl-" + k).value } }), "Đã lưu");
}
async function redrawChar(k) {
  await saveChar(k);
  act(async () => watchJob(await api(`/api/characters/${k}/redraw`, { method: "POST" }), loadChars));
}

// ---------- GIỌNG ĐỌC ----------
let voiceData = null;
async function loadVoices() {
  voiceData = await api("/api/voices");
  const t = voiceData.tts, sp = t.speakers || {};
  const rows = [
    ["narrator", "🎙 Người kể", t.provider || "vieneu", t.provider === "mai" ? t.mai?.voice : t.provider === "edge" ? t.edge_voice : t.vieneu_voice],
    ["ba", "👵 Bà", sp.ba?.provider || "vieneu", sp.ba?.voice],
    ["ong", "👴 Ông", sp.ong?.provider || "vieneu", sp.ong?.voice],
  ];
  $("#voiceRows").innerHTML = rows.map(([k, label, prov, voice]) => `<div class="vrow">
    <b>${label}</b>
    <select id="vp-${k}" onchange="fillVoices('${k}')">${["vieneu", "mai"].concat(k === "narrator" ? ["edge"] : []).map((p) => `<option value="${p}" ${p === prov ? "selected" : ""}>${{ vieneu: "VieNeu (máy)", mai: "MAI (Microsoft)", edge: "Edge (dự phòng)" }[p]}</option>`).join("")}</select>
    <select id="vv-${k}" data-cur="${esc(voice || "")}"></select>
    <button onclick="sampleVoice('${k}')">🔊 Nghe thử</button>
    <audio id="va-${k}" controls></audio></div>`).join("");
  rows.forEach(([k]) => fillVoices(k));
}
function fillVoices(k) {
  const prov = $("#vp-" + k).value, sel = $("#vv-" + k), cur = sel.dataset.cur;
  sel.innerHTML = voiceData[prov].map((v) => `<option ${v === cur ? "selected" : ""}>${esc(v)}</option>`).join("");
  const key = (prov + "_" + sel.value).replace(/[^\p{L}\p{M}\p{N}_-]+/gu, "_"); // khớp \w của Python
  const a = $("#va-" + k); a.src = voiceData.samples[key] || ""; a.classList.toggle("hidden", !voiceData.samples[key]);
  sel.onchange = () => { sel.dataset.cur = sel.value; fillVoices(k); };
}
function sampleVoice(k) {
  const provider = $("#vp-" + k).value, voice = $("#vv-" + k).value, text = $("#sampleText").value;
  act(async () => {
    const job = await api("/api/voices/sample", { method: "POST", body: { provider, voice, text } });
    watchJob(job, (j) => { if (j.status === "done") { const a = $("#va-" + k); a.src = job.sample + "?t=" + Date.now(); a.classList.remove("hidden"); a.play(); } });
  });
}
function saveVoices() {
  const g = (k) => ({ provider: $("#vp-" + k).value, voice: $("#vv-" + k).value });
  act(() => api("/api/voices", { method: "PUT", body: { narrator: g("narrator"), ba: g("ba"), ong: g("ong") } }), "Đã lưu giọng đọc");
}

// ---------- ÂM THANH ----------
async function loadAudio() {
  aiAudioEstimate();
  const d = await api("/api/audio");
  $("#musicList").innerHTML = d.music.map((m) => `<div class="mitem"><span>🎵 ${esc(m.name)}</span><audio controls preload="none" src="${m.url}"></audio>
    <button class="danger" onclick="removeAudio('music','${esc(m.name)}')">✕</button></div>`).join("") || `<div class="muted">Chưa có nhạc nền.</div>`;
  $("#sfxList").innerHTML = d.sfx.map((s) => `<div class="sfxitem"><b>${esc(AMB[s.name] || s.name)}</b>
    ${s.url ? `<audio controls preload="none" src="${s.url}"></audio>` : `<span class="muted" style="flex:1">chưa có</span>`}
    <label class="btn">⬆<input type="file" accept=".mp3,.m4a,.wav,.ogg" hidden onchange="uploadAudio('${s.name}', this)"></label></div>`).join("");
}
async function aiAudioEstimate() {
  const e = await api("/api/audio/ai-estimate").catch(() => null);
  const btn = $("#aiAudioBtn");
  if (!e) return null;
  if (!e.music && !e.sfx) { btn.textContent = "✓ Đã có đủ"; btn.disabled = true; }
  else { btn.disabled = false; btn.textContent = `✨ Tạo bằng AI (~${e.vnd.toLocaleString("vi-VN")}đ)`; }
  return e;
}
async function aiAudio() {
  const e = await aiAudioEstimate();
  if (!e || (!e.music && !e.sfx)) return;
  if (!confirm(`AI sẽ tạo ${e.music} bài nhạc + ${e.sfx} âm thanh còn thiếu.\nChi phí ước tính: ~${e.vnd.toLocaleString("vi-VN")}đ (${e.usd} USD), trừ vào tài khoản Pollinations, chỉ tốn 1 lần.\nTiếp tục?`)) return;
  act(async () => watchJob(await api("/api/audio/ai", { method: "POST", body: {} }), (j) => {
    loadAudio();
    if (j.status !== "done") { showTab("jobs"); openJob(j.id); }
  }));
}
async function uploadAudio(kind, input) {
  for (const f of input.files) {
    const fd = new FormData(); fd.append("kind", kind); fd.append("file", f);
    await act(() => api("/api/audio/upload", { method: "POST", body: fd }), "Đã tải lên " + f.name);
  }
  loadAudio();
}
function removeAudio(kind, name) {
  if (!confirm(`Gỡ "${name}"? (chuyển vào assets/_da_go, không xóa hẳn)`)) return;
  act(() => api("/api/audio/remove", { method: "POST", body: { kind, name } }), "Đã gỡ").then(loadAudio);
}

// ---------- CÀI ĐẶT ----------
async function loadSettings() {
  const s = await api("/api/settings"), c = s.config, fb = c.publish?.facebook || {}, m = c.motion || {};
  const vnd = Math.round((c.budget_usd_per_video || 0.18) * (c.usd_to_vnd || 26000));
  const keyField = (k, label, help) => `<div class="field"><label>${label} ${s.env_set[k] ? '<span class="tag ok">đã có</span>' : '<span class="tag">chưa có</span>'}</label>
    <input id="env-${k}" type="password" placeholder="${s.env_set[k] ? esc(s.env[k]) + " (để trống = giữ nguyên)" : "Dán vào đây"}">${help ? `<div class="muted">${help}</div>` : ""}</div>`;
  $("#settingsForm").innerHTML = `
    <div class="panel full"><h2>🔑 Khóa dịch vụ</h2><div class="form">
      ${keyField("POLLINATIONS_TOKEN", "Pollinations key", 'Ảnh, giọng MAI, AI viết kịch bản, cảnh cử động. <a href="https://enter.pollinations.ai" target="_blank">Quản lý / nạp tiền</a>')}
      ${keyField("GEMINI_API_KEY", "Gemini key (tùy chọn)", "Dự phòng để AI viết kịch bản")}
      ${keyField("FB_PAGE_ID", "Facebook Page ID", "")}
      ${keyField("FB_PAGE_TOKEN", "Facebook Page Token", "Cách lấy: xem README mục 6")}
    </div></div>
    <div class="panel full"><h2>🎬 Video</h2><div class="form">
      <div class="field"><label>Tên series (hiện trên video)</label><input id="s-series" value="${esc(c.video?.series_name || "")}"></div>
      <div class="field"><label>Phong cách ảnh</label><select id="s-style">${[["hoat_hinh_3d", "Hoạt hình 3D"], ["anh_xua_sang", "Ảnh phim xưa"], ["minh_hoa", "Tranh minh họa"], ["anh_that", "Ảnh chụp"]].map(([k, v]) => `<option value="${k}" ${c.images?.style === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      <div class="field"><label>Ngân sách tối đa / video (đồng)</label><input id="s-budget" type="number" step="500" value="${vnd}"></div>
      <div class="field"><label>Số video mỗi lần chạy tự động</label><input id="s-count" type="number" min="1" max="10" value="${c.videos_per_run || 1}"></div>
      <div class="field"><label class="check"><input type="checkbox" id="s-motion" ${m.enabled ? "checked" : ""}> Cảnh cử động thật (Seedance, cần nạp tiền)</label></div>
      <div class="field"><label>Độ nét clip cử động</label><select id="s-res"><option value="480p" ${m.resolution === "480p" ? "selected" : ""}>480p (~1.000đ/clip, được 3 clip)</option><option value="720p" ${m.resolution === "720p" ? "selected" : ""}>720p (~2.200đ/clip, nét hơn)</option></select></div>
      <div class="field"><label>Số clip cử động tối đa / video</label><input id="s-shots" type="number" min="0" max="6" value="${m.max_shots ?? 3}"></div>
    </div></div>
    <div class="panel full"><h2>👋 Cảnh kết (mời theo dõi)</h2><div class="form">
      <div class="field" style="grid-row: span 3"><div id="outroImg" class="outro-prev"></div>
        <button style="margin-top:6px" onclick="redrawOutro()">🎨 Vẽ lại ảnh cảnh kết</button></div>
      <div class="field"><label class="check" style="margin-top:0"><input type="checkbox" id="s-outro" ${c.video?.outro?.enabled !== false ? "checked" : ""}> Thêm cảnh kết cuối mỗi video</label></div>
      <div class="field"><label>Chữ trên màn hình (xuống dòng được)</label><textarea id="s-outro-text" rows="2">${esc((c.video?.outro?.text || "").replace(/\\N/g, "\n"))}</textarea></div>
      <div class="field"><label>Lời mời (giọng người kể đọc)</label><input id="s-outro-voice" value="${esc(c.video?.outro?.voice || "")}"></div>
    </div></div>
    <div class="panel full"><h2>📘 Facebook</h2><div class="form">
      <div class="field"><label class="check"><input type="checkbox" id="s-fb" ${fb.enabled ? "checked" : ""}> Tự đăng lên Facebook Page</label></div>
      <div class="field"><label>Cách đăng</label><select id="s-fbmode"><option value="scheduled" ${fb.mode !== "now" ? "selected" : ""}>Hẹn giờ (xem trước được)</option><option value="now" ${fb.mode === "now" ? "selected" : ""}>Đăng ngay</option></select></div>
      <div class="field"><label>Giờ đăng</label><div class="muted">${esc((fb.times || [fb.time || "19:30"]).join(" · "))} - chỉnh ở tab <a onclick="showTab('growth')">🚀 Tăng trưởng</a></div></div>
    </div></div>`;
  loadSchedule();
  loadOutro();
}
async function loadOutro() {
  const o = await api("/api/outro").catch(() => ({}));
  $("#outroImg").innerHTML = o.image ? `<img src="${o.image}">` : `<div class="muted">Chưa có ảnh - sẽ tự tạo ở video kế tiếp</div>`;
}
function redrawOutro() {
  if (!confirm("Vẽ lại ảnh cảnh kết (Bin vẫy tay)? Ảnh cũ được chuyển vào assets/_da_go.")) return;
  act(async () => watchJob(await api("/api/outro/redraw", { method: "POST" }), loadOutro));
}
function saveSettings() {
  const env = {};
  ["POLLINATIONS_TOKEN", "GEMINI_API_KEY", "FB_PAGE_ID", "FB_PAGE_TOKEN"].forEach((k) => { const v = $("#env-" + k).value.trim(); if (v) env[k] = v; });
  const config = {
    series_name: $("#s-series").value, style: $("#s-style").value, budget_vnd: +$("#s-budget").value,
    videos_per_run: +$("#s-count").value, motion_enabled: $("#s-motion").checked, motion_resolution: $("#s-res").value,
    max_shots: +$("#s-shots").value,
    outro: { enabled: $("#s-outro").checked, text: $("#s-outro-text").value, voice: $("#s-outro-voice").value },
    facebook: { enabled: $("#s-fb").checked, mode: $("#s-fbmode").value },
  };
  act(() => api("/api/settings", { method: "PUT", body: { config, env } }), "Đã lưu cài đặt").then(loadSettings);
}
function checkSetup() { act(async () => watchJob(await api("/api/check", { method: "POST" }), (j) => { showTab("jobs"); openJob(j.id); })); }
async function loadSchedule() {
  const s = await api("/api/schedule").catch(() => ({ enabled: false }));
  $("#schedOn").checked = !!s.enabled;
  if (s.time) $("#schedTime").value = s.time;
  $("#schedInfo").textContent = s.enabled ? `Đang bật · lần chạy tới: ${s.next || "?"}` : "Đang tắt";
}
function saveSchedule() {
  act(() => api("/api/schedule", { method: "POST", body: { enabled: $("#schedOn").checked, time: $("#schedTime").value } }), "Đã cập nhật lịch").then(loadSchedule);
}

// ---------- TÁC VỤ ----------
let openJobId = null, jobTimer = null;
async function loadJobs() { renderJobs(await api("/api/jobs")); if (openJobId) openJob(openJobId); }
function renderJobs(jobs) {
  const st = { queued: "chờ", running: "đang chạy", done: "xong", failed: "lỗi", canceled: "đã hủy" };
  $("#jobList").innerHTML = jobs.map((j) => `<div class="sitem ${openJobId === j.id ? "active" : ""}" onclick="openJob(${j.id})">
    <div class="t">${esc(j.label)}</div><div class="s"><span class="jstat ${j.status}">● ${st[j.status]}</span> · ${esc(j.created)}
    ${["queued", "running"].includes(j.status) ? `<button style="float:right;padding:1px 8px" onclick="event.stopPropagation();cancelJob(${j.id})">Hủy</button>` : ""}</div></div>`).join("") || `<div class="muted">Chưa có tác vụ.</div>`;
}
async function openJob(id) {
  openJobId = id; clearTimeout(jobTimer);
  const j = await api(`/api/jobs/${id}?tail=400`).catch(() => null);
  if (!j) return;
  const el = $("#jobLog"), atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
  el.textContent = j.log_text || "(chưa có log)";
  if (atBottom) el.scrollTop = el.scrollHeight;
  document.querySelectorAll("#jobList .sitem").forEach((n) => n.classList.toggle("active", n.getAttribute("onclick") === `openJob(${id})`));
  if (["queued", "running"].includes(j.status) && currentTab === "jobs") jobTimer = setTimeout(() => openJob(id), 1500);
}
function cancelJob(id) { if (confirm("Hủy tác vụ này?")) act(() => api(`/api/jobs/${id}/cancel`, { method: "POST" }), "Đã hủy").then(loadJobs); }

// ---------- modal ----------
function openModal(html) { $("#modalBox").innerHTML = html; $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); $("#modalBox").innerHTML = ""; }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

window.addEventListener("hashchange", () => { const t = location.hash.slice(1); if (t && t !== currentTab && loaders[t]) showTab(t); });
showTab(location.hash.slice(1) || "home");
pollJobs();
