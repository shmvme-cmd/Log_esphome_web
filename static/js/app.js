/* global io */
"use strict";

// -----------------------------------------------
//  Socket.IO
// -----------------------------------------------
const socket = io();

socket.on("connect",    () => console.log("Socket.IO connected:", socket.id));
socket.on("disconnect", () => updateStatus("Соединение потеряно", "disconnected"));
socket.on("status",     ({ message, state }) => updateStatus(message, state));
socket.on("log",        ({ message, level }) => {
    hidePlaceholder();
    addLogLine(message, level ?? "data");
});
socket.on("buttons_ready", ({ buttons }) => {
    const sel = document.getElementById("buttonSelect");
    sel.innerHTML = "";
    if (!buttons || !buttons.length) {
        sel.innerHTML = "<option value=''>— кнопки не найдены —</option>";
        sel.disabled = true;
        return;
    }
    buttons.forEach(({ key, name }) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.text  = name;
        sel.appendChild(opt);
    });
    sel.disabled = false;
});

socket.on("result_saved", ({ id }) => {
    showToast("✅ Результат Autotune сохранён в историю", "success");
    refreshHistoryFilterDevices();
    if (currentTab === "history") loadHistory();
});

// -----------------------------------------------
//  State
// -----------------------------------------------
let logColor   = "green";
let lineCount  = 0;
let currentTab = "terminal";

// -----------------------------------------------
//  Init
// -----------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    loadSavedDevices();
    refreshHistoryFilterDevices();
});

// -----------------------------------------------
//  Tab switching
// -----------------------------------------------
function switchTab(tab) {
    currentTab = tab;
    const isTerminal = tab === "terminal";
    document.getElementById("terminalTab").style.display = isTerminal ? "flex" : "none";
    document.getElementById("historyTab").style.display  = isTerminal ? "none"  : "flex";
    document.getElementById("tabTerminal").classList.toggle("tab-active", isTerminal);
    document.getElementById("tabHistory").classList.toggle("tab-active", !isTerminal);
    if (!isTerminal) { loadHistory(); refreshHistoryFilterDevices(); }
}

// -----------------------------------------------
//  Device connection
// -----------------------------------------------
function connectDevice() {
    const ip  = document.getElementById("ipInput").value.trim();
    const key = document.getElementById("apiKeyInput").value.trim();
    if (!ip || !key) { alert("Введите IP-адрес и API Key"); return; }
    updateStatus("Подключение…", "connecting");
    socket.emit("connect_device", { ip, key });
}

function disconnectDevice() {
    socket.emit("disconnect_device");
}

function sendAutotune() {
    const btn = document.getElementById("autotuneBtn");
    const sel = document.getElementById("buttonSelect");
    const key = sel.value !== "" ? parseInt(sel.value, 10) : null;
    if (key === null) { showToast("Выберите кнопку из списка", "error"); return; }
    btn.disabled = true;
    btn.textContent = "⏳ Отправка…";
    socket.emit("send_autotune", { key });
    setTimeout(() => {
        btn.disabled = false;
        btn.textContent = "🚀 Запустить Autotune";
    }, 3000);
}

// -----------------------------------------------
//  Saved devices
// -----------------------------------------------
async function loadSavedDevices() {
    try {
        const res     = await fetch("/api/devices");
        const devices = await res.json();
        const sel = document.getElementById("savedDeviceSelect");
        sel.innerHTML = "<option value=''>— выберите устройство —</option>";
        devices.forEach(({ id, name, ip }) => {
            const opt  = document.createElement("option");
            opt.value  = id;
            opt.text   = name + "  (" + ip + ")";
            sel.appendChild(opt);
        });
    } catch (e) {
        console.error("loadSavedDevices:", e);
    }
}

async function loadSavedDevice() {
    const sel = document.getElementById("savedDeviceSelect");
    const id  = sel.value;
    if (!id) { showToast("Выберите устройство из списка", "error"); return; }
    try {
        const res = await fetch("/api/devices/" + id);
        if (!res.ok) throw new Error(res.statusText);
        const dev = await res.json();
        document.getElementById("ipInput").value     = dev.ip;
        document.getElementById("apiKeyInput").value = dev.api_key;
        showToast("Загружено: " + dev.name, "success");
    } catch (e) {
        showToast("Ошибка загрузки устройства", "error");
    }
}

async function deleteSavedDevice() {
    const sel  = document.getElementById("savedDeviceSelect");
    const id   = sel.value;
    const name = sel.options[sel.selectedIndex]?.text || "";
    if (!id) { showToast("Выберите устройство", "error"); return; }
    if (!confirm("Удалить устройство «" + name + "»?")) return;
    try {
        const res = await fetch("/api/devices/" + id, { method: "DELETE" });
        if (!res.ok) throw new Error(res.statusText);
        showToast("Устройство удалено", "success");
        loadSavedDevices();
    } catch (e) {
        showToast("Ошибка удаления", "error");
    }
}

async function saveCurrentDevice() {
    const ip      = document.getElementById("ipInput").value.trim();
    const api_key = document.getElementById("apiKeyInput").value.trim();
    const name    = document.getElementById("saveNameInput").value.trim();
    if (!name)    { showToast("Введите название устройства", "error"); return; }
    if (!ip)      { showToast("IP-адрес не заполнен", "error"); return; }
    if (!api_key) { showToast("API Key не заполнен", "error"); return; }
    try {
        const res = await fetch("/api/devices", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ name, ip, api_key }),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || res.statusText);
        }
        showToast("Устройство «" + name + "» сохранено", "success");
        document.getElementById("saveNameInput").value = "";
        document.getElementById("saveAccordion").removeAttribute("open");
        loadSavedDevices();
    } catch (e) {
        showToast("Ошибка: " + e.message, "error");
    }
}

// -----------------------------------------------
//  mDNS scan
// -----------------------------------------------
async function scanMDNS() {
    updateStatus("Поиск устройств mDNS…", "connecting");
    try {
        const res     = await fetch("/scan_mdns");
        const devices = await res.json();
        const sel   = document.getElementById("mdnsSelect");
        const input = document.getElementById("ipInput");
        sel.innerHTML = "<option value=''>— выберите устройство —</option>";
        devices.forEach(({ ip, text }) => {
            const opt = document.createElement("option");
            opt.value = ip;
            opt.text  = text;
            sel.appendChild(opt);
        });
        sel.style.display   = "";
        input.style.display = "none";
        updateStatus("Найдено: " + devices.length + " устройств", "idle");
    } catch {
        updateStatus("Ошибка поиска", "error");
    }
}

function onMdnsSelect() {
    const val = document.getElementById("mdnsSelect").value;
    if (val) document.getElementById("ipInput").value = val;
}

// -----------------------------------------------
//  History
// -----------------------------------------------
async function refreshHistoryFilterDevices() {
    try {
        const [devRes, ipRes] = await Promise.all([
            fetch("/api/devices"),
            fetch("/api/results/ips"),
        ]);
        const devices = await devRes.json();
        const ips     = await ipRes.json();

        const sel = document.getElementById("historyDeviceFilter");
        const cur = sel.value;
        sel.innerHTML = "<option value=''>Все устройства</option>";

        if (devices.length) {
            const grp = document.createElement("optgroup");
            grp.label = "Сохранённые";
            devices.forEach(({ id, name, ip }) => {
                const opt = document.createElement("option");
                opt.value = "device:" + id;
                opt.text  = name + " (" + ip + ")";
                grp.appendChild(opt);
            });
            sel.appendChild(grp);
        }

        const savedIps = new Set(devices.map(d => d.ip));
        const freeIps  = ips.filter(ip => !savedIps.has(ip));
        if (freeIps.length) {
            const grp = document.createElement("optgroup");
            grp.label = "По IP";
            freeIps.forEach(ip => {
                const opt = document.createElement("option");
                opt.value = "ip:" + ip;
                opt.text  = ip;
                grp.appendChild(opt);
            });
            sel.appendChild(grp);
        }

        sel.value = cur;
    } catch (e) {
        console.error("refreshHistoryFilterDevices:", e);
    }
}

async function loadHistory() {
    const filterVal = document.getElementById("historyDeviceFilter").value;
    let url = "/api/results";
    if (filterVal.startsWith("device:")) {
        url += "?device_id=" + filterVal.slice(7);
    } else if (filterVal.startsWith("ip:")) {
        url += "?device_ip=" + encodeURIComponent(filterVal.slice(3));
    }
    try {
        const res     = await fetch(url);
        const results = await res.json();
        renderHistory(results);
    } catch (e) {
        showToast("Ошибка загрузки истории", "error");
    }
}

function renderHistory(results) {
    const empty  = document.getElementById("historyEmpty");
    const table  = document.getElementById("historyTable");
    const tbody  = document.getElementById("historyTbody");
    const count  = document.getElementById("historyCount");

    count.textContent = results.length + " " + plural(results.length, "запись", "записи", "записей");

    if (!results.length) {
        empty.style.display = "";
        table.style.display = "none";
        return;
    }

    empty.style.display = "none";
    table.style.display = "";
    tbody.innerHTML = "";

    results.forEach(r => {
        const devLabel  = r.saved_device_name || r.device_name || "—";
        const devIp     = r.device_ip || "";
        const statusCls = r.status === "Succeeded" ? "status-succeeded"
                        : r.status === "Failed"    ? "status-failed"
                        : "status-unknown";
        const statusDot = r.status === "Succeeded" ? "✓"
                        : r.status === "Failed"    ? "✗"
                        : "•";
        const kp = r.kp != null ? r.kp.toFixed(5) : "—";
        const ki = r.ki != null ? r.ki.toFixed(5) : "—";
        const kd = r.kd != null ? r.kd.toFixed(2) : "—";
        const dt = r.saved_at ? r.saved_at.replace("T"," ").slice(0,16) : r.started_at;

        const tr = document.createElement("tr");
        tr.innerHTML =
            "<td style='white-space:nowrap;font-family:JetBrains Mono,monospace;font-size:.79rem;color:var(--text-secondary);'>" + dt + "</td>" +
            "<td><div class='device-cell'><span class='device-name'>" + escHtml(devLabel) + "</span><span class='device-ip'>" + escHtml(devIp) + "</span></div></td>" +
            "<td><span class='status-pill " + statusCls + "'>" + statusDot + " " + escHtml(r.status || "Неизвестно") + "</span></td>" +
            "<td class='num-col'>" + kp + "</td>" +
            "<td class='num-col'>" + ki + "</td>" +
            "<td class='num-col'>" + kd + "</td>" +
            "<td style='white-space:nowrap;text-align:right;'>" +
            "<button class='action-btn' onclick='viewResult(" + r.id + ", event)' title='Подробнее'>🔍</button> " +
            "<button class='action-btn action-btn-del' onclick='deleteResult(" + r.id + ", event)' title='Удалить'>🗑</button>" +
            "</td>";
        tbody.appendChild(tr);
    });
}

async function viewResult(id, evt) {
    evt && evt.stopPropagation();
    try {
        const res = await fetch("/api/results/" + id);
        if (!res.ok) throw new Error(res.statusText);
        const r = await res.json();
        openResultModal(r);
    } catch (e) {
        showToast("Ошибка загрузки результата", "error");
    }
}

function openResultModal(r) {
    const devLabel = r.saved_device_name || r.device_name || r.device_ip;
    const dt       = (r.saved_at || r.started_at || "").replace("T", " ").slice(0, 16);

    document.getElementById("modalTitle").textContent    = "Результат Autotune — " + devLabel;
    document.getElementById("modalSubtitle").textContent = dt + (r.device_ip ? "  •  " + r.device_ip : "");

    let rulesHtml = "";
    if (r.rules && r.rules.length) {
        rulesHtml = "<div class='section-label'>Альтернативные правила</div>" +
            "<table class='rules-table'><thead><tr><th>Правило</th><th>kp</th><th>ki</th><th>kd</th></tr></thead><tbody>" +
            r.rules.map(ru =>
                "<tr><td>" + escHtml(ru.name) + "</td><td>" + ru.kp.toFixed(5) + "</td><td>" + ru.ki.toFixed(5) + "</td><td>" + ru.kd.toFixed(5) + "</td></tr>"
            ).join("") +
            "</tbody></table>";
    }

    document.getElementById("modalBody").innerHTML =
        "<div class='pid-cards'>" +
        "<div class='pid-card'><div class='pid-card-label'>kp</div><div class='pid-card-value'>" + (r.kp != null ? r.kp.toFixed(5) : "—") + "</div></div>" +
        "<div class='pid-card'><div class='pid-card-label'>ki</div><div class='pid-card-value'>" + (r.ki != null ? r.ki.toFixed(5) : "—") + "</div></div>" +
        "<div class='pid-card'><div class='pid-card-label'>kd</div><div class='pid-card-value'>" + (r.kd != null ? r.kd.toFixed(2) : "—") + "</div></div>" +
        "</div>" +
        rulesHtml +
        "<div class='section-label' style='margin-bottom:8px;'>Лог Autotune</div>" +
        "<pre class='raw-log'>" + escHtml(r.raw_text || "") + "</pre>";

    document.getElementById("resultModal").style.display = "flex";
}

function closeResultModal() {
    document.getElementById("resultModal").style.display = "none";
}

function closeModal(evt) {
    if (evt.target === document.getElementById("resultModal")) closeResultModal();
}

async function deleteResult(id, evt) {
    evt && evt.stopPropagation();
    if (!confirm("Удалить этот результат из истории?")) return;
    try {
        const res = await fetch("/api/results/" + id, { method: "DELETE" });
        if (!res.ok) throw new Error(res.statusText);
        showToast("Результат удалён", "success");
        loadHistory();
        refreshHistoryFilterDevices();
    } catch (e) {
        showToast("Ошибка удаления", "error");
    }
}

// -----------------------------------------------
//  UI helpers
// -----------------------------------------------
function toggleInputMode() {
    const input = document.getElementById("ipInput");
    const sel   = document.getElementById("mdnsSelect");
    if (input.style.display === "none") {
        input.style.display = "";
        sel.style.display   = "none";
    } else {
        input.style.display = "none";
        sel.style.display   = "";
    }
}

function togglePassword() {
    const input  = document.getElementById("apiKeyInput");
    const btn    = document.getElementById("togglePwdBtn");
    const hidden = input.type === "password";
    input.type   = hidden ? "text" : "password";
    btn.textContent = hidden ? "🔒" : "👁";
}

function toggleColor() {
    logColor = logColor === "green" ? "white" : "green";
    document.getElementById("colorBtn").textContent =
        logColor === "green" ? "🎨 Зелёный" : "🎨 Белый";
    document.querySelectorAll(".log-text-green, .log-text-white").forEach(el => {
        el.className = el.className.replace(/log-text-(green|white)/, "log-text-" + logColor);
    });
}

function clearLogs() {
    document.getElementById("terminal").innerHTML = "";
    lineCount = 0;
    updateLineCount();
    showPlaceholder();
}

async function downloadJSON() {
    try {
        const res  = await fetch("/get_json");
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href     = url;
        a.download = "pid_results_" + new Date().toISOString().slice(0, 10) + ".json";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    } catch {
        alert("Логов пока нет или ошибка загрузки");
    }
}

// -----------------------------------------------
//  Status badge
// -----------------------------------------------
function updateStatus(message, state) {
    const badge = document.getElementById("statusBadge");
    const text  = document.getElementById("statusText");
    ["idle","connecting","connected","disconnected","error"].forEach(s =>
        badge.classList.remove("status-" + s)
    );
    badge.classList.add("status-" + state);
    text.textContent = message;

    const connected = state === "connected";
    const loading   = state === "connecting";

    document.getElementById("connectBtn").disabled    = connected || loading;
    document.getElementById("disconnectBtn").disabled = !connected;
    document.getElementById("autotuneBtn").disabled   = !connected;
    if (!connected) {
        const sel = document.getElementById("buttonSelect");
        sel.innerHTML = "<option value=''>— подключитесь к устройству —</option>";
        sel.disabled = true;
    }
}

// -----------------------------------------------
//  Terminal
// -----------------------------------------------
function addLogLine(text, level) {
    const terminal = document.getElementById("terminal");
    const time     = new Date().toLocaleTimeString("ru-RU");

    const line     = document.createElement("div");
    line.className = "log-line";
    line.dataset.level = level;

    const timeSpan = document.createElement("span");
    timeSpan.className   = "log-time";
    timeSpan.textContent = time;

    const textSpan = document.createElement("span");
    textSpan.className   = "log-text log-text-" + logColor;
    textSpan.textContent = text;

    line.appendChild(timeSpan);
    line.appendChild(textSpan);
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;

    lineCount++;
    updateLineCount();
}

function updateLineCount() {
    document.getElementById("logCount").textContent =
        lineCount + " " + plural(lineCount, "строка", "строки", "строк");
}

function hidePlaceholder() {
    const ph = document.getElementById("terminalPlaceholder");
    if (ph) ph.remove();
}

function showPlaceholder() {
    const terminal = document.getElementById("terminal");
    const ph = document.createElement("div");
    ph.id        = "terminalPlaceholder";
    ph.className = "terminal-placeholder";
    ph.textContent = "Подключитесь к устройству, чтобы начать получать логи…";
    terminal.appendChild(ph);
}

// -----------------------------------------------
//  Toast
// -----------------------------------------------
let _toastTimer = null;

function showToast(msg, type) {
    type = type || "success";
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className   = "toast toast-" + type + " show";
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
}

// -----------------------------------------------
//  Utils
// -----------------------------------------------
function plural(n, one, two, five) {
    const mod10  = n % 10;
    const mod100 = n % 100;
    if (mod100 >= 11 && mod100 <= 14) return five;
    if (mod10  === 1)                 return one;
    if (mod10  >= 2 && mod10  <= 4)  return two;
    return five;
}

function escHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
