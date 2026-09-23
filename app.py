import streamlit as st
import google.generativeai as genai
import json
import random
import string
import time
import pandas as pd
from supabase import create_client, Client

# ========================================================
# 🔑 مفاتيح الربط (مع نظام قراءة ذكي من secrets أو قيم مباشرة)
# ========================================================
GEMINI_API_KEY = st.secrets.get("AQ.Ab8RN6Kp696FTmr7JoZn7lJbw747xx1oLsY1dA_s7VdNm9MSgw")
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

# تهيئة الاتصالات
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-3.6-flash"

# --- ضبط الصفحة وتنسيق الاتجاه (RTL) ---
st.set_page_config(
    page_title="منصة منارة التعليمية الذكية",
    page_icon="🎓",
    layout="wide"
)

st.markdown("""
<style>
    .stApp { direction: rtl; text-align: right; }
    p, div, span, h1, h2, h3, h4, label { text-align: right !important; }
    .stRadio label { direction: rtl !important; text-align: right !important; }
    div[data-testid="stExpander"] { direction: rtl; text-align: right; }
</style>
""", unsafe_allow_html=True)

# بيانات المعلمين
TEACHERS_DB = {
    "أ. عمر": {"password": "bio123", "subject": "الأحياء"},
    "أ. سيد": {"password": "math123", "subject": "الرياضيات"},
    "أ. رجب": {"password": "islamic123", "subject": "التربية الإسلامية"},
    "أ. محمد": {"password": "chm123", "subject": "الكيمياء"}
}

def generate_quiz_code(subject):
    code_chars = ''.join(random.choices(string.digits, k=4))
    prefix = subject[:3].strip()
    return f"{prefix}-{code_chars}"

# ========================================================
# 🧠 محرك الذكاء الاصطناعي (قراءة بصرية كاملة للـ PDF)
# ========================================================
def create_smart_quiz_from_pdf(pdf_bytes, subject, title, num_q, diff, allow_tf, make_summary):
    """الذكاء الاصطناعي يقرأ الـ PDF كملف أصلي متكامل دون تكسير النصوص العربية"""
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.25
        }
    )

    types_prompt = "جميع الأسئلة اختيار من متعدد بـ 4 خيارات (إجابة واحدة صحيحة، و3 خيارات ذكية ومضللة تقيس الفهم العميق)."
    if allow_tf:
        types_prompt += " يمكنك تنويع الأسئلة بتضمين أسئلة (صح أو خطأ) يكون الخياران فقط: 1) صح، 2) خطأ."

    prompt = f"""
    أنت موجه تربوي وخبير امتحانات متخصص في مادة ({subject}).
    مهمتك: قراءة ملف الـ PDF المرفق لدرس: ({title}) بعناية فائقة.

    المعايير التربوية الإلزامية:
    1. استخرج المعلومات والجداول والمفاهيم بدقة من صلب الملف المرفق.
    2. صغ أسئلة تقيس (الفهم، الاستيعاب، والتحليل) بمستوى صعوبة: ({diff}) وابتعد عن الأسئلة السطحية أو التافهة.
    3. عدد الأسئلة المطلوب بدقة: بالضبط {num_q} أسئلة.
    4. نمط الأسئلة: {types_prompt}.
    5. إذا كان make_summary = {make_summary}، اكتب ملخصاً في حقل summary يلخص أهم 4 أفكار رئيسية بالدرس، وإلا اتركه فارغاً.

    أرجع كائن JSON حصرياً وصالحاً 100% بالهيكل التالي:
    {{
      "summary": "نص الملخص التمهيدي هنا...",
      "questions": [
        {{
          "id": 1,
          "question": "نص السؤال الدقيق من واقع الدرس؟",
          "options": ["الخيار الأول", "الخيار الثاني", "الخيار الثالث", "الخيار الرابع"],
          "correct_index": 0,
          "explanation": "شرح علمي مدعم بالنص لسبب صحة هذا الخيار واستبعاد الباقي"
        }}
      ]
    }}
    ملاحظة: correct_index هو رقم الفهرس للإجابة الصحيحة (0 للرابع، 1 للثاني، 2 للثالث، 3 للرابع).
    """

    # نظام المحاولة التلقائية مع حماية من ضغط الـ 429
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = model.generate_content([
                {"mime_type": "application/pdf", "data": pdf_bytes},
                prompt
            ])
            return json.loads(res.text)
        except Exception as e:
            if ("429" in str(e) or "Quota exceeded" in str(e)) and attempt < max_retries - 1:
                time.sleep(5)
                continue
            raise e

def analyze_class_submissions(subject, submissions_data):
    """تحليل الذكاء الاصطناعي لنقاط ضعف الصف ككل"""
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    أنت مستشار تربوي. إليك بيانات أداء الطلاب في اختبارات مادة ({subject}):
    {json.dumps(submissions_data, ensure_ascii=False)}

    المطلوب: قدم تقريراً تشخيصياً واضحاً وموجهاً للأستاذ:
    1. المفاهيم أو الأسئلة التي تكررت فيها أخطاء الطلاب.
    2. نصائح وتوصيات تربوية للتركيز عليها وإعادة شرحها في الحصة القادمة.
    """
    res = model.generate_content(prompt)
    return res.text

def ask_ai_tutor(question, student_ans, correct_ans, explanation):
    """المعلم الذكي الخاص بالطالب لشرح السؤال الخاطئ"""
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    أنت معلم خصوصي ودود ومشجع. الطالب أخطأ في هذا السؤال:
    - السؤال: {question}
    - إجابة الطالب: {student_ans}
    - الإجابة الصحيحة: {correct_ans}
    - التفسير: {explanation}

    اشرح للطالب بأسلوب مبسط جداً وداعم سبب عدم صحة إجابته، وكيف يتذكر القاعدة الصحيحة دائماً.
    """
    res = model.generate_content(prompt)
    return res.text

# =======================================================
# الواجهة الرئيسية
# =======================================================
st.title("🎓 نظام منارة الذكي للاختبارات والتقييم")
role = st.sidebar.radio("اختر البوابة:", ["👨‍🏫 بوابة المعلم", "👨‍🎓 بوابة الطالب"])

# =======================================================
# 1. بوابة المعلم
# =======================================================
if role == "👨‍🏫 بوابة المعلم":
    if 'logged_teacher' not in st.session_state:
        st.session_state['logged_teacher'] = None

    if not st.session_state['logged_teacher']:
        st.subheader("🔒 تسجيل الدخول لأساتذة المواد")
        t_user = st.selectbox("اسم المعلم:", list(TEACHERS_DB.keys()))
        t_pwd = st.text_input("كلمة المرور:", type="password")

        if st.button("تسجيل الدخول", type="primary"):
            if t_pwd == TEACHERS_DB[t_user]["password"]:
                st.session_state['logged_teacher'] = t_user
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة.")
    else:
        teacher = st.session_state['logged_teacher']
        subject = TEACHERS_DB[teacher]["subject"]

        st.sidebar.success(f"👨‍🏫 **المعلم:** {teacher}\n\n📚 **المادة:** {subject}")
        if st.sidebar.button("🚪 تسجيل الخروج"):
            st.session_state['logged_teacher'] = None
            st.rerun()

        tab1, tab2, tab3 = st.tabs([
            "✨ إنشاء اختبار ذكي من الـ PDF", 
            "📚 بنك الاختبارات المتاحة", 
            "📊 تحليلات الذكاء الاصطناعي والنتائج"
        ])

        with tab1:
            st.subheader("🤖 توليد اختبار بقراءة مباشرة للـ PDF (فهم الجداول والمفاهيم)")
            c_title, c_num, c_diff = st.columns([2, 1, 1])
            with c_title:
                quiz_title = st.text_input("عنوان الدرس / الاختبار:", placeholder="مثال: الخلية والأنسجة الحية")
            with c_num:
                num_q = st.number_input("عدد الأسئلة:", 1, 25, 5)
            with c_diff:
                diff = st.selectbox("مستوى الصعوبة:", ["سهل", "متوسط", "متقدم"])

            st.markdown("#### ⚙️ خيارات الاختبار (اختيارية):")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                enable_shuffle = st.checkbox("🔀 عشوائية الأسئلة والخيارات", value=True, help="ترتيب مختلف لكل طالب لمنع الغش")
            with col2:
                enable_timer = st.checkbox("⏱️ تفعيل مؤقت زمني", value=False)
            with col3:
                allow_tf = st.checkbox("⚖️ تضمين صح وخطأ", value=False)
            with col4:
                enable_summary = st.checkbox("📝 توليد ملخص تمهيدي", value=True, help="ملخص يقرأه الطالب قبل بدء الحل")

            timer_val = None
            if enable_timer:
                timer_val = st.number_input("مدة الاختبار بالدقائق:", 1, 120, 10)

            pdf_file = st.file_uploader("ارفع ملف الدرس بصيغة (PDF):", type=["pdf"])

            if pdf_file and quiz_title and st.button("🚀 توليد الاختبار ونشره", type="primary"):
                with st.spinner("يقوم الذكاء الاصطناعي الآن بقراءة صفحات الـ PDF بصرياً وهندسة الأسئلة الاحترافية..."):
                    try:
                        ai_data = create_smart_quiz_from_pdf(
                            pdf_file.getvalue(), subject, quiz_title, num_q, diff, allow_tf, enable_summary
                        )
                        quiz_code = generate_quiz_code(subject)

                        supabase.table("quizzes").insert({
                            "quiz_code": quiz_code,
                            "teacher_name": teacher,
                            "subject": subject,
                            "lesson_title": quiz_title,
                            "difficulty": diff,
                            "timer_minutes": timer_val if enable_timer else None,
                            "shuffle_enabled": enable_shuffle,
                            "summary": ai_data.get("summary") if enable_summary else None,
                            "questions": ai_data.get("questions", [])
                        }).execute()

                        st.success(f"🎉 تم إنشاء ونشر الاختبار بنجاح! كود الاختبار للطلاب هو: **{quiz_code}**")
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء المعالجة: {e}")

        with tab2:
            st.subheader(f"📚 سجل اختبارات مادة ({subject})")
            q_res = supabase.table("quizzes").select("*").eq("subject", subject).order("created_at", desc=True).execute()

            if q_res.data:
                for qz in q_res.data:
                    with st.expander(f"🔑 كود: [{qz.get('quiz_code')}] - {qz['lesson_title']} ({len(qz['questions'])} أسئلة)"):
                        st.write(f"⏱️ **المؤقت:** {qz.get('timer_minutes')} دقيقة" if qz.get('timer_minutes') else "⏱️ **المؤقت:** مفتوح")
                        st.write(f"🔀 **عشوائية الأسئلة:** {'مفعلة' if qz.get('shuffle_enabled') else 'معطلة'}")
                        if qz.get("summary"):
                            st.info(f"💡 **الملخص المرفق للدرس:**\n{qz.get('summary')}")

                        st.markdown("---")
                        for idx, q in enumerate(qz["questions"]):
                            st.markdown(f"**س{idx+1}: {q['question']}**")
                            for o_idx, opt in enumerate(q['options']):
                                correct_mark = "✅ " if o_idx == q.get('correct_index') else ""
                                st.write(f"- {correct_mark}{opt}")
                            st.caption(f"التفسير التربوي: {q.get('explanation')}")

                        if st.button("🗑️ حذف هذا الاختبار", key=f"del_{qz['id']}"):
                            supabase.table("quizzes").delete().eq("id", qz['id']).execute()
                            st.rerun()
            else:
                st.info("لا توجد اختبارات منشورة حتى الآن.")

        with tab3:
            st.subheader(f"📊 نتائج وتقارير مادة ({subject})")
            sub_res = supabase.table("submissions").select("*").eq("subject", subject).order("created_at", desc=True).execute()

            if sub_res.data:
                df = pd.DataFrame(sub_res.data)
                col1, col2, col3 = st.columns(3)
                col1.metric("إجمالي المحاولات", len(df))
                col2.metric("متوسط الدرجات", f"{df['score'].mean():.1f} / {df['total'].iloc[0] if len(df) else 0}")
                col3.metric("نسبة النجاح", f"{(len(df[df['score'] >= df['total']/2]) / len(df)) * 100:.1f}%")

                st.divider()

                if st.button("🤖 طلب تقرير تشخيص نقاط ضعف الصف بالذكاء الاصطناعي", type="primary"):
                    with st.spinner("جاري قراءة إجابات الطلاب واستخراج الملاحظات التوجيهية..."):
                        report = analyze_class_submissions(subject, sub_res.data[:30])
                        st.markdown("### 📋 التقرير التشخيصي الذكي للأستاذ:")
                        st.success(report)

                st.write("---")
                export_df = df[['student_name', 'score', 'total', 'created_at']].copy()
                export_df.columns = ['اسم الطالب', 'الدرجة', 'المجموع', 'التاريخ']
                csv = export_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 تحميل النتائج كملف Excel (CSV)", csv, f"نتائج_{subject}.csv", "text/csv")

                st.dataframe(export_df, use_container_width=True)
            else:
                st.info("لا توجد أي تسليمات مسجلة من الطلاب حتى الآن.")

# =======================================================
# 2. بوابة الطالب
# =======================================================
elif role == "👨‍🎓 بوابة الطالب":
    st.header("بوابة الاختبارات التفاعلية للطلاب")

    access_type = st.radio("طريقة الانضمام للاختبار:", ["🔑 إدخال كود الاختبار (Quiz Code)", "📚 اختيار من قائمة المواد"], horizontal=True)
    target_quiz = None

    if access_type == "🔑 إدخال كود الاختبار (Quiz Code)":
        entered_code = st.text_input("أدخل كود الاختبار (مثال: أحيا-1234):").strip()
        if entered_code:
            res_code = supabase.table("quizzes").select("*").eq("quiz_code", entered_code).execute()
            if res_code.data:
                target_quiz = res_code.data[0]
            else:
                st.error("الكود غير صحيح أو أن الاختبار غير متاح.")
    else:
        subject_names = list(set([v["subject"] for v in TEACHERS_DB.values()]))
        chosen_subj = st.selectbox("اختر المادة الدراسية:", subject_names)
        quizzes_avail = supabase.table("quizzes").select("*").eq("subject", chosen_subj).execute()

        if quizzes_avail.data:
            quiz_options = {f"{item['lesson_title']} (كود: {item.get('quiz_code')})": item for item in quizzes_avail.data}
            selected_title = st.selectbox("اختر الدرس المطلوب:", list(quiz_options.keys()))
            target_quiz = quiz_options[selected_title]
        else:
            st.warning("لا توجد اختبارات منشورة لهذه المادة حالياً.")

    if target_quiz:
        st.divider()
        st.markdown(f"### 📝 اختبار: {target_quiz['lesson_title']} ({target_quiz['subject']})")

        if target_quiz.get("summary"):
            with st.expander("📖 ملخص سريع لأهم نقاط الدرس قبل البدء", expanded=True):
                st.write(target_quiz.get("summary"))

        if target_quiz.get("timer_minutes"):
            st.warning(f"⏱️ مدة الاختبار: {target_quiz['timer_minutes']} دقيقة.")

        student_name = st.text_input("أدخل اسمك الكامل للبدء:")

        if student_name.strip():
            session_quiz_key = f"quiz_data_{target_quiz['id']}"
            if session_quiz_key not in st.session_state:
                raw_qs = target_quiz["questions"]
                prepared_qs = []
                for q in raw_qs:
                    opts = list(enumerate(q["options"]))
                    if target_quiz.get("shuffle_enabled"):
                        random.shuffle(opts)
                    prepared_qs.append({
                        "question": q["question"],
                        "options": opts,
                        "correct_idx": q["correct_index"],
                        "explanation": q.get("explanation", "")
                    })
                if target_quiz.get("shuffle_enabled"):
                    random.shuffle(prepared_qs)
                st.session_state[session_quiz_key] = prepared_qs

            active_quiz = st.session_state[session_quiz_key]
            result_state_key = f"result_{target_quiz['id']}_{student_name.strip()}"

            if result_state_key not in st.session_state:
                user_choices = {}
                with st.form("exam_form"):
                    for idx, q in enumerate(active_quiz):
                        st.markdown(f"**س{idx+1}: {q['question']}**")
                        opts_text = [o[1] for o in q["options"]]
                        user_choices[idx] = st.radio(
                            "اختر الإجابة:",
                            options=list(range(len(opts_text))),
                            format_func=lambda x, texts=opts_text: texts[x],
                            key=f"field_{target_quiz['id']}_{idx}",
                            index=None
                        )
                        st.write("")

                    finish_btn = st.form_submit_button("📩 إنهاء وتسليم الإجابات", type="primary")

                if finish_btn:
                    if any(c is None for c in user_choices.values()):
                        st.error("يرجى الإجابة عن جميع الأسئلة قبل تسليم الاختبار.")
                    else:
                        score = 0
                        total = len(active_quiz)
                        report_details = []

                        for idx, q in enumerate(active_quiz):
                            selected_pos = user_choices[idx]
                            orig_idx = q["options"][selected_pos][0]
                            selected_str = q["options"][selected_pos][1]

                            correct_str = next(opt[1] for opt in q["options"] if opt[0] == q["correct_idx"])
                            is_correct = (orig_idx == q["correct_idx"])
                            if is_correct:
                                score += 1

                            report_details.append({
                                "question": q["question"],
                                "chosen": selected_str,
                                "correct": correct_str,
                                "is_correct": is_correct,
                                "explanation": q["explanation"]
                            })

                        # الحفظ في Supabase
                        supabase.table("submissions").insert({
                            "quiz_id": target_quiz["id"],
                            "subject": target_quiz["subject"],
                            "student_name": student_name.strip(),
                            "score": score,
                            "total": total,
                            "answers": report_details
                        }).execute()

                        st.session_state[result_state_key] = {
                            "score": score,
                            "total": total,
                            "details": report_details
                        }
                        st.rerun()

            if result_state_key in st.session_state:
                res_data = st.session_state[result_state_key]
                st.balloons()
                st.success(f"أحسنت يا {student_name}! نتيجتك هي: {res_data['score']} من {res_data['total']}")

                st.subheader("🔍 مراجعة الإجابات والتفسيرات:")
                for idx, item in enumerate(res_data["details"]):
                    with st.container():
                        if item["is_correct"]:
                            st.markdown(f"✅ **س{idx+1}: {item['question']}**")
                            st.write(f"- إجابتك: {item['chosen']}")
                        else:
                            st.markdown(f"❌ **س{idx+1}: {item['question']}**")
                            st.write(f"- إجابتك: {item['chosen']}")
                            st.write(f"- الإجابة الصحيحة: {item['correct']}")

                        st.caption(f"💡 السبب: {item['explanation']}")

                        if not item["is_correct"]:
                            tutor_key = f"tutor_ans_{target_quiz['id']}_{idx}"
                            if st.button(f"🤖 اطلب من المعلم الذكي شرح هذا السؤال", key=f"tutor_btn_{target_quiz['id']}_{idx}"):
                                with st.spinner("المعلم الذكي يكتب لك الشرح الآن..."):
                                    explanation_text = ask_ai_tutor(
                                        item["question"], item["chosen"], item["correct"], item["explanation"]
                                    )
                                    st.session_state[tutor_key] = explanation_text

                            if tutor_key in st.session_state:
                                st.info(st.session_state[tutor_key])

                        st.write("---")
