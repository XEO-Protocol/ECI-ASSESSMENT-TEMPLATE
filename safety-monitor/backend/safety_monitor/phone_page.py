"""The phone-as-camera web page, served by the hub itself.

Self-contained vanilla HTML/JS — no build step, no CDN, nothing leaves
the LAN. The same page handles both first-time pairing (opened via a
/pair/{token} QR link) and resuming a previously paired camera
(credentials kept in the phone's localStorage, route /phone-camera).

Frames go to the hub as JPEG blobs over a WebSocket at a modest rate —
analysis runs on the hub every couple of seconds, so ~6 fps is plenty
for preview and detection alike.
"""

PHONE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#0c1113">
<title>Safety Monitor — Phone Camera</title>
<style>
  :root {
    --bg:#0c1113; --surface:#12191c; --surface-2:#182126; --border:#233037;
    --text:#e7edee; --muted:#9bb0b6; --faint:#647a81;
    --accent:#4cc2b4; --accent-ink:#06211e; --warn:#d9a92f; --alert:#e0574f; --ok:#7ac07e;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
    background:var(--bg); color:var(--text); min-height:100vh;
    display:flex; flex-direction:column; align-items:center; padding:20px 16px 40px;
  }
  .mark { width:52px; height:52px; border-radius:14px; background:rgba(76,194,180,.13);
    display:grid; place-items:center; color:var(--accent); margin:18px 0 10px; }
  h1 { font-size:17px; margin:0 0 2px; font-weight:650; }
  .sub { color:var(--faint); font-size:12px; margin:0 0 22px; }
  .card { width:100%; max-width:420px; background:var(--surface); border:1px solid var(--border);
    border-radius:14px; padding:18px; display:flex; flex-direction:column; gap:12px; }
  label { font-size:12.5px; font-weight:550; }
  input {
    width:100%; font-size:16px; padding:10px 12px; border-radius:8px;
    border:1px solid var(--border); background:var(--surface-2); color:var(--text);
  }
  button {
    font-size:15px; font-weight:600; padding:12px; border-radius:9px; border:0;
    background:var(--accent); color:var(--accent-ink); cursor:pointer;
  }
  button.secondary { background:var(--surface-2); color:var(--muted);
    border:1px solid var(--border); }
  .status { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--muted); }
  .dot { width:9px; height:9px; border-radius:50%; background:var(--faint); }
  .dot.live { background:var(--ok); animation:pulse 2s infinite; }
  .dot.err { background:var(--alert); }
  .dot.warn { background:var(--warn); }
  @keyframes pulse { 50% { opacity:.35; } }
  video { width:100%; border-radius:10px; background:#000; border:1px solid var(--border); }
  .meta { font-size:11.5px; color:var(--faint); font-variant-numeric:tabular-nums; }
  .note { font-size:12px; color:var(--muted); line-height:1.55;
    background:var(--surface-2); border:1px solid var(--border); border-radius:8px; padding:10px 12px; }
  .note b { color:var(--text); }
  .err-box { color:var(--alert); font-size:13px; line-height:1.5; }
  .hidden { display:none !important; }
</style>
</head>
<body>
  <div class="mark">
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3l7.5 3v5.6c0 4.3-3 8-7.5 9.4-4.5-1.4-7.5-5.1-7.5-9.4V6L12 3z"/>
      <circle cx="12" cy="11" r="2.6"/>
    </svg>
  </div>
  <h1>Safety Monitor</h1>
  <p class="sub">phone camera &middot; streams only to your own hub on this network</p>

  <div class="card" id="setup">
    <label for="name">Name this camera</label>
    <input id="name" value="" placeholder="e.g. iPad — living room" autocomplete="off">
    <button id="start">Start camera</button>
    <p class="err-box hidden" id="setup-error"></p>
    <p class="note"><b>Keep this screen on.</b> Phones stop the camera when the
    screen locks — plug the device in and disable auto-lock (iPad: Settings &rarr;
    Display &amp; Brightness &rarr; Auto-Lock &rarr; Never) while it works as a camera.</p>
  </div>

  <div class="card hidden" id="live">
    <video id="preview" autoplay playsinline muted></video>
    <div class="status"><span class="dot" id="dot"></span><span id="status-text">starting…</span></div>
    <div class="meta" id="meta"></div>
    <button class="secondary" id="flip">Switch front/back camera</button>
    <button class="secondary" id="stop">Stop streaming</button>
  </div>

<script>
(function () {
  const qs = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const pathToken = location.pathname.startsWith('/pair/')
    ? decodeURIComponent(location.pathname.split('/pair/')[1] || '') : '';

  const saved = JSON.parse(localStorage.getItem('sm-phone-camera') || 'null');
  let creds = saved && saved.camera_id && saved.device_key ? saved : null;
  let stream = null, ws = null, sending = false, facing = 'environment';
  let sent = 0, stopped = false, reconnectDelay = 1000;

  if (creds) qs('name').value = creds.name || '';
  if (!creds && !pathToken) {
    showSetupError('This page needs a pairing link. On the desktop app choose ' +
      '"Add phone or tablet" and scan the QR code it shows.');
    qs('start').disabled = true;
  }

  function showSetupError(msg) {
    const el = qs('setup-error');
    el.textContent = msg; el.classList.remove('hidden');
  }
  function setStatus(kind, text) {
    qs('dot').className = 'dot ' + kind;
    qs('status-text').textContent = text;
  }

  async function claimIfNeeded() {
    if (creds) return true;
    const name = qs('name').value.trim() || 'Phone camera';
    const resp = await fetch('/api/pairing/claim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: pathToken, name: name }),
    });
    if (!resp.ok) {
      const detail = await resp.json().catch(() => ({}));
      showSetupError((detail.detail || 'Pairing failed') +
        ' — generate a fresh QR code on the desktop and scan again.');
      return false;
    }
    const data = await resp.json();
    creds = { camera_id: data.camera_id, device_key: data.device_key, name: name };
    localStorage.setItem('sm-phone-camera', JSON.stringify(creds));
    return true;
  }

  async function openCamera() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    qs('preview').srcObject = stream;
  }

  function connectWS() {
    if (stopped) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(proto + '//' + location.host + '/ws/phone/' + creds.camera_id);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      ws.send(JSON.stringify({ device_key: creds.device_key }));
      reconnectDelay = 1000;
      setStatus('live', 'Streaming to hub');
    };
    ws.onclose = (ev) => {
      if (stopped) return;
      if (ev.code === 4401) {
        setStatus('err', 'Unpaired — this camera was removed on the desktop');
        localStorage.removeItem('sm-phone-camera');
        return;
      }
      setStatus('warn', 'Hub unreachable — reconnecting…');
      setTimeout(connectWS, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 10000);
    };
    ws.onerror = () => ws.close();
  }

  async function sendLoop() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const video = qs('preview');
    while (!stopped) {
      if (ws && ws.readyState === 1 && video.videoWidth && !sending) {
        sending = true;
        const scale = Math.min(1, 1280 / video.videoWidth);
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.7));
        if (blob && ws.readyState === 1 && ws.bufferedAmount < 2000000) {
          ws.send(await blob.arrayBuffer());
          sent++;
          qs('meta').textContent = 'frames sent: ' + sent + ' · ' +
            canvas.width + 'x' + canvas.height + ' · keep this screen on';
        }
        sending = false;
      }
      await new Promise(r => setTimeout(r, 160)); // ~6 fps
    }
  }

  async function keepAwake() {
    try {
      if ('wakeLock' in navigator) {
        let lock = await navigator.wakeLock.request('screen');
        document.addEventListener('visibilitychange', async () => {
          if (document.visibilityState === 'visible') {
            lock = await navigator.wakeLock.request('screen').catch(() => null);
          }
        });
      }
    } catch (e) { /* not supported: the on-page note covers it */ }
  }

  qs('start').onclick = async () => {
    try {
      if (!(await claimIfNeeded())) return;
      await openCamera();
      qs('setup').classList.add('hidden');
      qs('live').classList.remove('hidden');
      stopped = false;
      connectWS();
      sendLoop();
      keepAwake();
    } catch (err) {
      showSetupError('Camera access failed: ' + err.message +
        (location.protocol === 'http:' ?
          ' — browsers only allow camera access on HTTPS links; scan the QR code again.' : ''));
    }
  };

  qs('flip').onclick = async () => {
    facing = facing === 'environment' ? 'user' : 'environment';
    try { await openCamera(); } catch (e) { /* keep old stream */ }
  };

  qs('stop').onclick = () => {
    stopped = true;
    if (ws) ws.close();
    if (stream) stream.getTracks().forEach(t => t.stop());
    setStatus('', 'Stopped');
    qs('setup').classList.remove('hidden');
    qs('live').classList.add('hidden');
  };
})();
</script>
</body>
</html>
"""
