import streamlit as st
from openai import OpenAI
from groq import Groq
from supabase import create_client, Client
import fitz  # PyMuPDF لتحويل الصفحات لصور حقيقية
import base64
import json
import random
import string
import pandas as pd
import re

# ========================================================
# 🔑 إعدادات المفاتيح الشغالة والمفعلة بحسابك
# ========================================================
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "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")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

# تهيئة العملاء
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# --- ضبط الصفحة وتنسيق الاتجاه (RTL) ---
st.set_page_config(
    page_title="منصة منارة التعليمية الذكية",
    page_icon="🎓",
    layout="wide"
)

st.markdown("""
<style>
    .stApp { 
        direction: rtl; 
        text-align: right; 
    }
    /* جعل النصوص العربية تدعم الكلمات والرموز الإنجليزية بانسيابية دون انقلاب */
    p, span, label, h1, h2, h3, h4, div[data-testid="stMarkdownContainer"] p { 
        direction: rtl !important; 
        text-align: right !important; 
        unicode-bidi: isolate !important;
    }
    /* تنسيق خيارات الراديو لتكون مرتبة */
    .stRadio label { 
        direction: rtl !important; 
        text-align: right !important; 
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    div[data-testid="stExpander"] { 
        direction: rtl; 
        text-align: right; 
    }
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
# 👁️ تحويل صفحات الـ PDF إلى صور JPEG حقيقية
# ========================================================
def convert_pdf_to_real_images(pdf_bytes, max_pages=3):
    """تحويل صفحات الـ PDF إلى صور حقيقية يقبلها الذكاء الاصطناعي كـ Vision"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_payload = []
    
    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=100) # دقة واضحة وخفيفة
        img_bytes = pix.tobytes("jpeg", jpg_quality=75)
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        images_payload.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64_img}"
            }
        })
        
    return images_payload

# ========================================================
# 🧹 تنظيف واستخراج كائن الـ JSON بأمان
# ========================================================
def clean_and_parse_json(text):
    if not text:
        raise ValueError("وصل رد فارغ من الموديل.")
    
    clean_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    clean_text = clean_text.strip()
    clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\s*```$", "", clean_text)
    clean_text = clean_text.strip()

    match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
    candidate = match.group(1) if match else clean_text
    
    try:
        return json.loads(candidate)
    except Exception:
        # إكمال الأقواس بأمان بدون أي أخطاء في السنتاكس
        fixes = ["}", "]}", "]}}", '"}]}']
        for fix in fixes:
            try:
                return json.loads(candidate + fix)
            except Exception:
                pass
        raise ValueError(f"تعذر استخراج كائن JSON صالح من الرد: {clean_text[:120]}")

def generate_quiz_from_pdf(pdf_bytes, subject, title, num_q, diff, allow_tf, make_summary):
    images_content = convert_pdf_to_real_images(pdf_bytes, max_pages=3)
    if not images_content:
        raise ValueError("ملف الـ PDF فارغ.")

    types_desc = "جميع الأسئلة اختيار من متعدد بـ 4 خيارات."
    if allow_tf:
        types_desc += " مع إمكانية تضمين أسئلة صح أو خطأ بخيارين: 1) صح، 2) خطأ."

    # توجيه حاسم: اللغة عربية فصحى نقية، والإنجليزي للرموز المستحيلة فقط
    prompt_text = f"""
أنت موجه تربوي وخبير امتحانات متخصص في مادة ({subject}).
اقرأ صور صفحات الدرس المرفقة لدرس: ({title}).

⚠️ قواعد اللغة والتنسيق الصارمة جداً:
1. لغة الاختبار هي اللغة العربية الفصحى حصراً بنسبة 100%.
2. يُمنع منعاً باتاً كتابة أي جمل أو عبارات أو كلمات باللغة الإنجليزية.
3. الاستثناء الوحيد المسموح به بالإنجليزية هو "الضرورة القصوى فقط" للرموز العلمية العالمية التي لا يوجد لها مقابل عربي نهائياً (مثل الرموز الوراثية: Bb, F1, P، أو اختصارات الأحماض: DNA, RNA, ATP). عدا ذلك، كل شيء يجب أن يكون عربياً خالصاً.

المطلوب:
1. استخرج بالضبط {num_q} أسئلة بمستوى صعوبة ({diff}) من صلب الصفحات لقياس الفهم الحقيقي.
2. نمط الأسئلة: {types_desc}.
3. إذا كان make_summary = {make_summary}، اكتب ملخصاً في حقل summary باللغة العربية الفصحى النقية في 4 نقاط رئيسية.

أرجع كائن JSON حصرياً بالهيكل التالي:
{{
  "summary": "نص الملخص باللغة العربية الفصحى...",
  "questions": [
    {{
      "id": 1,
      "question": "نص السؤال بالعربية الفصحى فقط؟",
      "options": ["الخيار الأول", "الخيار الثاني", "الخيار الثالث", "الخيار الرابع"],
      "correct_index": 0,
      "explanation": "شرح الإجابة باللغة العربية الفصحى النقية"
    }}
  ]
}}
ملاحظة: correct_index هو رقم الفهرس للإجابة الصحيحة (0 للخيار الأول، 1 للثاني، 2 للثالث، 3 للرابع).
"""

    user_payload = [{"type": "text", "text": prompt_text}] + images_content

    response = openrouter_client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {"role": "user", "content": user_payload}
        ],
        temperature=0.2,
        max_tokens=4000
    )

    if not response.choices or not response.choices[0].message.content:
        raise ValueError("لم يرجع السيرفر إجابة، يرجى المحاولة مرة أخرى.")

    raw_text = response.choices[0].message.content
    return clean_and_parse_json(raw_text)
# ========================================================
# ⚡ دوال الطلاب والتحليلات عبر Groq
# ========================================================
def analyze_class_submissions(subject, submissions_data):
    prompt = f"""
أنت مستشار تربوي. إليك بيانات أداء الطلاب في اختبارات مادة ({subject}):
{json.dumps(submissions_data, ensure_ascii=False)}

المطلوب: قدم تقريراً تشخيصياً واضحاً باللغة العربية الفصحى للأستاذ عن نقاط الضعف وتوصيات الحصة القادمة.
"""
    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",  # تحديث اسم النموذج لحل خطأ 404
        temperature=0.2
    )
    return completion.choices[0].message.content

def ask_ai_tutor(question, student_ans, correct_ans, explanation):
    prompt = f"""
أنت معلم خصوصي ودود وصبور. اشرح للطالب باللغة العربية الفصحى حصراً سبب خطئه وكيف يتذكر الإجابة الصحيحة:
- السؤال: {question}
- إجابة الطالب: {student_ans}
- الإجابة الصحيحة: {correct_ans}
- التفسير: {explanation}
"""
    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",  # تحديث اسم النموذج لحل خطأ 404
        temperature=0.3
    )
    return completion.choices[0].message.content
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
            st.subheader("🤖 توليد اختبار دقيق برؤية بصرية حقيقية للـ PDF")
            c_title, c_num, c_diff = st.columns([2, 1, 1])
            with c_title:
                quiz_title = st.text_input("عنوان الدرس / الاختبار:", placeholder="مثال: علم الوراثة المندلية")
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
                with st.spinner("جاري قراءة صفحات الـ PDF بصرياً كصور حقيقية وتوليد الأسئلة..."):
                    try:
                        ai_data = generate_quiz_from_pdf(
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

                        st.success(f"🎉 تم إنشاء ونشر الاختبار بنجاح! كود الاختبار للطلاب: **{quiz_code}**")
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
                    with st.spinner("جاري قراءة إجابات الطلاب واستخراج الملاحظات..."):
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

                        st.caption(f"💡 التفسير: {item['explanation']}")

                        # المعلم الذكي السريع عبر Groq
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
