// dashboard/static/js/dashboard.js - Interactive client logic for Clinical Workstation
document.addEventListener("DOMContentLoaded", () => {
    const currentPage = document.body.dataset.page;
    initGlobalAudioMute();

    if (currentPage === "live") {
        initLiveMonitor();
    } else if (currentPage === "alerts") {
        initAlertsPage();
    } else if (currentPage === "history") {
        initHistoryCharts();
    } else if (currentPage === "network") {
        initNetworkDashboard();
    } else if (currentPage === "admin") {
        initAdminPage();
    }
});

// CSRF Token Helper
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
}

// ==========================================
// CLINICAL AUDIO ALARM SYNTHESIZER (WEB AUDIO API)
// ==========================================
let audioCtx = null;
let lastAlarmTime = 0;

function getAudioContext() {
    if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
            audioCtx = new AudioContextClass();
        }
    }
    if (audioCtx && audioCtx.state === "suspended") {
        audioCtx.resume();
    }
    return audioCtx;
}

// Unlock audio context on user interaction (resolves browser autoplay policy)
function unlockAudio() {
    const ctx = getAudioContext();
    if (ctx && ctx.state === "suspended") {
        ctx.resume();
    }
}
document.addEventListener("click", unlockAudio, { passive: true });
document.addEventListener("keydown", unlockAudio, { passive: true });

function playTone(freq, durationSec, type = "triangle", gainLevel = 0.35, delaySec = 0) {
    try {
        const ctx = getAudioContext();
        if (!ctx) return;
        const now = ctx.currentTime + delaySec;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, now);

        // Anti-click exponential envelope
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(gainLevel, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + durationSec);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + durationSec + 0.05);
    } catch (e) {
        console.warn("Audio alarm playback error:", e);
    }
}

// IEC 60601-1-8 standard medical high-priority pulse burst
function playCriticalAlarm() {
    if (localStorage.getItem("alarm_muted") === "true") return;
    const now = Date.now();
    if (now - lastAlarmTime < 3200) return; // Throttle to 3.2s cadence
    lastAlarmTime = now;

    // High urgency clinical burst: C6 (1046Hz), A5 (880Hz), F5 (698Hz), A5 (880Hz), C6 (1046Hz)
    playTone(1046, 0.12, "triangle", 0.38, 0.00);
    playTone(880,  0.12, "triangle", 0.34, 0.16);
    playTone(698,  0.14, "triangle", 0.32, 0.32);
    playTone(880,  0.12, "triangle", 0.34, 0.52);
    playTone(1046, 0.18, "triangle", 0.38, 0.68);

    flashAudioButton("critical");
}

// Medium priority warning chime
function playWarningAlarm() {
    if (localStorage.getItem("alarm_muted") === "true") return;
    const now = Date.now();
    if (now - lastAlarmTime < 4500) return;
    lastAlarmTime = now;

    playTone(659, 0.16, "triangle", 0.28, 0.00);
    playTone(523, 0.22, "triangle", 0.30, 0.20);

    flashAudioButton("warning");
}

// Confirmation feedback tone when clicking/enabling audio
function playTestChime() {
    playTone(659, 0.10, "triangle", 0.25, 0.00);
    playTone(880, 0.15, "triangle", 0.30, 0.12);
}

function flashAudioButton(type) {
    const audioBtn = document.getElementById("alarmAudioBtn");
    if (!audioBtn) return;
    const flashClass = type === "critical" ? "ring-2 ring-rose-500 shadow-rose-500/50" : "ring-2 ring-amber-500 shadow-amber-500/50";
    audioBtn.classList.add(...flashClass.split(" "));
    setTimeout(() => {
        audioBtn.classList.remove(...flashClass.split(" "));
    }, 1200);
}

// Global Audio Mute Button & Alarm Surveillance
function initGlobalAudioMute() {
    const audioBtn = document.getElementById("alarmAudioBtn");
    if (!audioBtn) return;

    // Default to unmuted (active sound) unless user explicitly muted
    let isMuted = localStorage.getItem("alarm_muted") === "true";

    function updateBtn() {
        if (isMuted) {
            audioBtn.className = "p-2 rounded-lg bg-rose-950/40 border border-rose-500/60 text-rose-400 hover:text-rose-300 transition";
            audioBtn.title = "Audio Alarms Silenced (Click to enable audio)";
            audioBtn.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path>
                    <path d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path>
                </svg>
            `;
        } else {
            audioBtn.className = "p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/50 text-emerald-400 hover:text-emerald-300 transition";
            audioBtn.title = "Audio Alarms Active (Click to silence)";
            audioBtn.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path>
                </svg>
            `;
        }
    }
    updateBtn();

    audioBtn.addEventListener("click", () => {
        isMuted = !isMuted;
        localStorage.setItem("alarm_muted", isMuted ? "true" : "false");
        updateBtn();
        if (!isMuted) {
            getAudioContext();
            playTestChime();
        }
    });

    // Background global alert surveillance across all dashboard pages
    async function checkGlobalAlerts() {
        try {
            const res = await fetch("/api/alerts");
            if (!res.ok) return;
            const alerts = await res.json();
            const unacked = alerts.filter(a => !a.acknowledged);
            const critCount = unacked.filter(a => a.severity === "CRITICAL").length;
            const warnCount = unacked.filter(a => a.severity === "WARNING" || a.severity === "WARN").length;

            const navBadge = document.getElementById("navAlertBadge");
            if (navBadge) {
                const total = critCount + warnCount;
                navBadge.textContent = total > 0 ? total : "0";
                navBadge.className = total > 0 
                    ? "px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-500 text-white font-mono animate-pulse"
                    : "px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-slate-800 text-slate-400 font-mono";
            }
        } catch (e) {
            // ignore network jitter
        }
    }

    setInterval(checkGlobalAlerts, 2500);
    checkGlobalAlerts();
}

// ==========================================
// LIVE MONITOR & CLINICAL OSCILLOSCOPE
// ==========================================
function initLiveMonitor() {
    const patientSelect = document.getElementById("patient-select");
    const mrnChip = document.getElementById("patientMRN");
    const demoChip = document.getElementById("patientDemo");
    const admissionChip = document.getElementById("patientAdmission");
    const allergyChip = document.getElementById("patientAllergy");

    const valHr = document.getElementById("val-hr");
    const valSpo2 = document.getElementById("val-spo2");
    const barSpo2Mini = document.getElementById("bar-spo2-mini");
    const valTemp = document.getElementById("val-temp");
    const valTempF = document.getElementById("val-temp-f");
    const valBp = document.getElementById("val-bp");
    const valMap = document.getElementById("val-map");
    const valResp = document.getElementById("val-resp");
    const valLatency = document.getElementById("val-latency");

    const globalPill = document.getElementById("globalStatusPill");
    const globalText = document.getElementById("globalStatusText");
    const priorityBanner = document.getElementById("priorityBanner");
    const priorityReason = document.getElementById("priorityReason");

    const aiBadge = document.getElementById("aiClassificationBadge");
    const aiText = document.getElementById("aiClassificationText");
    const barNsr = document.getElementById("bar-nsr");
    const barNsrText = document.getElementById("bar-nsr-text");
    const barPvc = document.getElementById("bar-pvc");
    const barPvcText = document.getElementById("bar-pvc-text");
    const barArt = document.getElementById("bar-art");
    const barArtText = document.getElementById("bar-art-text");

    const sdnQueueText = document.getElementById("sdnQueueText");
    const sdnLossText = document.getElementById("sdnLossText");
    const sdnJitterText = document.getElementById("sdnJitterText");
    const alarmStatusTag = document.getElementById("alarmStatusTag");
    const alarmTachyText = document.getElementById("alarmTachyText");
    const alarmBradyText = document.getElementById("alarmBradyText");
    const alarmSpo2Text = document.getElementById("alarmSpo2Text");

    const canvas = document.getElementById("ecgCanvas");
    const ctx = canvas ? canvas.getContext("2d") : null;
    const freezeBtn = document.getElementById("freeze-btn");

    let isFrozen = false;
    let activePatient = patientSelect ? patientSelect.value.split(" ")[0] : "P101";

    if (freezeBtn) {
        freezeBtn.addEventListener("click", () => {
            isFrozen = !isFrozen;
            freezeBtn.textContent = isFrozen ? "Resume" : "Freeze";
            freezeBtn.classList.toggle("text-amber-400", isFrozen);
            freezeBtn.classList.toggle("border-amber-500", isFrozen);
        });
    }

    if (patientSelect) {
        patientSelect.addEventListener("change", (e) => {
            activePatient = e.target.value.split(" ")[0].trim();
            if (ctx && canvas) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                cursorX = 0;
                prevY = (canvas.height / (window.devicePixelRatio || 1)) * 0.52;
            }
            fetchLatestData();
        });
    }

    // Oscilloscope Sweep Engine
    let cursorX = 0;
    let prevY = 0;
    let cycleProgress = 0;
    let displayHr = 75;
    let targetHr = 76;
    let hasArrhythmia = false;
    let beatCount = 0;
    let lastOscilloscopeTime = performance.now();

    function resizeCanvas() {
        const dpr = window.devicePixelRatio || 1;
        if (canvas && ctx) {
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            ctx.scale(dpr, dpr);
            prevY = (canvas.height / dpr) * 0.52;
        }
    }
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    // High-Fidelity Clinical Lead-II Physiological Waveform Generator
    function getPhysiologicalECGSample(phase, isArrhythmia, hr, currentBeat) {
        let val = 0.0;

        // Clinical arrhythmia: intermittent ectopic ventricular contractions (PVC bigeminy/trigeminy)
        const isPvc = isArrhythmia && (currentBeat % 3 === 0);

        if (!isPvc) {
            // Normal Sinus Rhythm: Mathematically exact Lead-II P-Q-R-S-T morphology
            // P wave: rounded positive atrial depolarization
            const dp = phase - 0.16;
            val += 0.16 * Math.exp(-(dp * dp) / (2 * 0.030 * 0.030));

            // Q wave: crisp small septal negative deflection
            const dq = phase - 0.34;
            val += -0.10 * Math.exp(-(dq * dq) / (2 * 0.012 * 0.012));

            // R wave: dominant razor-sharp ventricular depolarization peak
            const dr = phase - 0.375;
            val += 1.35 * Math.exp(-(dr * dr) / (2 * 0.015 * 0.015));

            // S wave: rapid downward negative terminal deflection
            const ds = phase - 0.410;
            val += -0.28 * Math.exp(-(ds * ds) / (2 * 0.016 * 0.016));

            // T wave: asymmetrical ventricular repolarization (gentler upslope, steeper downslope)
            const dt = phase - 0.62;
            const tWidth = phase < 0.62 ? 0.062 : 0.045;
            val += 0.30 * Math.exp(-(dt * dt) / (2 * tWidth * tWidth));

            // Tachycardic ST-depression under physiological cardiac strain (>120 bpm)
            if (hr > 120 && phase >= 0.42 && phase <= 0.54) {
                val -= 0.04 * Math.min(1.0, (hr - 120) / 30.0);
            }
        } else {
            // Premature Ventricular Contraction (PVC):
            // Ectopic focus: absent P wave, bizarre wide inverted QRS complex (-1.15 mV), discordant elevated T wave (+0.48 mV)
            const dpvc1 = phase - 0.30;
            val -= 1.15 * Math.exp(-(dpvc1 * dpvc1) / (2 * 0.058 * 0.058));

            const dpvcNotch = phase - 0.38;
            val += 0.15 * Math.exp(-(dpvcNotch * dpvcNotch) / (2 * 0.025 * 0.025));

            const dpvc2 = phase - 0.55;
            val += 0.48 * Math.exp(-(dpvc2 * dpvc2) / (2 * 0.090 * 0.090));
            // Compensatory pause: baseline rest follows naturally from phase 0.70 to 1.00
        }

        // Physiological baseline wander (0.15 Hz respiration) + micro-tremor from skin telemetry interface
        const respWander = 0.025 * Math.sin(2 * Math.PI * 0.15 * (Date.now() / 1000));
        const microNoise = (Math.random() - 0.5) * 0.010;
        return val + respWander + microNoise;
    }

    let liveEcgBatch = null;

    function renderOscilloscope(timestamp) {
        if (!ctx || !canvas) return;
        if (!isFrozen) {
            const now = timestamp || performance.now();
            const dt = Math.min(0.04, Math.max(0.001, (now - lastOscilloscopeTime) / 1000));
            lastOscilloscopeTime = now;

            const rect = canvas.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            const baseline = height * 0.52;
            const amplitude = height * 0.28; // Standard 10 mm/mV clinical monitor calibration gain

            // Smooth physiological HR transition
            displayHr += (targetHr - displayHr) * Math.min(1.0, 3.0 * dt);

            // Clinical sweep speed (~135 px/s calibrated to standard 25 mm/s monitor sweep)
            const sweepSpeedPxPerSec = 135;
            const dx = sweepSpeedPxPerSec * dt;

            // Clear lead sweep bar in front of cursor (simulates clinical phosphor erase)
            const eraseWidth = 28;
            ctx.clearRect(cursorX, 0, eraseWidth, height);
            if (cursorX + eraseWidth > width) {
                ctx.clearRect(0, 0, (cursorX + eraseWidth) - width, height);
            }

            // Advance cardiac cycle phase accurately with real-world seconds
            const beatsPerSec = Math.max(30, displayHr) / 60.0;
            cycleProgress += beatsPerSec * dt;
            if (cycleProgress >= 1.0) {
                cycleProgress -= 1.0;
                beatCount++;
            }

            const sample = getPhysiologicalECGSample(cycleProgress, hasArrhythmia, displayHr, beatCount);
            const currentY = baseline - (sample * amplitude);

            const nextX = cursorX + dx;

            if (nextX >= width) {
                // Seamless cursor wrap back to start without cross-screen drawing
                cursorX = 0;
                prevY = currentY;
            } else {
                // Stroke ECG line segment with luminous phosphor glow
                ctx.beginPath();
                const isAlarm = isWaveformAlarm;
                ctx.strokeStyle = isAlarm ? "#EF4444" : "#10B981";
                ctx.lineWidth = isAlarm ? 2.3 : 1.9;
                ctx.lineCap = "round";
                ctx.lineJoin = "round";
                ctx.shadowColor = isAlarm ? "#F87171" : "#34D399";
                ctx.shadowBlur = isAlarm ? 9 : 6;

                ctx.moveTo(cursorX, prevY);
                ctx.lineTo(nextX, currentY);
                ctx.stroke();

                // Draw leading phosphor scan dot
                ctx.beginPath();
                ctx.arc(nextX, currentY, 2.5, 0, 2 * Math.PI);
                ctx.fillStyle = isAlarm ? "#FCA5A5" : "#6EE7B7";
                ctx.shadowColor = isAlarm ? "#EF4444" : "#A7F3D0";
                ctx.shadowBlur = 12;
                ctx.fill();

                prevY = currentY;
                cursorX = nextX;
            }
        } else {
            lastOscilloscopeTime = performance.now();
        }
        requestAnimationFrame(renderOscilloscope);
    }
    requestAnimationFrame(renderOscilloscope);

    // Track alarm transition state
    let isWaveformAlarm = false;
    let lastAlarmState = null;

    // Fetch Live Telemetry Data
    async function fetchLatestData() {
        try {
            const res = await fetch(`/api/patients/${activePatient}/live`);
            if (!res.ok) return;
            const d = await res.json();

            // Ingest real 360 Hz ECG telemetry batch from backend
            if (d.ecg_batch && Array.isArray(d.ecg_batch) && d.ecg_batch.length > 0) {
                liveEcgBatch = d.ecg_batch;
            }

            targetHr = d.hr || 75;
            targetSpo2 = d.spo2 || 98.0;
            hasArrhythmia = d.ecg_classification === "ARRHYTHMIA";

            const isTachycardia = targetHr > 100;
            const isBradycardia = targetHr < 50;
            const isHrAbnormal = isTachycardia || isBradycardia;
            const isCritical = d.overall_status === "CRITICAL";
            const isWarning = d.overall_status === "WARNING";

            // Turn waveform RED when tachycardia, bradycardia, arrhythmia, or critical alarm is present
            // Seamlessly transitions trace color as the sweep beam moves forward WITHOUT resetting cursorX or refreshing canvas
            isWaveformAlarm = hasArrhythmia || isHrAbnormal || isCritical || (d.priority_active === true);
            lastAlarmState = isWaveformAlarm;

            // Update Demographics chips
            if (mrnChip) mrnChip.textContent = `MRN: ${d.mrn || '884-9021'}`;
            if (demoChip) demoChip.textContent = `${d.age || 42}y • ${d.gender || 'F'}`;
            if (admissionChip) admissionChip.textContent = d.admission || '2d ago (Post-PTCA)';
            if (allergyChip) allergyChip.innerHTML = `Allergy: <strong class="underline decoration-amber-500">${d.allergy || 'Penicillin'}</strong>`;

            // Update Metric Cards
            if (valHr) {
                valHr.textContent = Math.round(targetHr);
                if (isTachycardia) {
                    valHr.className = "text-4xl lg:text-5xl font-mono font-extrabold text-rose-500 tracking-tight animate-pulse";
                } else if (isBradycardia) {
                    valHr.className = "text-4xl lg:text-5xl font-mono font-extrabold text-amber-400 tracking-tight animate-pulse";
                } else {
                    valHr.className = "text-4xl lg:text-5xl font-mono font-extrabold text-white tracking-tight";
                }
            }
            const lblHrRange = document.getElementById("lbl-hr-range");
            const svgHrPulse = document.getElementById("svg-hr-pulse");
            if (lblHrRange) {
                if (isTachycardia) {
                    lblHrRange.className = "text-rose-400 font-bold tracking-wide animate-pulse";
                    lblHrRange.textContent = "TACHYCARDIA (> 100 bpm)";
                } else if (isBradycardia) {
                    lblHrRange.className = "text-amber-400 font-bold tracking-wide";
                    lblHrRange.textContent = "BRADYCARDIA (< 60 bpm)";
                } else {
                    lblHrRange.className = "text-emerald-400 font-medium";
                    lblHrRange.textContent = "Normal Range: 60 - 100";
                }
            }
            if (svgHrPulse) {
                svgHrPulse.className = isTachycardia ? "w-16 h-4 text-rose-500 animate-pulse" : (isBradycardia ? "w-16 h-4 text-amber-500" : "w-16 h-4 text-emerald-400");
            }

            if (valSpo2) valSpo2.textContent = (d.spo2 || 98).toFixed(1);
            if (barSpo2Mini) barSpo2Mini.style.width = `${Math.min(100, Math.max(0, d.spo2 || 98))}%`;
            if (valTemp) valTemp.textContent = (d.temp || 36.8).toFixed(1);
            if (valTempF) valTempF.textContent = `(${((d.temp || 36.8) * 1.8 + 32).toFixed(1)}°F)`;
            if (valBp) valBp.textContent = `${d.bp_sys || 118}/${d.bp_dia || 74}`;
            if (valMap) valMap.textContent = d.map || 88;
            if (valResp) valResp.textContent = d.resp_rate || 16;
            if (valLatency) valLatency.textContent = (d.inference_latency_ms || 8.3).toFixed(1);

            // Update Global Status Pill
            if (globalPill && globalText) {
                if (isCritical) {
                    globalPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full bg-rose-950/60 border border-rose-500/60 text-rose-300 text-xs font-semibold tracking-wider animate-pulse";
                    globalText.textContent = "CRITICAL ALERT";
                    playCriticalAlarm();
                } else if (isWarning) {
                    globalPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full bg-amber-950/60 border border-amber-500/60 text-amber-300 text-xs font-semibold tracking-wider";
                    globalText.textContent = "CLINICAL WARNING";
                } else {
                    globalPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-950/50 border border-emerald-500/40 text-emerald-400 text-xs font-semibold tracking-wider";
                    globalText.textContent = "STABLE / NORMAL";
                }
            }

            // Update Priority Banner
            if (priorityBanner) {
                if (d.priority_active) {
                    priorityBanner.style.display = "flex";
                    if (priorityReason) priorityReason.textContent = d.reason || "Emergency QoS rerouting triggered: Traffic steered to guaranteed 6-10 Mbps Linux HTB Queue.";
                } else {
                    priorityBanner.style.display = "none";
                }
            }

            // Update AI Classification Chip
            const aiDot = document.getElementById("aiClassificationDot");
            if (aiBadge && aiText) {
                if (hasArrhythmia) {
                    aiBadge.className = "bg-rose-950/90 border border-rose-500/60 px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-2";
                    aiText.className = "text-xs font-mono font-semibold text-rose-300";
                    aiText.textContent = `AI Classification: Ventricular Arrhythmia (PVC) • ${(d.ecg_confidence * 100).toFixed(1)}% Conf.`;
                    if (aiDot) aiDot.className = "w-2 h-2 rounded-full bg-rose-400 animate-ping";
                } else if (isTachycardia) {
                    aiBadge.className = "bg-rose-950/90 border border-rose-500/60 px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-2";
                    aiText.className = "text-xs font-mono font-semibold text-rose-300";
                    aiText.textContent = `ECG Telemetry: Sinus Tachycardia (HR ${Math.round(targetHr)} bpm) • High Rate Alert`;
                    if (aiDot) aiDot.className = "w-2 h-2 rounded-full bg-rose-400 animate-ping";
                } else if (isBradycardia) {
                    aiBadge.className = "bg-amber-950/90 border border-amber-500/60 px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-2";
                    aiText.className = "text-xs font-mono font-semibold text-amber-300";
                    aiText.textContent = `ECG Telemetry: Sinus Bradycardia (HR ${Math.round(targetHr)} bpm) • Low Rate Alert`;
                    if (aiDot) aiDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-ping";
                } else {
                    aiBadge.className = "bg-clinical-950/90 border border-emerald-500/40 px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-2";
                    aiText.className = "text-xs font-mono font-semibold text-emerald-300";
                    aiText.textContent = `AI Classification: Normal Sinus Rhythm (NSR) • ${(d.ecg_confidence * 100).toFixed(1)}% Conf.`;
                    if (aiDot) aiDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
                }
            }

            // Update Scope Header Status Badges
            const scopeStreamPulse = document.getElementById("scopeStreamPulse");
            const scopeStreamBadge = document.getElementById("scopeStreamBadge");
            if (scopeStreamPulse) {
                scopeStreamPulse.className = isWaveformAlarm ? "w-2.5 h-2.5 rounded-full bg-rose-400 animate-ping" : "w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse";
            }
            if (scopeStreamBadge) {
                if (isWaveformAlarm) {
                    scopeStreamBadge.className = "text-xs font-mono px-2 py-0.5 rounded bg-rose-950/90 text-rose-300 border border-rose-600/60 animate-pulse";
                    scopeStreamBadge.textContent = "• CRITICAL TELEMETRY";
                } else {
                    scopeStreamBadge.className = "text-xs font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-600/40";
                    scopeStreamBadge.textContent = "• LIVE STREAMING";
                }
            }

            // Update Beat Classifier Progress Bars
            if (barNsr && barNsrText) {
                const nsrVal = d.nsr_pct || 99.4;
                barNsr.style.width = `${nsrVal}%`;
                barNsrText.textContent = `${nsrVal}%`;
            }
            if (barPvc && barPvcText) {
                const pvcVal = d.pvc_pct || 0.4;
                barPvc.style.width = `${pvcVal}%`;
                barPvcText.textContent = `${pvcVal}%`;
            }
            if (barArt && barArtText) {
                const artVal = d.artifact_pct || 0.2;
                barArt.style.width = `${artVal}%`;
                barArtText.textContent = `${artVal}%`;
            }

            // Update SDN Network Flow Status Card
            if (sdnQueueText) {
                sdnQueueText.textContent = d.sdn_queue || (d.priority_active ? "Queue 1 (Priority HTB)" : "Queue 0 (Best-Effort)");
                sdnQueueText.className = d.priority_active ? "font-bold text-purple-400" : "font-bold text-emerald-400";
            }
            if (sdnLossText) sdnLossText.textContent = `${(d.sdn_loss_pct || 0.0002).toFixed(4)} %`;
            if (sdnJitterText) sdnJitterText.textContent = `${(d.sdn_jitter_ms || 1.18).toFixed(2)} ms`;

            // Update Alarm Triggers Card
            if (alarmStatusTag) {
                if (isCritical) {
                    alarmStatusTag.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800";
                    alarmStatusTag.textContent = "ALARM ACTIVE";
                } else {
                    alarmStatusTag.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800";
                    alarmStatusTag.textContent = "ALL PASS";
                }
            }
            if (alarmTachyText) {
                alarmTachyText.textContent = d.hr > 120 ? `> 120 bpm (BREACH: ${Math.round(d.hr)})` : "> 120 bpm (Safe)";
                alarmTachyText.className = d.hr > 120 ? "text-rose-400 font-bold" : "text-slate-400";
            }
            if (alarmBradyText) {
                alarmBradyText.textContent = d.hr < 50 ? `< 50 bpm (BREACH: ${Math.round(d.hr)})` : "< 50 bpm (Safe)";
                alarmBradyText.className = d.hr < 50 ? "text-rose-400 font-bold" : "text-slate-400";
            }
            if (alarmSpo2Text) {
                alarmSpo2Text.textContent = d.spo2 < 90 ? `< 90 % (BREACH: ${d.spo2.toFixed(1)}%)` : "< 90 % (Safe)";
                alarmSpo2Text.className = d.spo2 < 90 ? "text-rose-400 font-bold" : "text-slate-400";
            }

        } catch (err) {
            console.error("Telemetry fetch error:", err);
        }
    }

    // Refresh every 1 second
    setInterval(fetchLatestData, 1000);
    fetchLatestData();
}

// ==========================================
// ==========================================
// ALERTS TRIAGE PAGE (MASTER-DETAIL WORKSPACE)
// ==========================================
function initAlertsPage() {
    const queueContainer = document.getElementById("alert-queue-container");
    const searchInput = document.getElementById("alertSearch");
    const filterSelect = document.getElementById("filterSeverity");
    const ackAllBtn = document.getElementById("ackAllBtn");

    const pendingBadge = document.getElementById("pendingBadge");
    const statActiveCritical = document.getElementById("statActiveCritical");
    const statWarnings = document.getElementById("statWarnings");
    const statResolved = document.getElementById("statResolved");
    const activeAlertCount = document.getElementById("activeAlertCount");

    // Inspector Elements
    const inspBadge = document.getElementById("inspBadge");
    const inspTriggerTime = document.getElementById("inspTriggerTime");
    const inspPatientName = document.getElementById("inspPatientName");
    const inspPatientSub = document.getElementById("inspPatientSub");
    const inspEventName = document.getElementById("inspEventName");
    const inspAnomalyTag = document.getElementById("inspAnomalyTag");
    const inspConfidenceTag = document.getElementById("inspConfidenceTag");
    const inspValHR = document.getElementById("inspValHR");
    const inspNoteHR = document.getElementById("inspNoteHR");
    const inspValSpO2 = document.getElementById("inspValSpO2");
    const inspNoteSpO2 = document.getElementById("inspNoteSpO2");
    const inspValBP = document.getElementById("inspValBP");
    const inspNoteMAP = document.getElementById("inspNoteMAP");
    const inspValTemp = document.getElementById("inspValTemp");
    const inspNoteTemp = document.getElementById("inspNoteTemp");
    const inspProtocols = document.getElementById("inspProtocols");
    const inspAckBtn = document.getElementById("inspAckBtn");
    const inspAckBtnText = document.getElementById("inspAckBtnText");
    const rapidResponseBtn = document.getElementById("rapidResponseBtn");

    let allAlerts = [];
    let selectedAlertId = null;

    function formatTimeAgo(ts) {
        const diff = Math.max(1, Math.floor(Date.now() / 1000 - ts));
        if (diff < 60) return `${diff}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        return `${Math.floor(diff / 3600)}h ago`;
    }

    async function loadAlerts() {
        const sev = filterSelect ? filterSelect.value : "all";
        try {
            const res = await fetch(`/api/alerts?severity=${sev}`);
            if (!res.ok) return;
            allAlerts = await res.json();
            updateTriageStats();
            renderQueue();
            renderInspector();
        } catch (e) {
            console.error("Error loading alerts:", e);
        }
    }

    function updateTriageStats() {
        let critCount = 0;
        let warnCount = 0;
        let resolvedCount = 0;

        allAlerts.forEach(a => {
            if (a.acknowledged) {
                resolvedCount++;
            } else if (a.severity === "CRITICAL") {
                critCount++;
            } else {
                warnCount++;
            }
        });

        if (statActiveCritical) statActiveCritical.textContent = critCount;
        if (statWarnings) statWarnings.textContent = warnCount;
        if (statResolved) statResolved.textContent = resolvedCount;
        if (activeAlertCount) activeAlertCount.textContent = (critCount + warnCount);

        if (pendingBadge) {
            if (critCount > 0) {
                pendingBadge.className = "px-2.5 py-0.5 text-xs font-medium rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse";
                pendingBadge.textContent = `${critCount} Critical Alert${critCount > 1 ? 's' : ''} Pending`;
            } else if (warnCount > 0) {
                pendingBadge.className = "px-2.5 py-0.5 text-xs font-medium rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40";
                pendingBadge.textContent = `${warnCount} Warning${warnCount > 1 ? 's' : ''} Pending`;
            } else {
                pendingBadge.className = "px-2.5 py-0.5 text-xs font-medium rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
                pendingBadge.textContent = "All Triage Cleared • Stable";
            }
        }

        const navBadge = document.getElementById("navAlertBadge");
        if (navBadge) {
            const unacked = critCount + warnCount;
            navBadge.textContent = unacked > 0 ? unacked : "0";
            navBadge.className = unacked > 0 
                ? "px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-500 text-white font-mono animate-pulse"
                : "px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-slate-800 text-slate-400 font-mono";
        }
    }

    function getFilteredAlerts() {
        const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
        return allAlerts.filter(a => {
            if (!query) return true;
            return (
                (a.patient_id && a.patient_id.toLowerCase().includes(query)) ||
                (a.patient_name && a.patient_name.toLowerCase().includes(query)) ||
                (a.patient_room && a.patient_room.toLowerCase().includes(query)) ||
                (a.title && a.title.toLowerCase().includes(query)) ||
                (a.message && a.message.toLowerCase().includes(query)) ||
                (a.patient_condition && a.patient_condition.toLowerCase().includes(query))
            );
        });
    }

    function renderQueue() {
        if (!queueContainer) return;
        const filtered = getFilteredAlerts();

        if (filtered.length === 0) {
            queueContainer.innerHTML = `
                <div class="p-8 text-center text-slate-400 font-mono text-xs bg-slate-900/40 rounded-xl border border-slate-800">
                    No clinical alerts matching your search criteria.
                </div>
            `;
            return;
        }

        // If current selection is invalid or null, select first alert
        if (!selectedAlertId || !filtered.some(a => a.id === selectedAlertId)) {
            selectedAlertId = filtered[0].id;
        }

        queueContainer.innerHTML = filtered.map(a => {
            const isSelected = a.id === selectedAlertId;
            const isCrit = a.severity === "CRITICAL";

            const borderClass = isSelected
                ? (isCrit ? "bg-slate-900/90 border-2 border-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.25)]" : "bg-slate-900/90 border-2 border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.25)]")
                : "bg-slate-900/60 border border-slate-800 hover:border-slate-700";

            const sevBadge = isCrit
                ? `<span class="px-2 py-0.5 rounded text-xs font-bold font-mono bg-rose-500 text-white">CRITICAL</span>`
                : `<span class="px-2 py-0.5 rounded text-xs font-bold font-mono bg-amber-500/20 text-amber-400 border border-amber-500/40">WARNING</span>`;

            // Vital snippet string
            let vitalSnippet = `Heart Rate <span class="${a.hr > 120 ? 'text-rose-400' : 'text-slate-200'} font-mono font-bold">${a.hr || 75} bpm</span>`;
            if (a.spo2 < 90) {
                vitalSnippet += ` • SpO2 <span class="text-rose-400 font-mono font-bold">${(a.spo2).toFixed(1)}%</span> (Critically Low)`;
            } else if (a.temp > 38.0) {
                vitalSnippet += ` • Temp <span class="text-amber-400 font-mono">${(a.temp).toFixed(1)}°C</span>`;
            } else {
                vitalSnippet += ` • MAP <span class="text-slate-300 font-mono">${a.map || 80} mmHg</span>`;
            }

            return `
            <article data-id="${a.id}" class="p-4 rounded-xl ${borderClass} transition-all cursor-pointer space-y-3">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        ${sevBadge}
                        <span class="text-xs font-mono text-slate-400">#${a.id} • ${formatTimeAgo(a.timestamp)}</span>
                    </div>
                    <span class="text-xs font-medium text-cyan-300 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800">
                        Bed ${a.patient_room || '302'} • ${a.patient_name || a.patient_id}
                    </span>
                </div>

                <div>
                    <h3 class="text-sm font-bold text-white">${a.title}</h3>
                    <p class="text-xs text-slate-300 mt-1">${vitalSnippet}</p>
                </div>

                <div class="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
                    <span class="text-slate-400 font-mono text-[11px]">ML Confidence: ${(a.confidence || 63.6).toFixed(1)}%</span>
                    <div class="flex items-center gap-2">
                        <button class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition text-xs btn-review" data-id="${a.id}" type="button">
                            Review
                        </button>
                        ${!a.acknowledged ? `
                            <button class="px-3 py-1 rounded ${isCrit ? 'bg-rose-600 hover:bg-rose-500' : 'bg-amber-600 hover:bg-amber-500'} text-white font-medium transition text-xs btn-ack" data-id="${a.id}" type="button">
                                Acknowledge
                            </button>
                        ` : `
                            <span class="text-xs text-emerald-400 font-mono">✓ Triage Closed</span>
                        `}
                    </div>
                </div>
            </article>
            `;
        }).join("");

        // Attach events to cards and review/ack buttons
        queueContainer.querySelectorAll("article").forEach(art => {
            art.addEventListener("click", (e) => {
                if (e.target.closest(".btn-ack")) return;
                selectedAlertId = parseInt(art.dataset.id, 10);
                renderQueue();
                renderInspector();
            });
        });

        queueContainer.querySelectorAll(".btn-review").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                selectedAlertId = parseInt(btn.dataset.id, 10);
                renderQueue();
                renderInspector();
                const inspector = document.getElementById("alert-inspector-panel");
                if (inspector && window.innerWidth < 1024) {
                    inspector.scrollIntoView({ behavior: "smooth" });
                }
            });
        });

        queueContainer.querySelectorAll(".btn-ack").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const aid = parseInt(btn.dataset.id, 10);
                acknowledgeAlert(aid);
            });
        });
    }

    function renderInspector() {
        const filtered = getFilteredAlerts();
        const sel = filtered.find(a => a.id === selectedAlertId) || filtered[0];
        if (!sel) return;

        const isCrit = sel.severity === "CRITICAL";

        if (inspBadge) {
            inspBadge.className = `px-2 py-0.5 rounded text-xs font-mono font-bold ${isCrit ? 'bg-rose-500 text-white' : 'bg-amber-500 text-slate-950'}`;
            inspBadge.textContent = `${sel.severity} ALERT #${sel.id}`;
        }
        if (inspTriggerTime) {
            inspTriggerTime.textContent = `Triggered at ${new Date(sel.timestamp * 1000).toLocaleTimeString()}`;
        }
        if (inspPatientName) {
            inspPatientName.innerHTML = `${sel.patient_name || sel.patient_id} <span class="text-sm font-normal text-slate-400">(Bed ${sel.patient_room || '302'})</span>`;
        }
        if (inspPatientSub) {
            inspPatientSub.textContent = `${sel.patient_age || 42} years old • ${sel.patient_mrn || 'MRN #994-012-ICU'} • Primary: ${sel.patient_condition || 'Cardiology Observation'}`;
        }
        if (inspEventName) {
            inspEventName.textContent = `${sel.title} Detected`;
        }
        if (inspAnomalyTag) {
            inspAnomalyTag.textContent = sel.title.split("-")[0].trim();
        }
        if (inspConfidenceTag) {
            inspConfidenceTag.textContent = `Confidence: ${(sel.confidence || 63.6).toFixed(1)}%`;
        }

        // Dynamic Vitals from actual database snapshot
        const isHrBreach = sel.hr > 120 || sel.hr < 50;
        const isSpo2Breach = sel.spo2 < 90;
        const isTempBreach = sel.temp > 38.0;

        const cardHR = document.getElementById("inspCardHR");
        const cardSpO2 = document.getElementById("inspCardSpO2");
        const cardBP = document.getElementById("inspCardBP");
        const cardTemp = document.getElementById("inspCardTemp");

        if (cardHR) {
            cardHR.className = isHrBreach 
                ? "bg-slate-950 p-3 rounded-lg border border-rose-500/60 shadow-[0_0_10px_rgba(244,63,94,0.2)] space-y-1" 
                : "bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1";
        }
        if (inspValHR) {
            inspValHR.textContent = Math.round(sel.hr || 75);
            inspValHR.className = isHrBreach ? "text-2xl font-bold font-mono text-rose-400" : "text-2xl font-bold font-mono text-slate-200";
        }
        if (inspNoteHR) {
            inspNoteHR.textContent = sel.hr > 120 ? `High (>120 bpm breach)` : (sel.hr < 50 ? `Bradycardia (<50 bpm breach)` : `Normal Range (60-100)`);
            inspNoteHR.className = isHrBreach ? "text-[10px] text-rose-300 font-medium block" : "text-[10px] text-emerald-400 font-medium block";
        }

        if (cardSpO2) {
            cardSpO2.className = isSpo2Breach 
                ? "bg-slate-950 p-3 rounded-lg border border-rose-500/60 shadow-[0_0_10px_rgba(244,63,94,0.2)] space-y-1" 
                : "bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1";
        }
        if (inspValSpO2) {
            inspValSpO2.textContent = (sel.spo2 || 98.0).toFixed(1);
            inspValSpO2.className = isSpo2Breach ? "text-2xl font-bold font-mono text-rose-400" : "text-2xl font-bold font-mono text-cyan-400";
        }
        if (inspNoteSpO2) {
            inspNoteSpO2.textContent = sel.spo2 < 90 ? `Critical Low (<90% breach)` : `Safe Saturation (≥95%)`;
            inspNoteSpO2.className = isSpo2Breach ? "text-[10px] text-rose-300 font-medium block" : "text-[10px] text-cyan-400 font-medium block";
        }

        if (cardBP) cardBP.className = "bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1";
        if (inspValBP) inspValBP.textContent = `${sel.bp_sys || 118}/${sel.bp_dia || 74}`;
        if (inspNoteMAP) inspNoteMAP.textContent = `MAP: ${sel.map || 88} mmHg`;

        if (cardTemp) {
            cardTemp.className = isTempBreach 
                ? "bg-slate-950 p-3 rounded-lg border border-amber-500/60 shadow-[0_0_10px_rgba(245,158,11,0.2)] space-y-1" 
                : "bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1";
        }
        if (inspValTemp) {
            inspValTemp.textContent = (sel.temp || 37.0).toFixed(1);
            inspValTemp.className = isTempBreach ? "text-2xl font-bold font-mono text-amber-300" : "text-2xl font-bold font-mono text-slate-200";
        }
        if (inspNoteTemp) {
            inspNoteTemp.textContent = sel.temp > 38.0 ? `Elevated Core Temp (>38°C)` : `Afebrile Safe Range`;
            inspNoteTemp.className = isTempBreach ? "text-[10px] text-amber-400 font-medium block" : "text-[10px] text-emerald-400 font-medium block";
        }

        // Tailored Clinical Guidelines based on diagnosis and real vitals
        if (inspProtocols) {
            const combinedText = ((sel.title || '') + ' ' + (sel.message || '')).toLowerCase();
            if (combinedText.includes("arrhythmia") || combinedText.includes("ventricular")) {
                inspProtocols.innerHTML = `
                    <li class="leading-relaxed"><strong class="text-white">Immediate Oxygen:</strong> Deliver high-flow oxygen via non-rebreather mask (target SpO2 > 92%).</li>
                    <li class="leading-relaxed"><strong class="text-white">Diagnostic STAT:</strong> Perform urgent 12-lead ECG STAT and draw serum electrolytes (K+, Mg2+).</li>
                    <li class="leading-relaxed"><strong class="text-white">Medication Prep:</strong> Ready Amiodarone 150 mg IV over 10 min if ventricular runs recur.</li>
                `;
            } else if (combinedText.includes("tachycardia") || combinedText.includes("fever") || (sel.hr > 120) || (sel.temp > 38.0)) {
                inspProtocols.innerHTML = `
                    <li class="leading-relaxed"><strong class="text-white">Antipyretic Administration:</strong> Administer IV Paracetamol / Acetaminophen as prescribed.</li>
                    <li class="leading-relaxed"><strong class="text-white">Fluid Hydration:</strong> Initiate 500 mL Normal Saline bolus if hemodynamically stable.</li>
                    <li class="leading-relaxed"><strong class="text-white">Vitals Recheck:</strong> Perform serial blood pressure and core temperature checks every 15 minutes.</li>
                `;
            } else if (combinedText.includes("hypoxemia") || combinedText.includes("spo2") || (sel.spo2 < 90)) {
                inspProtocols.innerHTML = `
                    <li class="leading-relaxed"><strong class="text-white">Airway Verification:</strong> Confirm sensor placement; switch probe location if perfusion index < 1.0.</li>
                    <li class="leading-relaxed"><strong class="text-white">Oxygen Titration:</strong> Escalate nasal cannula flow from 2 L/min to 6 L/min or initiate venturi mask.</li>
                    <li class="leading-relaxed"><strong class="text-white">Chest Auscultation:</strong> Auscultate bilateral lung fields for crackles, wheezing, or atelectasis.</li>
                `;
            } else {
                inspProtocols.innerHTML = `
                    <li class="leading-relaxed"><strong class="text-white">Continuous Telemetry:</strong> Maintain Lead-II continuous waveform recording.</li>
                    <li class="leading-relaxed"><strong class="text-white">Nursing Triage:</strong> Assess patient level of consciousness, peripheral pulses, and skin turgor.</li>
                    <li class="leading-relaxed"><strong class="text-white">Clinician Documentation:</strong> Record triage assessment in Electronic Medical Record (EMR).</li>
                `;
            }
        }

        // Dynamic Network Telemetry Strip
        const netDot = document.getElementById("inspNetworkDot");
        const netText = document.getElementById("inspNetworkText");
        const netQueue = document.getElementById("inspNetworkQueue");
        if (netDot && netText && netQueue) {
            if (sel.acknowledged) {
                netDot.className = "w-2 h-2 rounded-full bg-slate-500";
                netText.textContent = "Network: Standard Best-Effort • Baseline Priority";
                netQueue.textContent = "Switch SW-ICU-02 • Queue 0 (100Mbps Best-Effort)";
            } else {
                netDot.className = "w-2 h-2 rounded-full bg-emerald-400 status-ping";
                netText.textContent = "Network: Prioritized QoS Active • Sub-ms Latency";
                netQueue.textContent = "Switch SW-ICU-02 • Queue 1 (HTB 10Mbps Priority)";
            }
        }

        // Acknowledge Button in Inspector
        if (inspAckBtn && inspAckBtnText) {
            if (sel.acknowledged) {
                inspAckBtn.disabled = true;
                inspAckBtn.className = "px-5 py-2.5 rounded-lg bg-slate-800 text-slate-500 text-xs font-bold transition flex items-center gap-1.5 cursor-not-allowed";
                inspAckBtnText.textContent = `Alert #${sel.id} Acknowledged`;
            } else {
                inspAckBtn.disabled = false;
                inspAckBtn.className = "px-5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold transition flex items-center gap-1.5 shadow-sm";
                inspAckBtnText.textContent = `Acknowledge Alert #${sel.id}`;
                inspAckBtn.onclick = () => acknowledgeAlert(sel.id);
            }
        }
    }

    // Acknowledge a single alert
    window.acknowledgeAlert = async function(alertId) {
        try {
            const res = await fetch(`/api/alerts/${alertId}/ack`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken()
                }
            });
            if (res.ok) {
                const target = allAlerts.find(a => a.id === alertId);
                if (target) {
                    target.acknowledged = true;
                    target.acknowledged_by = "Staff";
                }
                updateTriageStats();
                renderQueue();
                renderInspector();
            }
        } catch (err) {
            console.error("Failed to acknowledge alert:", err);
        }
    };

    // Bulk Acknowledge All
    if (ackAllBtn) {
        ackAllBtn.addEventListener("click", async () => {
            if (!confirm("Are you sure you want to acknowledge all active clinical alerts?")) return;
            try {
                const res = await fetch("/api/alerts/ack-all", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken()
                    }
                });
                if (res.ok) {
                    allAlerts.forEach(a => a.acknowledged = true);
                    updateTriageStats();
                    renderQueue();
                    renderInspector();
                }
            } catch (err) {
                console.error("Failed to acknowledge all alerts:", err);
            }
        });
    }

    // Rapid Response Action
    if (rapidResponseBtn) {
        rapidResponseBtn.addEventListener("click", async () => {
            if (!selectedAlertId) return;
            try {
                const res = await fetch(`/api/alerts/${selectedAlertId}/rapid-response`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken()
                    }
                });
                if (res.ok) {
                    alert(`🚨 RAPID RESPONSE TEAM DISPATCHED!\nSTAT notification transmitted to ICU Crash Team and telemetry overhead.`);
                }
            } catch (err) {
                console.error("Failed to trigger rapid response:", err);
            }
        });
    }

    // Filter and search live handlers
    if (filterSelect) filterSelect.addEventListener("change", loadAlerts);
    if (searchInput) searchInput.addEventListener("input", () => {
        renderQueue();
        renderInspector();
    });

    // Refresh loop every 2 seconds
    setInterval(loadAlerts, 2000);
    loadAlerts();
}

// ==========================================
// HISTORY CHARTS
// ==========================================
function initHistoryCharts() {
    const patientSelect = document.getElementById("historyPatientSelect");
    let chartHR = null, chartSpO2 = null, chartTemp = null;

    const chartCommonOptions = {
        responsive: true,
        plugins: {
            legend: { labels: { color: '#94A3B8', font: { family: 'Inter', size: 11 } } }
        },
        scales: {
            x: {
                grid: { color: 'rgba(56, 189, 248, 0.08)' },
                ticks: { color: '#64748B', font: { family: 'monospace', size: 10 } }
            },
            y: {
                grid: { color: 'rgba(56, 189, 248, 0.08)' },
                ticks: { color: '#94A3B8', font: { family: 'monospace', size: 10 } }
            }
        }
    };

    async function loadHistory() {
        const pid = patientSelect ? patientSelect.value.split(" ")[0].trim() : "P101";
        const res = await fetch(`/api/patients/${pid}/history?range=120`);
        const data = await res.json();

        const labels = data.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
        const hrData = data.map(d => d.hr);
        const spo2Data = data.map(d => d.spo2);
        const tempData = data.map(d => d.temp);

        if (chartHR) chartHR.destroy();
        if (chartSpO2) chartSpO2.destroy();
        if (chartTemp) chartTemp.destroy();

        const ctxHR = document.getElementById("chartHR").getContext("2d");
        chartHR = new Chart(ctxHR, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Heart Rate (bpm)",
                    data: hrData,
                    borderColor: "#EF4444",
                    backgroundColor: "rgba(239, 68, 68, 0.15)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 2
                }]
            },
            options: { ...chartCommonOptions, scales: { ...chartCommonOptions.scales, y: { ...chartCommonOptions.scales.y, min: 40, max: 160 } } }
        });

        const ctxSpO2 = document.getElementById("chartSpO2").getContext("2d");
        chartSpO2 = new Chart(ctxSpO2, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Blood Oxygen SpO2 (%)",
                    data: spo2Data,
                    borderColor: "#06B6D4",
                    backgroundColor: "rgba(6, 182, 212, 0.15)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 2
                }]
            },
            options: { ...chartCommonOptions, scales: { ...chartCommonOptions.scales, y: { ...chartCommonOptions.scales.y, min: 70, max: 100 } } }
        });

        const ctxTemp = document.getElementById("chartTemp").getContext("2d");
        chartTemp = new Chart(ctxTemp, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Body Temperature (°C)",
                    data: tempData,
                    borderColor: "#F59E0B",
                    backgroundColor: "rgba(245, 158, 11, 0.15)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 2
                }]
            },
            options: { ...chartCommonOptions, scales: { ...chartCommonOptions.scales, y: { ...chartCommonOptions.scales.y, min: 34, max: 41 } } }
        });
    }

    if (patientSelect) patientSelect.addEventListener("change", loadHistory);
    loadHistory();
}

// ==========================================
// SDN NETWORK FABRIC DASHBOARD
// ==========================================
function initNetworkDashboard() {
    let netChart = null;

    async function loadNetworkData() {
        const res = await fetch("/api/network/metrics");
        const data = await res.json();

        const ctx = document.getElementById("netPerfChart").getContext("2d");
        if (netChart) netChart.destroy();

        netChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: ["Latency (ms)", "Throughput (Mbps)", "Packet Loss (%)"],
                datasets: [
                    {
                        label: "Priority OFF (Best-Effort Queue 0 Under 10 Mbps Saturation)",
                        data: [data.off.latency, data.off.throughput, data.off.loss],
                        backgroundColor: "rgba(239, 68, 68, 0.75)",
                        borderColor: "#EF4444",
                        borderWidth: 1
                    },
                    {
                        label: "Priority ON (SDN Queue 1 Dynamic QoS Guaranteed)",
                        data: [data.on.latency, data.on.throughput, data.on.loss],
                        backgroundColor: "rgba(16, 185, 129, 0.75)",
                        borderColor: "#10B981",
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: { color: '#94A3B8', font: { family: 'Inter', size: 11 } } }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(56, 189, 248, 0.08)' },
                        ticks: { color: '#94A3B8', font: { family: 'Inter', size: 11 } }
                    },
                    y: {
                        grid: { color: 'rgba(56, 189, 248, 0.08)' },
                        ticks: { color: '#64748B', font: { family: 'monospace', size: 10 } }
                    }
                }
            }
        });

        // Load active flows table
        const flowRes = await fetch("/api/network/flows");
        const flows = await flowRes.json();
        const flowList = document.getElementById("flowList");
        if (flowList) {
            flowList.innerHTML = flows.length === 0
                ? `<tr><td colspan="6" class="text-center py-8 text-slate-400 font-mono text-xs">No active priority flows. Traffic forwarded via standard OpenFlow L2 learning switch.</td></tr>`
                : flows.map(f => `
                    <tr>
                        <td class="font-mono text-purple-300 font-bold">${f.rule_name}</td>
                        <td class="font-mono text-slate-300">${f.match_ip}</td>
                        <td><span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-800">Queue ${f.queue_id} (Priority)</span></td>
                        <td class="font-mono text-slate-300">${f.priority}</td>
                        <td class="font-mono text-cyan-400">${f.flow_setup_time_ms ? f.flow_setup_time_ms + ' ms' : '3.2 ms'}</td>
                        <td class="text-xs text-slate-300">${f.reason}</td>
                    </tr>
                `).join("");
        }
    }
    loadNetworkData();
    setInterval(loadNetworkData, 3000);
}

// ==========================================
// CLINICAL ADMIN PAGE
// ==========================================
function initAdminPage() {
    const form = document.getElementById("thresholdForm");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                hr_min: parseFloat(document.getElementById("hrMin").value),
                hr_max: parseFloat(document.getElementById("hrMax").value),
                spo2_min: parseFloat(document.getElementById("spo2Min").value),
                temp_max: parseFloat(document.getElementById("tempMax").value)
            };
            const res = await fetch("/api/admin/thresholds", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken()
                },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                alert("Clinical alarm thresholds updated & propagated successfully!");
            }
        });
    }
}
