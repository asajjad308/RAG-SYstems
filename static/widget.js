(function () {
  'use strict';

  const script = document.currentScript;
  const BOT_ID = script && script.getAttribute('data-bot-id');
  if (!BOT_ID) { console.error('[DocMind] Missing data-bot-id attribute'); return; }

  const API_BASE = script.src.replace(/\/static\/widget\.js.*$/, '');

  let messages = [];
  let open = false;
  let shadow = null;
  let busy = false;

  fetch(`${API_BASE}/chatbots/${BOT_ID}/config`)
    .then(r => r.ok ? r.json() : Promise.reject('Bot not found'))
    .then(config => init(config))
    .catch(err => console.error('[DocMind]', err));

  function init(bot) {
    const accent = bot.accent_color || '#5b7bf5';
    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:2147483647;';
    document.body.appendChild(host);
    shadow = host.attachShadow({ mode: 'open' });

    shadow.innerHTML = `
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:host { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }

.bubble {
  width: 54px; height: 54px; border-radius: 50%;
  background: ${accent}; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 20px rgba(0,0,0,.3); color: #fff; font-size: 22px;
  transition: transform .2s, box-shadow .2s; position: relative;
}
.bubble:hover { transform: scale(1.07); box-shadow: 0 6px 28px rgba(0,0,0,.4); }

.window {
  position: absolute; bottom: 66px; right: 0;
  width: 340px; height: 490px;
  background: #0a0d1a; border: 1px solid #242d52;
  border-radius: 14px; display: flex; flex-direction: column;
  overflow: hidden; box-shadow: 0 8px 44px rgba(0,0,0,.5);
  opacity: 0; transform: translateY(14px) scale(.96);
  transition: opacity .22s, transform .22s; pointer-events: none;
}
.window.open { opacity: 1; transform: none; pointer-events: all; }

.win-head {
  padding: 13px 14px; background: #111525;
  border-bottom: 1px solid #242d52;
  display: flex; align-items: center; gap: 10px; flex-shrink: 0;
}
.win-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: ${accent}; display: flex; align-items: center;
  justify-content: center; font-size: 15px; flex-shrink: 0;
}
.win-name { font-size: 13px; font-weight: 600; color: #dce3f8; }
.win-status { font-size: 11px; color: #38d4a0; }
.win-close {
  margin-left: auto; background: none; border: none;
  color: #6876a8; font-size: 20px; cursor: pointer;
  border-radius: 5px; width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, color .15s;
}
.win-close:hover { background: #1a1f35; color: #dce3f8; }

.messages {
  flex: 1; overflow-y: auto; padding: 14px;
  display: flex; flex-direction: column; gap: 10px;
}

.welcome {
  align-self: center; text-align: center;
  padding: 20px 12px; color: #6876a8; font-size: 12px; line-height: 1.65;
}
.welcome-icon { font-size: 30px; margin-bottom: 8px; }
.welcome-title { color: #dce3f8; font-weight: 600; font-size: 14px; margin-bottom: 6px; }

.msg { display: flex; flex-direction: column; max-width: 84%; }
.msg.user { align-self: flex-end; align-items: flex-end; }
.msg.bot  { align-self: flex-start; align-items: flex-start; }

.msg-bubble {
  padding: 9px 13px; border-radius: 14px;
  font-size: 13px; line-height: 1.55; word-break: break-word;
}
.user .msg-bubble {
  background: ${accent}; color: #fff; border-bottom-right-radius: 4px;
}
.bot .msg-bubble {
  background: #111525; color: #dce3f8; border-bottom-left-radius: 4px;
  border: 1px solid #242d52;
}

.typing {
  display: flex; gap: 4px;
  padding: 11px 14px; background: #111525;
  border: 1px solid #242d52;
  border-radius: 14px; border-bottom-left-radius: 4px;
}
.typing span {
  width: 6px; height: 6px; border-radius: 50%;
  background: #6876a8; animation: t .8s infinite;
}
.typing span:nth-child(2) { animation-delay: .15s; }
.typing span:nth-child(3) { animation-delay: .3s; }
@keyframes t {
  0%,80%,100% { transform: translateY(0); opacity:.35; }
  40%          { transform: translateY(-5px); opacity:1; }
}

.win-foot {
  padding: 10px 12px; border-top: 1px solid #242d52;
  display: flex; gap: 8px; flex-shrink: 0; background: #0a0d1a;
}
.win-input {
  flex: 1; background: #111525; border: 1px solid #242d52;
  color: #dce3f8; font-size: 13px; padding: 8px 12px;
  border-radius: 8px; outline: none; font-family: inherit;
  transition: border-color .15s;
}
.win-input:focus { border-color: ${accent}; }
.win-input::placeholder { color: #3a4268; }

.win-send {
  width: 36px; height: 36px; border-radius: 8px;
  background: ${accent}; border: none; color: #fff;
  font-size: 15px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: opacity .15s;
}
.win-send:disabled { opacity: .4; cursor: not-allowed; }
.win-send:hover:not(:disabled) { opacity: .82; }

.powered {
  text-align: center; font-size: 10px; color: #2d3458;
  padding: 4px 0 8px;
}
.powered a { color: #3d4878; text-decoration: none; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #242d52; border-radius: 2px; }
</style>

<div class="window" id="win">
  <div class="win-head">
    <div class="win-avatar">🤖</div>
    <div>
      <div class="win-name">${esc(bot.name)}</div>
      <div class="win-status">● Online</div>
    </div>
    <button class="win-close" id="closeBtn">×</button>
  </div>
  <div class="messages" id="messages">
    <div class="welcome">
      <div class="welcome-icon">👋</div>
      <div class="welcome-title">${esc(bot.name)}</div>
      Ask me anything about the documents I've been trained on.
    </div>
  </div>
  <div class="win-foot">
    <input class="win-input" id="input" placeholder="Type a message…" autocomplete="off">
    <button class="win-send" id="sendBtn">↑</button>
  </div>
  <div class="powered">Powered by <a href="#">DocMind</a></div>
</div>

<button class="bubble" id="bubble">💬</button>`;

    const win     = shadow.getElementById('win');
    const bubble  = shadow.getElementById('bubble');
    const closeBtn = shadow.getElementById('closeBtn');
    const input   = shadow.getElementById('input');
    const sendBtn = shadow.getElementById('sendBtn');

    bubble.addEventListener('click', () => {
      open = !open;
      win.classList.toggle('open', open);
      if (open) setTimeout(() => input.focus(), 220);
    });

    closeBtn.addEventListener('click', () => {
      open = false;
      win.classList.remove('open');
    });

    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
    sendBtn.addEventListener('click', send);
  }

  async function send() {
    if (busy) return;
    const input   = shadow.getElementById('input');
    const sendBtn = shadow.getElementById('sendBtn');
    const text    = input.value.trim();
    if (!text) return;

    input.value = '';
    busy = true;
    sendBtn.disabled = true;

    messages.push({ role: 'user', content: text });
    appendMsg('user', text);
    const typing = appendTyping();

    try {
      const res = await fetch(`${API_BASE}/chatbots/${BOT_ID}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: messages.slice(-10) })
      });
      const data = await res.json();
      typing.remove();
      const answer = data.answer || data.detail || 'Sorry, I could not process that.';
      messages.push({ role: 'assistant', content: answer });
      appendMsg('bot', answer);
    } catch {
      typing.remove();
      appendMsg('bot', 'Connection error. Please try again.');
    } finally {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  function appendMsg(role, text) {
    const msgs = shadow.getElementById('messages');
    msgs.querySelector('.welcome')?.remove();
    const el = document.createElement('div');
    el.className = `msg ${role}`;
    el.innerHTML = `<div class="msg-bubble">${esc(text)}</div>`;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function appendTyping() {
    const msgs = shadow.getElementById('messages');
    const el = document.createElement('div');
    el.className = 'msg bot';
    el.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
    return el;
  }

  function esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
})();
