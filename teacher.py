import streamlit as st
from datetime import datetime
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="TEN: Мұғалім мониторы", page_icon="🛡", layout="wide")
st.markdown("""
<style>
  [data-testid="stSidebar"]{display:none;}
  [data-testid="collapsedControl"]{display:none;}
  .block-container{padding-top:1.5rem!important;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )


def fetch_live_drafts():
    try:
        res = (get_supabase().table("live_drafts")
               .select("*").eq("submitted", 0)
               .order("updated_at", desc=True).execute())
        return res.data or []
    except Exception:
        return []


def fetch_anticheat():
    try:
        res = (get_supabase().table("anticheat_events")
               .select("*").order("created_at", desc=True).limit(300).execute())
        return res.data or []
    except Exception:
        return []


def fetch_results():
    try:
        res = (get_supabase().table("results")
               .select("*").order("checked_at", desc=True).limit(300).execute())
        return res.data or []
    except Exception:
        return []


def fetch_all_drafts():
    """Барлық draft — жоғалған оқушыларды іздеу үшін."""
    try:
        res = (get_supabase().table("live_drafts")
               .select("*").order("updated_at", desc=True).execute())
        return res.data or []
    except Exception:
        return []


def fetch_students() -> list:
    """students кестесінен оқушылар тізімін оқиды."""
    try:
        res = (get_supabase().table("students")
               .select("*").order("name").execute())
        return res.data or []
    except Exception:
        return []


def add_student(name: str) -> bool:
    try:
        get_supabase().table("students").insert({"name": name.strip()}).execute()
        return True
    except Exception:
        return False


def delete_student(student_id: int) -> bool:
    try:
        get_supabase().table("students").delete().eq("id", student_id).execute()
        return True
    except Exception:
        return False


def fetch_results_for_journal() -> list:
    """Барлық нәтижелерді оқиды (журнал үшін)."""
    try:
        res = (get_supabase().table("results")
               .select("*").order("checked_at", desc=True).execute())
        return res.data or []
    except Exception:
        return []



    st.session_state["drafts"]     = fetch_live_drafts()
    st.session_state["ac"]         = fetch_anticheat()
    st.session_state["results"]    = fetch_results()
    st.session_state["all_drafts"] = fetch_all_drafts()
    st.session_state["updated_at"] = datetime.now().strftime("%H:%M:%S")


# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────

if "loaded" not in st.session_state:
    reload_all()
    st.session_state["loaded"] = True

for k, v in [("drafts",[]),("ac",[]),("results",[]),("all_drafts",[]),("updated_at","—")]:
    st.session_state.setdefault(k, v)


# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────

col_h1, col_h2 = st.columns([6, 1])
with col_h1:
    st.markdown("<h1 style='font-size:22px;font-weight:500;margin:0 0 4px;'>Мұғалім мониторы</h1>",
                unsafe_allow_html=True)
with col_h2:
    if st.button("🔄 Жаңарту", use_container_width=True):
        reload_all()
        st.rerun()


# ─────────────────────────────────────────
# МЕТРИКА КАРТОЧКАЛАРЫ
# ─────────────────────────────────────────

drafts_all  = st.session_state["drafts"]
events_all  = st.session_state["ac"]
results_all = st.session_state["results"]

writing_count  = len(drafts_all)
checked_count  = len(results_all)
suspect_count  = len(set(
    e.get("student_name") for e in events_all
    if e.get("blur_count", 0) >= 2 or e.get("paste_count", 0) >= 1
))
annulled_count = len(set(
    e.get("student_name") for e in events_all
    if e.get("annulled", 0)
))
started_names = set(e.get("student_name") for e in events_all
                    if e.get("event_type") == "timer_start")
checked_names = set(r.get("student_name") for r in results_all)
lost_count    = len(started_names - checked_names)


def metric_card(col, label, value, color=None):
    c = f"color:{color};" if color else ""
    col.markdown(f"""
    <div style="background:var(--color-background-secondary);border-radius:8px;
                padding:14px 12px;text-align:center;">
        <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">{label}</p>
        <p style="margin:0;font-size:24px;font-weight:500;{c}">{value}</p>
    </div>""", unsafe_allow_html=True)


m1, m2, m3, m4, m5 = st.columns(5)
metric_card(m1, "Жазып жатыр",  writing_count)
metric_card(m2, "Тексерілді",   checked_count)
metric_card(m3, "Күдікті",      suspect_count,  "#A32D2D" if suspect_count  else None)
metric_card(m4, "Аннулирленді", annulled_count, "#A32D2D" if annulled_count else None)
metric_card(m5, "⚠️ Жоғалған",  lost_count,     "#A32D2D" if lost_count     else None)

st.caption(f"Соңғы жаңарту: {st.session_state['updated_at']}")
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# ҚОЙЫНДЫЛАР
# ─────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "👁 Live",
    "🔴 Античит",
    "📊 Нәтижелер",
    "📈 Статистика",
    "⚠️ Жоғалған жұмыстар",
    "📓 Журнал",
])


# ─────────────────────────────────────────
# ТАБ 1: LIVE
# ─────────────────────────────────────────

with tab1:
    col_l1, col_l2 = st.columns([5, 1])
    with col_l1:
        st.caption(f"{len(drafts_all)} оқушы жазып жатыр")
    with col_l2:
        if st.button("🔄 Live", key="live_ref"):
            st.session_state["drafts"]     = fetch_live_drafts()
            st.session_state["updated_at"] = datetime.now().strftime("%H:%M:%S")
            st.rerun()

    if not drafts_all:
        st.info("Қазір жазып жатқан оқушы жоқ.")
    else:
        for d in drafts_all:
            name       = d.get("student_name","—")
            word_count = d.get("word_count",0)
            draft_text = d.get("draft_text","")
            updated_at = (d.get("updated_at","") or "")[:19].replace("T"," ")
            task_type  = d.get("task_type", "Task 1")
            min_w      = 250 if task_type == "Task 2" else 150
            progress   = min(word_count / min_w, 1.0)

            if word_count >= 250:
                pc,bb,bc = "#639922","#EAF3DE","#3B6D11"
            elif word_count >= 150:
                pc,bb,bc = "#EF9F27","#FAEEDA","#854F0B"
            else:
                pc,bb,bc = "#E24B4A","#FCEBEB","#A32D2D"

            st.markdown(f"""
            <div style="background:var(--color-background-primary);
                        border:0.5px solid var(--color-border-tertiary);
                        border-radius:12px;padding:12px 16px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-size:14px;font-weight:500;">{name}</span>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:11px;background:{bb};color:{bc};
                                     padding:2px 10px;border-radius:20px;">{word_count} сөз</span>
                        <span style="font-size:11px;color:var(--color-text-secondary);">{updated_at}</span>
                    </div>
                </div>
                <div style="background:var(--color-background-secondary);border-radius:4px;height:5px;overflow:hidden;">
                    <div style="width:{int(progress*100)}%;height:100%;background:{pc};border-radius:4px;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:11px;
                            color:var(--color-text-secondary);margin-top:4px;">
                    <span style="color:{pc};font-weight:500;">{int(progress*100)}%</span>
                    <span>Минимум: {min_w} сөз</span>
                </div>
            </div>""", unsafe_allow_html=True)

            if draft_text.strip():
                with st.expander("Мәтінді көру"):
                    st.text_area("", value=draft_text, height=180, disabled=True,
                                 key=f"dt_{d.get('session_id','')}",
                                 label_visibility="collapsed")


# ─────────────────────────────────────────
# ТАБ 2: АНТИЧИТ
# ─────────────────────────────────────────

with tab2:
    events = st.session_state["ac"]
    clean  = [e for e in events
              if e.get("event_type") not in ("autosave","start","timer_start")]

    if not clean:
        st.info("Оқиға жоқ.")
    else:
        cf1, cf2 = st.columns(2)
        with cf1:
            names_ac = sorted(set(e.get("student_name","") for e in clean))
            sel_name = st.selectbox("Оқушы:", ["Барлығы"]+names_ac)
        with cf2:
            etypes   = sorted(set(e.get("event_type","") for e in clean))
            sel_type = st.selectbox("Оқиға:", ["Барлығы"]+etypes)

        fil_ac = clean
        if sel_name != "Барлығы":
            fil_ac = [e for e in fil_ac if e.get("student_name")==sel_name]
        if sel_type != "Барлығы":
            fil_ac = [e for e in fil_ac if e.get("event_type")==sel_type]

        st.caption(f"{len(fil_ac)} оқиға")

        for ev in fil_ac:
            name       = ev.get("student_name","—")
            event_type = ev.get("event_type","—")
            blur       = ev.get("blur_count",0)
            paste      = ev.get("paste_count",0)
            ann        = ev.get("annulled",0)
            created_at = (ev.get("created_at","") or "")[:16]

            if ann:
                bg,bd,c,lbl = "#F09595","#E24B4A","#501313","АННУЛИРЛЕНДІ"
                bb,bc       = "#FCEBEB","#A32D2D"
            elif blur>=2 or paste>=1:
                bg,bd,c,lbl = "#FAEEDA","#EF9F27","#854F0B","КҮДІКТІ"
                bb,bc       = "#FFF3CD","#854F0B"
            elif event_type=="blur_1":
                bg,bd,c,lbl = "#FCEBEB","#E24B4A","#A32D2D","ЕСКЕРТУ"
                bb,bc       = "#FCEBEB","#A32D2D"
            elif event_type=="timer_expired":
                bg,bd,c,lbl = "#E6F1FB","#378ADD","#042C53","УАҚЫТ БІТТІ"
                bb,bc       = "#E6F1FB","#042C53"
            else:
                bg,bd,c,lbl = "#EAF3DE","#639922","#27500A",event_type
                bb,bc       = "#EAF3DE","#27500A"

            st.markdown(f"""
            <div style="background:{bg};border-left:4px solid {bd};color:{c};
                border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:6px;
                display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="font-size:13px;font-weight:500;">{name}</span>
                    <span style="font-size:12px;margin-left:8px;">
                        Blur: <b>{blur}</b> · Paste: <b>{paste}</b>
                    </span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:11px;background:{bb};color:{bc};
                                 padding:2px 10px;border-radius:20px;font-weight:500;">{lbl}</span>
                    <span style="font-size:11px;opacity:.6;">{created_at}</span>
                </div>
            </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# ТАБ 3: НӘТИЖЕЛЕР
# ─────────────────────────────────────────

with tab3:
    results = st.session_state["results"]
    if not results:
        st.info("Нәтиже жоқ.")
    else:
        cr1, cr2 = st.columns(2)
        with cr1:
            names_r = sorted(set(r.get("student_name","") for r in results))
            sel_r   = st.selectbox("Оқушы:", ["Барлығы"]+names_r, key="res_filter")
        with cr2:
            ttypes  = sorted(set(r.get("task_type","Task 1") for r in results))
            sel_t   = st.selectbox("Тапсырма түрі:", ["Барлығы"]+ttypes, key="task_filter")

        fil_r = results
        if sel_r != "Барлығы":
            fil_r = [r for r in fil_r if r.get("student_name")==sel_r]
        if sel_t != "Барлығы":
            fil_r = [r for r in fil_r if r.get("task_type")==sel_t]

        st.caption(f"{len(fil_r)} нәтиже")

        for r in fil_r:
            name      = r.get("student_name","—")
            overall   = r.get("overall","—")
            ta        = r.get("ta","—")
            cc        = r.get("cc","—")
            lr        = r.get("lr","—")
            gra       = r.get("gra","—")
            chk_at    = (r.get("checked_at","") or "")[:16]
            task_type = r.get("task_type","Task 1")

            try:
                ov = float(overall)
                if ov>=7.0:   oc,ob = "#27500A","#EAF3DE"
                elif ov>=6.0: oc,ob = "#854F0B","#FAEEDA"
                else:          oc,ob = "#A32D2D","#FCEBEB"
            except Exception:
                oc,ob = "#3C3489","#EEEDFE"

            t_badge  = "🔵" if task_type=="Task 2" else "🟣"
            ta_label = "TR" if task_type=="Task 2" else "TA"

            with st.expander(f"{t_badge} {task_type} · {name} · Overall: {overall} · {chk_at}"):
                st.markdown(f"""
                <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:12px;">
                    <div style="background:{ob};border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:{oc};">Overall</p>
                        <p style="margin:0;font-size:22px;font-weight:500;color:{oc};">{overall}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">{ta_label}</p>
                        <p style="margin:0;font-size:22px;font-weight:500;">{ta}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">CC</p>
                        <p style="margin:0;font-size:22px;font-weight:500;">{cc}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">LR</p>
                        <p style="margin:0;font-size:22px;font-weight:500;">{lr}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">GRA</p>
                        <p style="margin:0;font-size:22px;font-weight:500;">{gra}</p>
                    </div>
                </div>""", unsafe_allow_html=True)

                errors = r.get("main_errors",[])
                if errors:
                    st.markdown("**Қателер:**")
                    for e in (errors if isinstance(errors,list) else []):
                        st.warning(f"• {e}")
                if r.get("feedback"):
                    st.info(r["feedback"])


# ─────────────────────────────────────────
# ТАБ 4: СТАТИСТИКА
# ─────────────────────────────────────────

with tab4:
    if not results_all:
        st.info("Деректер жоқ.")
    else:
        total_st  = len(set(r.get("student_name","") for r in results_all))
        total_res = len(results_all)
        try:
            avg_ov = round(sum(float(r.get("overall",0)) for r in results_all)/total_res,1)
        except Exception:
            avg_ov = "—"

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:1.5rem;">
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Оқушылар</p>
                <p style="margin:0;font-size:24px;font-weight:500;">{total_st}</p>
            </div>
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Тексерулер</p>
                <p style="margin:0;font-size:24px;font-weight:500;">{total_res}</p>
            </div>
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Орташа балл</p>
                <p style="margin:0;font-size:24px;font-weight:500;">{avg_ov}</p>
            </div>
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Аннулирленді</p>
                <p style="margin:0;font-size:24px;font-weight:500;
                   color:{'#A32D2D' if annulled_count else 'inherit'};">{annulled_count}</p>
            </div>
        </div>""", unsafe_allow_html=True)

        def avg(lst):
            return round(sum(lst)/len(lst),1) if lst else "—"

        for task_label in ["Task 1","Task 2"]:
            task_res = [r for r in results_all if r.get("task_type")==task_label]
            if not task_res:
                continue
            st.subheader(f"{'🟣' if task_label=='Task 1' else '🔵'} {task_label}")
            ta_col = "TA" if task_label=="Task 1" else "TR"

            stats: dict = {}
            for r in task_res:
                n = r.get("student_name","—")
                stats.setdefault(n,{"overall":[],"ta":[],"cc":[],"lr":[],"gra":[]})
                for k in ["overall","ta","cc","lr","gra"]:
                    v = r.get(k)
                    if v is not None:
                        try: stats[n][k].append(float(v))
                        except Exception: pass

            rows = [{
                "Оқушы":  n,
                "Overall": avg(v["overall"]),
                ta_col:    avg(v["ta"]),
                "CC":      avg(v["cc"]),
                "LR":      avg(v["lr"]),
                "GRA":     avg(v["gra"]),
                "Саны":    len(v["overall"]),
            } for n,v in sorted(stats.items())]

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# ТАБ 5: ЖОҒАЛҒАН ЖҰМЫСТАР  ← ЖАҢА
# ─────────────────────────────────────────

with tab6:
    st.markdown("### 📓 Оқушылар журналы")

    # ── Оқушы қосу ──────────────────────────────
    with st.expander("➕ Оқушы қосу / өшіру", expanded=False):
        col_add1, col_add2 = st.columns([4, 1])
        with col_add1:
            new_name = st.text_input("Оқушының аты-жөні:",
                                     placeholder="Мысалы: Айгерім Сейтқали",
                                     key="new_student_name",
                                     label_visibility="collapsed")
        with col_add2:
            if st.button("➕ Қосу", use_container_width=True, key="add_student_btn"):
                if new_name.strip():
                    ok = add_student(new_name.strip())
                    if ok:
                        st.success(f"✅ {new_name.strip()} қосылды")
                        st.rerun()
                    else:
                        st.error("Қате болды. Қайталаңыз.")
                else:
                    st.warning("Аты-жөнді енгізіңіз.")

        students_list = fetch_students()
        if students_list:
            st.markdown("**Тіркелген оқушылар:**")
            for s in students_list:
                sc1, sc2 = st.columns([6, 1])
                sc1.markdown(f"👤 {s['name']}")
                if sc2.button("🗑", key=f"del_{s['id']}", help="Өшіру"):
                    delete_student(s["id"])
                    st.rerun()
        else:
            st.info("Оқушылар тізімі бос.")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Деректерді жүктеу ──────────────────────
    students_all  = fetch_students()
    journal_res   = fetch_results_for_journal()

    if not students_all:
        st.info("Алдымен оқушыларды қосыңыз (жоғарыдағы «Оқушы қосу» бөліміне өтіңіз).")
        st.stop()

    # results-ті оқушы атына қарай сөздікке топтаймыз
    from collections import defaultdict
    student_results: dict = defaultdict(list)
    for r in journal_res:
        n = (r.get("student_name") or "").strip()
        if n:
            student_results[n].append(r)

    # ── Журнал кестесі ─────────────────────────
    st.markdown("#### 📋 Жиынтық кесте")

    def safe_float(v):
        try: return float(v)
        except Exception: return None

    table_rows = []
    for s in students_all:
        name = s["name"]
        res_list = student_results.get(name, [])
        t1 = [r for r in res_list if r.get("task_type") == "Task 1"]
        t2 = [r for r in res_list if r.get("task_type") == "Task 2"]

        def last_overall(lst):
            vals = [safe_float(r.get("overall")) for r in lst if safe_float(r.get("overall")) is not None]
            return vals[0] if vals else None  # desc сортталған, бірінші = соңғы

        def avg_overall(lst):
            vals = [safe_float(r.get("overall")) for r in lst if safe_float(r.get("overall")) is not None]
            return round(sum(vals)/len(vals), 1) if vals else None

        def last_date(lst):
            if not lst: return "—"
            d = (lst[0].get("checked_at") or "")[:16].replace("T", " ")
            return d or "—"

        table_rows.append({
            "Оқушы":          name,
            "T1 соңғы":       last_overall(t1) or "—",
            "T1 орта":        avg_overall(t1) or "—",
            "T1 саны":        len(t1),
            "T2 соңғы":       last_overall(t2) or "—",
            "T2 орта":        avg_overall(t2) or "—",
            "T2 саны":        len(t2),
            "Соңғы тапсырма": last_date(sorted(res_list,
                                key=lambda x: x.get("checked_at",""), reverse=True)),
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Оқушы таңдап, прогресс графигін көру ───
    st.markdown("---")
    st.markdown("#### 📈 Оқушының прогресі")

    sel_student = st.selectbox(
        "Оқушыны таңдаңыз:",
        [s["name"] for s in students_all],
        key="journal_student_sel",
    )

    sel_task = st.radio(
        "Тапсырма түрі:",
        ["Task 1", "Task 2", "Екеуі де"],
        horizontal=True,
        key="journal_task_sel",
    )

    s_results = student_results.get(sel_student, [])
    if sel_task != "Екеуі де":
        s_results = [r for r in s_results if r.get("task_type") == sel_task]

    if not s_results:
        st.info(f"«{sel_student}» үшін нәтиже жоқ.")
    else:
        # Хронологиялық ретке келтіреміз
        s_results_sorted = sorted(s_results, key=lambda x: x.get("checked_at",""))

        import json as _json

        # Plotly-сіз таза HTML + Chart.js арқылы
        labels  = []
        overall = []
        ta_vals = []
        cc_vals = []
        lr_vals = []
        gra_vals= []
        colors  = []

        for r in s_results_sorted:
            dt  = (r.get("checked_at") or "")[:16].replace("T", " ")
            tt  = r.get("task_type","T1")
            lbl = f"{tt} · {dt}"
            labels.append(lbl)
            ov  = safe_float(r.get("overall"))
            overall.append(ov if ov is not None else "null")
            ta_vals.append(safe_float(r.get("ta")) or "null")
            cc_vals.append(safe_float(r.get("cc")) or "null")
            lr_vals.append(safe_float(r.get("lr")) or "null")
            gra_vals.append(safe_float(r.get("gra")) or "null")
            colors.append("#639922" if tt=="Task 1" else "#378ADD")

        import streamlit.components.v1 as _comp
        chart_html = f"""
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<div style="background:white;border-radius:12px;padding:16px;">
  <canvas id="progressChart" height="120"></canvas>
</div>
<script>
const ctx = document.getElementById('progressChart').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: {_json.dumps(labels)},
    datasets: [
      {{
        label: 'Overall',
        data: {overall},
        borderColor: '#27500A',
        backgroundColor: 'rgba(39,80,10,0.08)',
        borderWidth: 2.5,
        pointRadius: 5,
        tension: 0.3,
        fill: true,
      }},
      {{
        label: 'TA/TR',
        data: {ta_vals},
        borderColor: '#639922',
        borderWidth: 1.5,
        pointRadius: 3,
        tension: 0.3,
        borderDash: [4,3],
      }},
      {{
        label: 'CC',
        data: {cc_vals},
        borderColor: '#EF9F27',
        borderWidth: 1.5,
        pointRadius: 3,
        tension: 0.3,
        borderDash: [4,3],
      }},
      {{
        label: 'LR',
        data: {lr_vals},
        borderColor: '#378ADD',
        borderWidth: 1.5,
        pointRadius: 3,
        tension: 0.3,
        borderDash: [4,3],
      }},
      {{
        label: 'GRA',
        data: {gra_vals},
        borderColor: '#9B59B6',
        borderWidth: 1.5,
        pointRadius: 3,
        tension: 0.3,
        borderDash: [4,3],
      }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'bottom' }},
      title: {{
        display: true,
        text: '{sel_student} — прогресі',
        font: {{ size: 14 }},
      }}
    }},
    scales: {{
      y: {{
        min: 3,
        max: 9,
        ticks: {{ stepSize: 0.5 }},
        grid: {{ color: '#f0f0f0' }},
      }},
      x: {{
        ticks: {{ maxRotation: 30, font: {{ size: 10 }} }},
      }}
    }}
  }}
}});
</script>"""
        _comp.html(chart_html, height=340)

        # ── Толық тарих ──────────────────────
        st.markdown("**Толық тарих:**")
        for r in reversed(s_results_sorted):
            ov   = r.get("overall","—")
            ta   = r.get("ta","—")
            cc   = r.get("cc","—")
            lr   = r.get("lr","—")
            gra  = r.get("gra","—")
            tt   = r.get("task_type","—")
            dt   = (r.get("checked_at","") or "")[:16].replace("T"," ")
            badge = "🟣" if tt=="Task 1" else "🔵"
            try:
                ov_f = float(ov)
                oc = "#27500A" if ov_f>=7 else "#854F0B" if ov_f>=6 else "#A32D2D"
                ob = "#EAF3DE" if ov_f>=7 else "#FAEEDA" if ov_f>=6 else "#FCEBEB"
            except Exception:
                oc, ob = "#3C3489","#EEEDFE"

            with st.expander(f"{badge} {tt} · Overall: **{ov}** · {dt}"):
                st.markdown(f"""
                <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;">
                  <div style="background:{ob};border-radius:8px;padding:10px;text-align:center;">
                    <p style="margin:0 0 2px;font-size:11px;color:{oc};">Overall</p>
                    <p style="margin:0;font-size:20px;font-weight:600;color:{oc};">{ov}</p>
                  </div>
                  <div style="background:#F4F4F4;border-radius:8px;padding:10px;text-align:center;">
                    <p style="margin:0 0 2px;font-size:11px;color:#555;">TA/TR</p>
                    <p style="margin:0;font-size:20px;font-weight:600;">{ta}</p>
                  </div>
                  <div style="background:#F4F4F4;border-radius:8px;padding:10px;text-align:center;">
                    <p style="margin:0 0 2px;font-size:11px;color:#555;">CC</p>
                    <p style="margin:0;font-size:20px;font-weight:600;">{cc}</p>
                  </div>
                  <div style="background:#F4F4F4;border-radius:8px;padding:10px;text-align:center;">
                    <p style="margin:0 0 2px;font-size:11px;color:#555;">LR</p>
                    <p style="margin:0;font-size:20px;font-weight:600;">{lr}</p>
                  </div>
                  <div style="background:#F4F4F4;border-radius:8px;padding:10px;text-align:center;">
                    <p style="margin:0 0 2px;font-size:11px;color:#555;">GRA</p>
                    <p style="margin:0;font-size:20px;font-weight:600;">{gra}</p>
                  </div>
                </div>""", unsafe_allow_html=True)
                fb = r.get("feedback","")
                if fb:
                    st.info(fb)

with tab5:
    st.markdown("### ⚠️ Жоғалған жұмыстар")
    st.caption(
        "**timer_start** оқиғасы бар (жұмыс бастаған), "
        "бірақ **results** кестесінде жоқ оқушылар."
    )

    if st.button("🔄 Жаңарту", key="lost_ref"):
        reload_all()
        st.rerun()

    # Жұмыс бастаған оқушылар (ең соңғы session_id)
    started: dict = {}
    for e in reversed(st.session_state["ac"]):
        if e.get("event_type") == "timer_start":
            n = e.get("student_name","")
            if n and n not in started:
                started[n] = e.get("session_id","")

    checked_set = set(r.get("student_name","") for r in st.session_state["results"])
    lost        = {n: s_id for n, s_id in started.items() if n not in checked_set}

    if not lost:
        st.success("✅ Барлық оқушының жұмысы тексерілген!")
    else:
        st.warning(f"**{len(lost)} оқушының жұмысы табылмады**")

        draft_map = {d.get("session_id",""): d
                     for d in st.session_state["all_drafts"]}

        for name, s_id in sorted(lost.items()):
            draft    = draft_map.get(s_id)
            has_text = bool(draft and draft.get("draft_text","").strip())
            wc       = draft.get("word_count",0) if draft else 0
            upd      = (draft.get("updated_at","") or "")[:16] if draft else "—"
            status   = f"📄 Мәтін бар ({wc} сөз)" if has_text else "❌ Мәтін жоқ"

            with st.expander(f"👤 {name}  —  {status}"):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Session ID:** `{s_id}`")
                c2.markdown(f"**Соңғы сақтау:** {upd}")

                if has_text:
                    st.text_area("Мәтін:", value=draft["draft_text"],
                                 height=200, disabled=True,
                                 key=f"lost_{s_id}")
                    st.info(
                        "💡 Мәтін бар — оқушының браузерінде **Тексеруге жіберу** "
                        "батырмасын қайта басыңыз. Немесе **Жаңарту** батырмасын "
                        "басып, оқушы қайта жіберсін."
                    )
                else:
                    # Anticheat тарихы
                    ev_list = [e.get("event_type","") for e in st.session_state["ac"]
                               if e.get("student_name")==name]
                    st.error("Мәтін Supabase-те жоқ.")
                    if ev_list:
                        st.markdown(f"**Тіркелген оқиғалар:** `{', '.join(ev_list)}`")
                    st.warning(
                        "Мүмкін себептер: оқушы жазбаған, "
                        "интернет үзілген, немесе беттi жаңартқан."
                    )
