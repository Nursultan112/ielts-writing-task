import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import time as _time
from PIL import Image
from datetime import datetime

from utils import (
    get_supabase,
    get_latest_draft,
    save_result,
    count_words,
    call_gemini_with_retry,
    show_result_page,
    build_writing_html,
)

st.set_page_config(page_title="TEN: IELTS Task 1", page_icon="✏️", layout="centered")
st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)


def writing_component(student_name: str, session_id: str) -> None:
    sb_url = st.secrets["supabase"]["url"]
    sb_key = st.secrets["supabase"]["key"]
    html = build_writing_html(
        student_name=student_name,
        session_id=session_id,
        sb_url=sb_url,
        sb_key=sb_key,
        total_seconds=1200,   # 20 минут
        min_words=150,
        height=280,
    )
    components.html(html, height=380)


# ──────────────────────────────────────────
# ОҚУШЫ БЕТІ
# ──────────────────────────────────────────
st.title("✏️ IELTS Writing Task 1")
st.caption("Тапсырманы орындап, жауабыңызды жіберіңіз.")
st.markdown("---")

st.subheader("1. Аты-жөніңізді жазыңыз")
student_name = st.text_input("", placeholder="Мысалы: Айгерім Сейтқали",
                              label_visibility="collapsed")

st.subheader("2. Тапсырма суретін жүктеңіз")
uploaded_file = st.file_uploader("", type=["png", "jpg", "jpeg"],
                                  label_visibility="collapsed")
image = None
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Тапсырма", width=400)

if student_name.strip() and uploaded_file is not None:
    st.markdown("---")

    session_key = f"sid_{student_name.strip().replace(' ', '_')}"
    if session_key not in st.session_state:
        st.session_state[session_key] = datetime.now().strftime("%Y%m%d%H%M%S")
    session_id = st.session_state[session_key]

    annul_key      = f"annulled_{session_id}"
    done_key       = f"done_{session_id}"
    submitting_key = f"submitting_{session_id}"

    st.session_state.setdefault(annul_key,      False)
    st.session_state.setdefault(done_key,        False)
    st.session_state.setdefault(submitting_key,  False)

    # ── Аннулирленді ──
    if st.session_state[annul_key]:
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    # ── Нәтиже бар ──
    if st.session_state[done_key]:
        result     = st.session_state.get(f"result_{session_id}", {})
        essay_text = st.session_state.get(f"essay_text_{session_id}", "")
        if result:
            show_result_page(result, essay_text, task_type="Task 1")
        st.stop()

    # ── Тексеру жүріп жатыр ──
    if st.session_state[submitting_key]:
        with st.spinner("⏳ Жұмысыңыз тексерілуде..."):
            # Supabase-тен мәтінді аламыз (макс 8 сек)
            draft = None
            for _ in range(4):
                draft = get_latest_draft(session_id)
                if draft and draft.get("draft_text", "").strip():
                    break
                _time.sleep(2)

            essay_text = draft.get("draft_text", "").strip() if draft else ""

            if not essay_text:
                st.session_state[submitting_key] = False
                st.error("Жауап табылмады. Жазып болғаннан кейін бірнеше секунд күтіп жіберіңіз!")
                st.rerun()
            else:
                genai.configure(api_key=st.secrets["gemini"]["api_key"])
                model = genai.GenerativeModel(
                    "gemini-2.5-flash",
                    generation_config={
                        "response_mime_type": "application/json",
                        "max_output_tokens": 8000,
                        "temperature": 0,
                    },
                )
                word_count = count_words(essay_text)

                prompt = f"""You are an expert and strict IELTS Writing Examiner. Evaluate the student's IELTS Academic Task 1 report based on the provided image.
CRITICAL RULES & SCORING PENALTIES (NEVER IGNORE):
The student's response is exactly {word_count} words long. Apply the following scoring rules based on length:
- Under 50 words: Maximum Overall Score is 2.5.
- 50 to 99 words: Maximum Overall Score is 4.5.
- 100 to 139 words: Maximum Overall Score is 6.5. Deduct up to 1.0 band from Task Achievement (TA) because short essays usually lack key details. However, evaluate CC, LR, and GRA completely normally based on the actual quality of the text written. Do not artificially lower them.
- 140+ words: Evaluate normally. Do not apply any length penalties.
GRADING CRITERIA:
1. Score each category (TA, CC, LR, GRA) using exact 0.5 increments only (e.g., 5.0, 5.5, 6.0).
2. Calculate the 'overall' score as the exact mathematical average of TA, CC, LR, and GRA. Round down to the nearest 0.5 if necessary.
LANGUAGE & FEEDBACK REQUIREMENT:
The 'main_errors' array and 'feedback' string MUST be written entirely in natural, professional, and grammatically correct Kazakh language.
Base your feedback strictly on the student's actual text. You MUST quote specific words or sentences the student used to prove your points.
OUTPUT FORMAT:
Return ONLY a valid JSON object. Do not include markdown formatting like ```json, do not include explanations, and do not write any text outside the JSON structure.
Use this exact JSON structure:
{{
  "overall": 0.0,
  "TA": 0.0,
  "CC": 0.0,
  "LR": 0.0,
  "GRA": 0.0,
  "main_errors": [
    "Бірінші нақты қате...",
    "Екінші нақты қате..."
  ],
  "feedback": "### 1. Task Achievement (Тапсырманың орындалуы): **[Score]**\\n* [1-2 sentences explaining what key features were covered]\\n* [1 sentence evaluating their Overview]\\n\\n### 2. Coherence and Cohesion (Логика және байланыс): **[Score]**\\n* [Comment on paragraphing and logical flow]\\n* [Quote and evaluate the linking words used]\\n* **Ұсыныс:** [Actionable advice]\\n\\n### 3. Lexical Resource (Сөздік қор): **[Score]**\\n* [Quote specific good vocabulary used]\\n* [Point out precise errors in collocations or word choice]\\n\\n### 4. Grammatical Range and Accuracy (Грамматика): **[Score]**\\n* [Comment on sentence structures]\\n* [Point out specific grammatical errors]\\n\\n---\\n### Қалай жақсартуға болады? (Tips for [Overall + 0.5]+)\\n1. **[Specific Tip 1]:** [Actionable advice based on their mistakes]\\n2. **[Specific Tip 2]:** [Actionable advice]\\n\\n**Қорытынды:** [Brief encouraging summary]"
}}"""

                result = call_gemini_with_retry(model, [prompt, image, essay_text])

                if result:
                    # Кілттерді қалыпқа келтіру
                    result["TA"]      = result.get("TA",      result.get("ta",      0))
                    result["CC"]      = result.get("CC",      result.get("cc",      0))
                    result["LR"]      = result.get("LR",      result.get("lr",      0))
                    result["GRA"]     = result.get("GRA",     result.get("gra",     0))
                    result["overall"] = result.get("overall", result.get("Overall", 0))

                    save_result(student_name.strip(), result, session_id, task_type="Task 1")
                    st.session_state[f"result_{session_id}"]     = result
                    st.session_state[f"essay_text_{session_id}"] = essay_text
                    st.session_state[done_key]       = True
                    st.session_state[submitting_key] = False
                else:
                    st.session_state[submitting_key] = False

                st.rerun()
    else:
        # ── Жазу беті ──
        st.subheader("3. Жауабыңызды жазыңыз")
        st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")
        writing_component(student_name.strip(), session_id)

        if st.button("✅ Тексеруге жіберу", type="primary",
                     use_container_width=True, key=f"submit_{session_id}"):
            st.session_state[submitting_key] = True
            st.rerun()

elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")
