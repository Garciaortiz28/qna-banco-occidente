/* ══════════════════════════════════════════════════════
   voice.js — Voz para Asistente Virtual BdO
   STT: Web Speech API (browser nativo, gratis)
   TTS: SpeechSynthesis (browser nativo, gratis)
   ══════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── Estado ─────────────────────────────────────────
  let isListening   = false;
  let isTTSEnabled  = true;   // TTS activado por defecto
  let recognition   = null;
  let lastResponse  = '';

  // ── Soporte del navegador ───────────────────────────
  const STT_SUPPORTED = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  const TTS_SUPPORTED = 'speechSynthesis' in window;

  // ── Inyectar botones en el DOM ──────────────────────
  function injectUI() {
    // Botón de voz
    const voiceBtn = document.createElement('button');
    voiceBtn.id        = 'bdo-voice-btn';
    voiceBtn.innerHTML = '🎤';
    voiceBtn.title     = STT_SUPPORTED
      ? 'Habla con el asistente'
      : 'Tu navegador no soporta voz. Usa Chrome o Edge.';
    voiceBtn.disabled  = !STT_SUPPORTED;

    const voiceTip = document.createElement('div');
    voiceTip.id        = 'bdo-voice-tooltip';
    voiceTip.innerText = STT_SUPPORTED
      ? 'Haz clic y habla'
      : 'Usa Chrome o Edge para voz';

    // WhatsApp flotante
    const waDiv = document.createElement('div');
    waDiv.id        = 'bdo-whatsapp';
    waDiv.innerHTML = `
      <div class="wa-bubble">💬 Chatea con un asesor</div>
      <a href="https://api.whatsapp.com/send?phone=573186714836"
         target="_blank" rel="noopener" class="wa-btn">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15
          -.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475
          -.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52
          .149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207
          -.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372
          -.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2
          5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719
          2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004
          a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0
          01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825
          9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815
          0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305
          -1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821
          11.821 0 00-3.48-8.413z"/>
        </svg>
        <span>Hablar con asesor</span>
      </a>
    `;

    document.body.appendChild(voiceBtn);
    document.body.appendChild(voiceTip);
    document.body.appendChild(waDiv);

    voiceBtn.addEventListener('click', toggleVoice);
  }

  // ── STT — Reconocimiento de voz ─────────────────────
  function toggleVoice() {
    if (!STT_SUPPORTED) {
      alert('Tu navegador no soporta reconocimiento de voz.\nUsa Google Chrome o Microsoft Edge.');
      return;
    }
    isListening ? stopListening() : startListening();
  }

  function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();

    recognition.lang            = 'es-CO';
    recognition.continuous      = false;
    recognition.interimResults  = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      isListening = true;
      const btn       = document.getElementById('bdo-voice-btn');
      if (btn) { btn.innerHTML = '🔴'; btn.classList.add('listening'); }
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      sendToChat(transcript);
    };

    recognition.onerror = (event) => {
      console.warn('[BdO Voice] Error STT:', event.error);
      if (event.error === 'not-allowed') {
        alert('Permiso de micrófono denegado. Actívalo en la configuración del navegador.');
      }
      stopListening();
    };

    recognition.onend = () => stopListening();

    recognition.start();
  }

  function stopListening() {
    isListening = false;
    const btn = document.getElementById('bdo-voice-btn');
    if (btn) { btn.innerHTML = '🎤'; btn.classList.remove('listening'); }
    if (recognition) { try { recognition.stop(); } catch (_) {} }
  }

  // ── Enviar texto al input del chat ──────────────────
  function sendToChat(text) {
    // Busca el textarea de Chainlit
    const textarea = document.querySelector('textarea');
    if (!textarea) return;

    // Inyectar texto vía React synthetic event
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, 'value'
    ).set;
    nativeSet.call(textarea, text);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));

    // Auto-submit después de 200ms
    setTimeout(() => {
      const submitBtn = document.querySelector('button[type="submit"]')
        || document.querySelector('[data-testid="send-button"]');
      if (submitBtn) submitBtn.click();
    }, 200);
  }

  // ── TTS — Texto a voz ───────────────────────────────
  function speak(text) {
    if (!TTS_SUPPORTED || !isTTSEnabled) return;

    // Cancelar cualquier audio previo
    window.speechSynthesis.cancel();

    // Limpiar markdown básico
    const clean = text
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/`(.*?)`/g, '$1')
      .replace(/#{1,6}\s/g, '')
      .substring(0, 500); // Max 500 chars para no hablar demasiado

    const utterance          = new SpeechSynthesisUtterance(clean);
    utterance.lang           = 'es-CO';
    utterance.rate           = 1.0;
    utterance.pitch          = 1.0;
    utterance.volume         = 0.9;

    // Preferir voz en español si está disponible
    const voices = window.speechSynthesis.getVoices();
    const esVoice = voices.find(v => v.lang.startsWith('es'));
    if (esVoice) utterance.voice = esVoice;

    window.speechSynthesis.speak(utterance);
  }

  // ── Observar nuevas respuestas del asistente ────────
  function observeResponses() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== 1) continue;

          // Detectar mensajes del asistente (Chainlit)
          const assistantMsg = node.querySelector?.('.message.assistant, [data-author="assistant"]')
            || (node.matches?.('.message.assistant') ? node : null);

          if (assistantMsg) {
            const text = assistantMsg.innerText || assistantMsg.textContent;
            if (text && text !== lastResponse) {
              lastResponse = text;
              // Pequeño delay para que el texto esté completo
              setTimeout(() => speak(text), 300);
            }
          }
        }
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  // ── Inicialización ──────────────────────────────────
  function init() {
    injectUI();
    observeResponses();

    // Cargar voces (puede tardar un momento en algunos navegadores)
    if (TTS_SUPPORTED) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }

    console.log('[BdO Voice] Iniciado. STT:', STT_SUPPORTED, '| TTS:', TTS_SUPPORTED);
  }

  // Esperar a que el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    setTimeout(init, 1500); // Chainlit necesita tiempo para renderizar
  }

})();
