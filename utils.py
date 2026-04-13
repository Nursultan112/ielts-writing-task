"""
utils.py — TEN IELTS жобасының ортақ модулі
app.py (Task 1) және app2.py (Task 2) осыны пайдаланады.
"""

import re
import json
import time as _time
import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client


# ──────────────────────────────────────────
# SUPABASE
# ──────────────────────────────────────────

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )


def get_latest_draft(session_id: str) -> dict | None:
    """live_drafts кестесінен соңғы черновикті қайтарады."""
    try:
        res = (
            get_supabase()
            .table("live_drafts")
            .select("*")
            .eq("session_id", session_id)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return None


def save_result(student_name: str, result: dict, session_id: str, task_type: str) -> None:
    """
    Нәтижені results кестесіне сақтайды.
    task_type: "Task 1" немесе "Task 2"
    """
    try:
        # Task 1 → TA, Task 2 → TR, екеуі де 'ta' бағанасына сақталады
        ta_value = result.get("TA", result.get("TR", 0))
        get_supabase().table("results").insert({
            "student_name": student_name,
            "overall":      result["overall"],
            "ta":           ta_value,
            "cc":           result["CC"],
            "lr":           result["LR"],
            "gra":          result["GRA"],
            "main_errors":  result["main_errors"],
            "feedback":     result["feedback"],
            "task_type":    task_type,
        }).execute()
        # Черновикті жою
        get_supabase().table("live_drafts").delete().eq("session_id", session_id).execute()
    except Exception as e:
        st.warning(f"Сақтауда қате: {e}")


# ──────────────────────────────────────────
# СӨЗ САНЫ (нақты)
# ──────────────────────────────────────────

def count_words(text: str) -> int:
    """
    Нақты сөз санын қайтарады.
    re.findall арқылы тырнақшалар мен сызықшаларды дұрыс санайды.
    """
    return len(re.findall(r"\b\w+\b", text))


# ──────────────────────────────────────────
# JSON ТАЗАЛАУ
# ──────────────────────────────────────────

def clean_json(raw: str) -> str:
    """Gemini қайтарған жауаптан ```json ... ``` белгілерін тазалайды."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        # parts[1] — блок ішіндегі мазмұн
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ──────────────────────────────────────────
# RETRY ЛОГИКАСЫ (түзетілген)
# ──────────────────────────────────────────

RATE_LIMIT_KEYWORDS = ("429", "quota", "rate", "resource_exhausted")
MAX_RETRIES   = 5
RETRY_DELAYS  = [5, 10, 20, 30, 60]


def call_gemini_with_retry(model, contents: list) -> dict | None:
    """
    Gemini-ге сұраныс жіберіп, JSON нәтижені қайтарады.
    Rate-limit немесе басқа қатеде retry жасайды.
    Сәтсіз болса None қайтарады және st.error шығарады.
    """
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                wait = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                st.info(f"⏳ Кезек күтілуде... {wait} сек ({attempt}/{MAX_RETRIES})")
                _time.sleep(wait)

            raw = model.generate_content(contents).text
            result = json.loads(clean_json(raw))
            return result

        except Exception as e:
            last_error = str(e)
            is_rate = any(k in last_error.lower() for k in RATE_LIMIT_KEYWORDS)
            # Rate-limit емес қатеде — барлық retry-ды жалғастыру
            # (бұрын бұл жерде break болып, тек 1 рет байқалатын)
            if not is_rate and attempt >= 1:
                break  # Тек rate-limit емес + 2-ші рет+ болса ғана тоқтату

    # Барлық retry сарқылды
    if last_error and any(k in last_error.lower() for k in RATE_LIMIT_KEYWORDS):
        st.error("⏳ Жүйе қазір бос емес. 1-2 минуттан кейін қайталаңыз.")
    elif last_error:
        st.error(f"Қате шықты: {last_error}")
    return None


# ──────────────────────────────────────────
# НӘТИЖЕ БЕТІ (ортақ UI)
# ──────────────────────────────────────────

def show_result_page(result: dict, essay_text: str, task_type: str) -> None:
    """
    Тексеру нәтижесін көрсетеді.
    task_type: "Task 1" немесе "Task 2"
    """
    is_task2 = task_type == "Task 2"
    first_label = "Task Response" if is_task2 else "Task Achievement"
    first_key   = "TR" if is_task2 else "TA"

    st.success("✅ Жұмысыңыз сәтті тексерілді!")
    st.markdown(
        f"<h2 style='text-align:center;color:#1E88E5;'>🏆 Overall Band: {result['overall']}</h2>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(first_label,    result.get(first_key, "—"))
    c2.metric("Coherence",    result.get("CC",  "—"))
    c3.metric("Lexical",      result.get("LR",  "—"))
    c4.metric("Grammar",      result.get("GRA", "—"))

    st.markdown("---")
    st.subheader("🛠 Жіберілген қателер")
    for e in result.get("main_errors", []):
        st.warning(f"• {e}")

    st.subheader("📝 Пікір")
    st.markdown(result.get("feedback", ""))

    # ── Оқушының мәтіні (ЖАҢА: бұрын жоқ болатын)
    st.markdown("---")
    if essay_text:
        st.subheader("📋 Жазған мәтініңіз")
        st.text_area(
            "", value=essay_text, height=220,
            disabled=True, label_visibility="collapsed",
            key=f"saved_essay_{task_type.replace(' ', '_')}",
        )
        # Clipboard батырмасы
        copy_html = f"""
        <button id="copy-btn" onclick="copyText()" style="
            padding:10px 20px; background:#1E88E5; color:white;
            border:none; border-radius:8px; font-size:14px;
            cursor:pointer; width:100%; margin-top:4px;
        ">📋 Мәтінді көшіру</button>
        <span id="copy-msg" style="font-size:12px;color:#3B6D11;margin-left:8px;display:none;">✅ Көшірілді!</span>
        <script>
        function copyText() {{
            const text = {json.dumps(essay_text)};
            navigator.clipboard.writeText(text).then(() => {{
                document.getElementById('copy-msg').style.display = 'inline';
                document.getElementById('copy-btn').textContent = '✅ Көшірілді!';
                document.getElementById('copy-btn').style.background = '#639922';
                setTimeout(() => {{
                    document.getElementById('copy-btn').textContent = '📋 Мәтінді көшіру';
                    document.getElementById('copy-btn').style.background = '#1E88E5';
                    document.getElementById('copy-msg').style.display = 'none';
                }}, 3000);
            }}).catch(() => {{
                const ta = document.createElement('textarea');
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                document.getElementById('copy-btn').textContent = '✅ Көшірілді!';
                document.getElementById('copy-btn').style.background = '#639922';
                setTimeout(() => {{
                    document.getElementById('copy-btn').textContent = '📋 Мәтінді көшіру';
                    document.getElementById('copy-btn').style.background = '#1E88E5';
                }}, 3000);
            }});
        }}
        </script>
        """
        import streamlit.components.v1 as _components
        _components.html(copy_html, height=60)


# ──────────────────────────────────────────
# WRITING COMPONENT — ортақ HTML/JS қаңқасы
# ──────────────────────────────────────────

def build_writing_html(
    student_name: str,
    session_id: str,
    sb_url: str,
    sb_key: str,        # ← RLS анонимді ключ (тек INSERT/PATCH рұқсатты)
    total_seconds: int, # 1200 = 20 мин, 2400 = 40 мин
    min_words: int,     # 150 немесе 250
    height: int,        # textarea биіктігі пиксельде
    teacher_name: str = "Айнұр ұстазға",
) -> str:
    """
    Жазу компонентінің HTML/JS кодын қайтарады.
    app.py мен app2.py осы функцияны шақырады,
    сондықтан JS код бір жерде ғана тұрады.
    """
    timer_init = f"{total_seconds // 60:02d}:00"

    return f"""
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }}
        body {{ background: transparent; }}
        #timer-box {{
            position: fixed; top: 16px; right: 16px; z-index: 9999;
            background: #EAF3DE; border: 1.5px solid #639922;
            border-radius: 12px; padding: 10px 18px;
            text-align: center; min-width: 100px;
            transition: background 0.5s, border-color 0.5s;
        }}
        #timer-label {{ font-size: 11px; color: #3B6D11; text-transform: uppercase; margin-bottom: 2px; }}
        #timer-display {{ font-size: 26px; font-weight: 600; color: #27500A; letter-spacing: 1px; }}
        #timer-box.yellow {{ background: #FAEEDA; border-color: #EF9F27; }}
        #timer-box.yellow #timer-label {{ color: #854F0B; }}
        #timer-box.yellow #timer-display {{ color: #633806; }}
        #timer-box.red {{ background: #FCEBEB; border-color: #E24B4A; }}
        #timer-box.red #timer-label {{ color: #A32D2D; }}
        #timer-box.red #timer-display {{ color: #501313; }}
        #timer-box.done {{ background: #F09595; border-color: #E24B4A; animation: pulse 1s ease-in-out infinite; }}
        @keyframes pulse {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.04); }} }}
        #ac-bar {{
            padding: 10px 16px; border-radius: 8px; margin-bottom: 10px;
            background: #EAF3DE; border-left: 4px solid #639922;
            font-size: 13px; color: #3B6D11;
            display: flex; align-items: center; gap: 8px; transition: all 0.3s;
        }}
        .ac-dot {{ width: 10px; height: 10px; border-radius: 50%; background: #639922; flex-shrink: 0; }}
        #essay-box {{
            width: 100%; height: {height}px;
            border: 1px solid #ddd; border-radius: 8px;
            padding: 12px; font-size: 15px; line-height: 1.6;
            resize: vertical; outline: none;
            transition: border-color 0.3s;
            font-family: sans-serif; color: #333;
            background: white;
        }}
        #essay-box:focus {{ border-color: #639922; }}
        #essay-box:disabled {{ background: #f5f5f5; color: #888; cursor: not-allowed; }}
        #bottom-bar {{
            display: flex; justify-content: space-between; align-items: center;
            margin-top: 8px; margin-bottom: 4px;
        }}
        #word-count {{ font-size: 12px; font-weight: 500; color: #A32D2D; }}
        #save-status {{ font-size: 11px; color: #aaa; }}
    </style>

    <div id="timer-box">
        <div id="timer-label">Уақыт</div>
        <div id="timer-display">{timer_init}</div>
    </div>
    <div id="ac-bar">
        <div class="ac-dot" id="ac-dot"></div>
        <span id="ac-text">Античит белсенді — жұмысты адал орындаңыз</span>
    </div>
    <textarea id="essay-box" placeholder="Жауабыңызды осында теріңіз..."></textarea>
    <div id="bottom-bar">
        <span id="word-count">0 сөз</span>
        <div style="display:flex;align-items:center;gap:8px;">
            <span id="save-status"></span>
            <button id="show-teacher-btn" style="
                padding:5px 12px; background:transparent;
                border:1px solid #ddd; border-radius:6px;
                font-size:12px; color:#555; cursor:pointer;
            ">👁 {teacher_name} көрсету</button>
        </div>
    </div>

    <script>
    (function() {{
        const STUDENT  = {json.dumps(student_name)};
        const SESSION  = {json.dumps(session_id)};
        const SB_URL   = {json.dumps(sb_url)};
        const SB_KEY   = {json.dumps(sb_key)};
        const TOTAL    = {total_seconds};
        const MIN_WORDS = {min_words};

        let blur = 0, paste = 0, annulled = false;
        let started = false, left = TOTAL, timerInterval = null, expired = false;
        let draftInserted = false, submitting = false;
        let alarmCtx = null, alarmOsc = null, alarmGain = null;
        let teacherBtnActive = false;

        const tBox   = document.getElementById('timer-box');
        const tDisp  = document.getElementById('timer-display');
        const dot    = document.getElementById('ac-dot');
        const txt    = document.getElementById('ac-text');
        const bar    = document.getElementById('ac-bar');
        const essay  = document.getElementById('essay-box');
        const wcEl   = document.getElementById('word-count');
        const saveEl = document.getElementById('save-status');

        // ── Supabase helpers (тек anon key — RLS қорғайды) ──
        const HEADERS = {{
            'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY,
            'Content-Type': 'application/json', 'Prefer': 'return=minimal'
        }};

        async function sbPost(table, body) {{
            try {{
                await fetch(SB_URL + '/rest/v1/' + table, {{
                    method: 'POST', headers: HEADERS, body: JSON.stringify(body)
                }});
            }} catch(e) {{}}
        }}

        async function sbPatch(table, filter, body) {{
            try {{
                await fetch(SB_URL + '/rest/v1/' + table + '?' + filter, {{
                    method: 'PATCH', headers: HEADERS, body: JSON.stringify(body)
                }});
            }} catch(e) {{}}
        }}

        // ── Античит логгер ──
        async function logEvent(ev) {{
            if (ev === 'start') return;
            await sbPost('anticheat_events', {{
                student_name: STUDENT, session_id: SESSION,
                event_type: ev, blur_count: blur,
                paste_count: paste,
                annulled: (ev === 'annulled') ? 1 : 0
            }});
        }}

        // ── Статус жолағы ──
        function setStatus(msg, bg, bc, c, dc) {{
            bar.style.background = bg; bar.style.borderColor = bc;
            bar.style.color = c; dot.style.background = dc;
            txt.textContent = msg;
        }}

        // ── Дыбыс (тек алғашқы 10 мин) ──
        function startAlarm() {{
            if (left < TOTAL - 600) return;
            try {{
                alarmCtx = new (window.AudioContext || window.webkitAudioContext)();
                alarmGain = alarmCtx.createGain();
                alarmGain.gain.value = 0.4;
                alarmGain.connect(alarmCtx.destination);
                function playTone() {{
                    if (!alarmCtx) return;
                    alarmOsc = alarmCtx.createOscillator();
                    alarmOsc.connect(alarmGain);
                    alarmOsc.type = 'square';
                    alarmOsc.frequency.setValueAtTime(880, alarmCtx.currentTime);
                    alarmOsc.frequency.setValueAtTime(660, alarmCtx.currentTime + 0.3);
                    alarmOsc.frequency.setValueAtTime(880, alarmCtx.currentTime + 0.6);
                    alarmOsc.start(alarmCtx.currentTime);
                    alarmOsc.stop(alarmCtx.currentTime + 0.9);
                    alarmOsc.onended = () => {{ if (alarmCtx) playTone(); }};
                }}
                playTone();
                setTimeout(() => stopAlarm(), 3000);
            }} catch(e) {{}}
        }}

        function stopAlarm() {{
            try {{
                if (alarmOsc) {{ alarmOsc.onended = null; alarmOsc.stop(); alarmOsc = null; }}
                if (alarmCtx) {{ alarmCtx.close(); alarmCtx = null; }}
            }} catch(e) {{}}
        }}

        // ── Аннулирлеу ──
        function doAnnul() {{
            annulled = true;
            if (timerInterval) clearInterval(timerInterval);
            stopAlarm();
            essay.disabled = true;
            setStatus('ЖҰМЫС АННУЛИРЛЕНДІ — мұғалімге хабарланды',
                '#F09595', '#E24B4A', '#501313', '#E24B4A');
            tBox.className = 'done'; tDisp.textContent = 'XXX';
            logEvent('annulled');
        }}

        // ── Таймер ──
        function fmt(s) {{
            return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
        }}

        function startTimer() {{
            if (started) return;
            started = true;
            logEvent('timer_start');
            timerInterval = setInterval(() => {{
                if (annulled) {{ clearInterval(timerInterval); return; }}
                left--;
                tDisp.textContent = fmt(left);
                tBox.className = left <= 0 ? 'done' : left <= 60 ? 'red' : left <= 300 ? 'yellow' : '';
                if (left === 60) {{
                    setStatus('1 минут қалды! Жіберуге дайындалыңыз.',
                        '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                    logEvent('timer_warning');
                }}
                if (left <= 0) {{
                    clearInterval(timerInterval);
                    expired = true;
                    tDisp.textContent = '00:00';
                    setStatus('Уақыт бітті! Жұмысыңызды жіберіңіз.',
                        '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');
                    logEvent('timer_expired');
                }}
            }}, 1000);
        }}

        // ── Blur ──
        function onBlur() {{
            if (annulled || expired || submitting) return;
            blur++;
            startAlarm();
            if (blur === 1) {{
                setStatus('Ескерту! Басқа бетке өтпеңіз! (1/3)',
                    '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                logEvent('blur_1');
            }} else if (blur === 2) {{
                setStatus('ҚАТАҢ ЕСКЕРТУ! Тағы бір рет шықсаңыз аннулирленеді! (2/3)',
                    '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');
                logEvent('blur_2');
            }} else {{
                doAnnul();
            }}
        }}

        function onFocus() {{ stopAlarm(); }}

        // ── Мұғалімге жіберу ──
        async function sendToTeacher() {{
            const text = essay.value.trim();
            if (!text) {{ alert('Алдымен мәтін жазыңыз!'); return; }}
            teacherBtnActive = true;
            setTimeout(() => {{ teacherBtnActive = false; }}, 2000);
            // Нақты сөз саны (regex)
            const wc = (text.match(/\\b\\w+\\b/g) || []).length;
            const now = new Date().toISOString();
            const btn = document.getElementById('show-teacher-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Жіберілуде...';
            const payload = {{
                student_name: STUDENT, session_id: SESSION,
                draft_text: text, word_count: wc, submitted: 0
            }};
            try {{
                if (!draftInserted) {{
                    await fetch(SB_URL + '/rest/v1/live_drafts?session_id=eq.' + SESSION, {{
                        method: 'DELETE', headers: HEADERS
                    }});
                    const res = await fetch(SB_URL + '/rest/v1/live_drafts', {{
                        method: 'POST', headers: HEADERS, body: JSON.stringify(payload)
                    }});
                    if (res.ok || res.status === 201) draftInserted = true;
                }} else {{
                    await sbPatch('live_drafts', 'session_id=eq.' + SESSION,
                        {{ draft_text: text, word_count: wc, updated_at: now }});
                }}
                btn.textContent = '✅ Жіберілді!';
                btn.style.cssText = 'background:#EAF3DE;color:#3B6D11;border-color:#639922;';
                saveEl.textContent = 'Жіберілді: ' + new Date().toLocaleTimeString();
                setTimeout(() => {{
                    btn.disabled = false;
                    btn.textContent = '👁 {teacher_name} көрсету';
                    btn.style.cssText = '';
                }}, 3000);
            }} catch(e) {{
                btn.disabled = false;
                btn.textContent = '👁 {teacher_name} көрсету';
            }}
        }}

        // ── Textarea оқиғалары ──
        essay.addEventListener('input', () => {{
            const words = (essay.value.match(/\\b\\w+\\b/g) || []).length;
            wcEl.textContent = words + ' сөз';
            wcEl.style.color = words >= MIN_WORDS ? '#3B6D11' : words >= Math.round(MIN_WORDS*0.6) ? '#854F0B' : '#A32D2D';
            if (!started && !annulled) startTimer();
        }});

        essay.addEventListener('paste', () => {{
            if (annulled) return;
            paste++;
            setStatus('Ескерту! Мәтін қою анықталды!',
                '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
            logEvent('paste');
        }});

        document.addEventListener('visibilitychange', () => {{
            if (document.hidden) {{
                if (teacherBtnActive || submitting) return;
                onBlur();
            }} else onFocus();
        }});
        window.addEventListener('blur', () => {{
            setTimeout(() => {{
                if (teacherBtnActive || submitting) return;
                if (document.activeElement && document.activeElement.tagName === 'BUTTON') return;
                onBlur();
            }}, 100);
        }});
        window.addEventListener('focus', onFocus);
        document.getElementById('show-teacher-btn').addEventListener('click', sendToTeacher);
    }})();
    </script>
    """
