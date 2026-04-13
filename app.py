import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import time as _time
from PIL import Image
from datetime import datetime

from utils import (
    get_supabase, get_latest_draft, save_result,
    count_words, call_gemini_with_retry, show_result_page,
    build_writing_html,
)

st.set_page_config(page_title="TEN: IELTS Task 1", page_icon="✏️", layout="centered")
st.markdown("""
<style>
  [data-testid="stSidebar"]{display:none;}
  [data-testid="collapsedControl"]{display:none;}
</style>
""", unsafe_allow_html=True)


def writing_component(student_name: str, session_id: str):
    html = build_writing_html(
        student_name=student_name, session_id=session_id,
        sb_url=st.secrets["supabase"]["url"],
        sb_key=st.secrets["supabase"]["key"],
        total_seconds=1200, min_words=150, height=280,
    )
    components.html(html, height=400)


# ──────────────────────────────────────────
st.title("✏️ IELTS Writing Task 1")
st.caption("Тапсырманы орындап, жауабыңызды жіберіңіз.")
st.markdown("---")

st.subheader("1. Аты-жөніңізді жазыңыз")
student_name = st.text_input("", placeholder="Мысалы: Айгерім Сейтқали",
                              label_visibility="collapsed")

st.subheader("2. Тапсырма суретін жүктеңіз")
uploaded_file = st.file_uploader("", type=["png","jpg","jpeg"],
                                  label_visibility="collapsed")
image = None
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Тапсырма", width=400)

if student_name.strip() and uploaded_file is not None:
    st.markdown("---")

    # Session ID — аты + күн/уақыт негізінде бірегей
    skey = f"sid_{student_name.strip().replace(' ','_')}"
    if skey not in st.session_state:
        st.session_state[skey] = datetime.now().strftime("%Y%m%d%H%M%S")
    sid = st.session_state[skey]

    annul_key = f"annulled_{sid}"
    done_key  = f"done_{sid}"
    sub_key   = f"submitting_{sid}"
    st.session_state.setdefault(annul_key, False)
    st.session_state.setdefault(done_key,  False)
    st.session_state.setdefault(sub_key,   False)

    # ── Аннулирленген ──
    if st.session_state[annul_key]:
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    # ── Нәтиже дайын ──
    if st.session_state[done_key]:
        result = st.session_state.get(f"result_{sid}", {})
        essay  = st.session_state.get(f"essay_{sid}",  "")
        if result:
            show_result_page(result, essay, "Task 1")
        st.stop()

    # ── Тексеру процесі ──
    if st.session_state[sub_key]:
        with st.spinner("⏳ Жұмысыңыз тексерілуде..."):

            # forceSave() JS-те мәтінді жазады.
            # Python жағы 3 сек күтіп, содан кейін draft іздейді.
            _time.sleep(3)

            # Максимум 25 сек күтеміз (1 сек × 25)
            draft = None
            for i in range(25):
                draft = get_latest_draft(sid)
                if draft and draft.get("draft_text","").strip():
                    break
                _time.sleep(1)

            essay_text = (draft or {}).get("draft_text","").strip()

            if not essay_text:
                st.session_state[sub_key] = False
                st.error(
                    "⚠️ **Мәтін табылмады.**\n\n"
                    "**Себебі:** Мәтін Supabase-ке сақталмаған.\n\n"
                    "**Не істеу керек:**\n"
                    "1. Беттi жаңартпаңыз\n"
                    "2. **👁 Айнұр ұстазға көрсету** батырмасын басыңыз\n"
                    "3. ✅ деп шыққан соң — **Тексеруге жіберу** батырмасын қайта басыңыз"
                )
                st.rerun()

            # ── Gemini бағалау ──
            genai.configure(api_key=st.secrets["gemini"]["api_key"])
            model = genai.GenerativeModel(
                "gemini-2.5-flash",
                generation_config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 8000,
                    "temperature": 0,
                },
            )
            wc = count_words(essay_text)
            prompt = f"""You are an expert and strict IELTS Writing Examiner. Evaluate the student's IELTS Academic Task 1 report based on the provided image.
CRITICAL RULES:
The student's response is exactly {wc} words.
- Under 50 words: max Overall 2.5
- 50-99 words: max Overall 4.5
- 100-139 words: max Overall 6.5, deduct up to 1.0 from TA
- 140+ words: evaluate normally
Score TA, CC, LR, GRA in 0.5 increments. Overall = average of four, round down to nearest 0.5.
'main_errors' and 'feedback' MUST be in Kazakh. Quote the student's actual words.
Return ONLY valid JSON, no markdown:
{{"overall":0.0,"TA":0.0,"CC":0.0,"LR":0.0,"GRA":0.0,
"main_errors":["қате 1","қате 2"],
"feedback":"### 1. Task Achievement: **[Score]**\\n* [...]\\n\\n### 2. Coherence and Cohesion: **[Score]**\\n* [...]\\n\\n### 3. Lexical Resource: **[Score]**\\n* [...]\\n\\n### 4. Grammatical Range and Accuracy: **[Score]**\\n* [...]\\n\\n---\\n### Қалай жақсартуға болады?\\n1. **[Кеңес 1]:** [...]\\n2. **[Кеңес 2]:** [...]\\n\\n**Қорытынды:** [...]"}}"""

            result = call_gemini_with_retry(model, [prompt, image, essay_text])

            if result:
                result["TA"]      = result.get("TA",      result.get("ta",      0))
                result["CC"]      = result.get("CC",      result.get("cc",      0))
                result["LR"]      = result.get("LR",      result.get("lr",      0))
                result["GRA"]     = result.get("GRA",     result.get("gra",     0))
                result["overall"] = result.get("overall", result.get("Overall", 0))
                save_result(student_name.strip(), result, sid, "Task 1")
                st.session_state[f"result_{sid}"] = result
                st.session_state[f"essay_{sid}"]  = essay_text
                st.session_state[done_key] = True
                st.session_state[sub_key]  = False
            else:
                st.session_state[sub_key] = False

            st.rerun()

    else:
        # ── Жазу беті ──
        st.subheader("3. Жауабыңызды жазыңыз")
        st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")
        writing_component(student_name.strip(), sid)

        st.info(
            "💡 Жіберер алдында **👁 Айнұр ұстазға көрсету** батырмасын бір рет басыңыз — "
            "мәтін сенімді сақталады.",
            icon="ℹ️",
        )

        # Submit батырмасы: басылғанда JS forceSave() іске қосылады,
        # содан кейін Streamlit sub_key=True қояды
        submit_html = f"""
        <script>
        async function doSubmit() {{
          const btn = document.getElementById('sub-btn');
          btn.disabled = true;
          btn.textContent = '⏳ Сақталуда...';

          // writing_component iframe-ін табамыз
          let saved = false;
          const frames = window.parent.document.querySelectorAll('iframe');
          for (const f of frames) {{
            try {{
              if (typeof f.contentWindow.forceSave === 'function') {{
                saved = await f.contentWindow.forceSave();
                break;
              }}
            }} catch(e) {{}}
          }}

          if (saved) {{
            btn.textContent = '✅ Жіберілді!';
            // Streamlit-тің hidden формасын trigger етеміз
            window.parent.postMessage({{type:'streamlit:setComponentValue', value:true}}, '*');
          }} else {{
            btn.disabled = false;
            btn.textContent = '✅ Тексеруге жіберу';
          }}
        }}
        </script>
        <button id="sub-btn" onclick="doSubmit()" style="
          width:100%;padding:13px;margin-top:6px;
          background:#639922;color:white;border:none;
          border-radius:8px;font-size:16px;font-weight:500;cursor:pointer;">
          ✅ Тексеруге жіберу
        </button>
        """
        components.html(submit_html, height=60)

        # Streamlit батырмасы (JS forceSave болмаса fallback)
        if st.button("✅ Тексеруге жіберу", type="primary",
                     use_container_width=True, key=f"sub_{sid}"):
            st.session_state[sub_key] = True
            st.rerun()

elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")
