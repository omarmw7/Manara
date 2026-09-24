import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import fitz  # PyMuPDF
import base64
import json
import random
import string
import pandas as pd
import re

# ========================================================
# 🔑 إعدادات الربط والمفاتيح المعتمدة
# ========================================================
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "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")
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

# تهيئة العملاء
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=120.0
)

# --- ضبط الصفحة وتنسيق الثيم الداكن والفخم ---
st.set_page_config(
    page_title="منصة منارة التعليمية الذكية",
    page_icon="🎓",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl;
        text-align: right;
    }

    h1 {
        font-weight: 900 !important;
        color: #60A5FA !important;
        margin-bottom: 20px !important;
        text-align: right !important;
    }

    p, span, label, h2, h3, h4, div[data-testid="stMarkdownContainer"] p { 
        direction: rtl !important; 
        text-align: right !important; 
        unicode-bidi: isolate !important;
        color: #F1F5F9 !important;
    }

    .quiz-card {
        background: #1E293B !important;
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 20px;
        border: 1px solid #334155;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4);
    }

    .q-badge {
        display: inline-block;
        background: #1E3A8A !important;
        color: #93C5FD !important;
        font-weight: 800;
        font-size: 0.85rem;
        padding: 4px 14px;
        border-radius: 20px;
        margin-bottom: 10px;
        border: 1px solid #3B82F6;
    }

    div[data-testid="stRadio"] > div {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    div[data-testid="stRadio"] label {
        background: #1E293B !important;
        border: 1.5px solid #334155 !important;
        padding: 12px 18px !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        color: #F8FAFC !important;
    }
    div[data-testid="stRadio"] label:hover {
        border-color: #3B82F6 !important;
        background: #0F172A !important;
    }
    div[data-testid="stRadio"] label p {
        color: #F8FAFC !important;
    }

    .correct-box {
        background: rgba(16, 185, 129, 0.12) !important;
        border: 1.5px solid #10B981 !important;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .wrong-box {
        background: rgba(239, 68, 68, 0.12) !important;
        border: 1.5px solid #EF4444 !important;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }

    div[data-testid="stExpander"] { 
        direction: rtl; 
        text-align: right; 
        border-color: #334155 !important;
    }

    .stButton > button {
        border-radius: 12px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
    }
</style>
""", unsafe_allow_html=True)

# بيانات المعلمين
TEACHERS_DB = {
    "أ. عمر": {"password": "bio123", "subject": "الأحياء"},
    "أ. سيد": {"password": "math123", "subject": "الرياضيات"},
    "أ. رجب": {"password": "islamic123", "subject": "التربية الإسلامية"},
    "أ. محمد": {"password": "chm123", "subject": "الكيمياء"}
    "أ.أحمد": {"password": "Eng123", "subject": "English Language"}
}

def generate_quiz_code(subject):
    code_chars = ''.join(random.choices(string.digits, k=4))
    prefix = subject[:3].strip()
    return f"{prefix}-{code_chars}"

# ========================================================
# 👁️ تحويل صفحات الـ PDF إلى صور عالية الدقة لكامل الدرس
# ========================================================
def convert_pdf_to_real_images(pdf_bytes, max_pages=6):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_payload = []
    
    total_pages = min(len(doc), max_pages)
    for page_num in range(total_pages):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=110)
        img_bytes = pix.tobytes("jpeg", jpg_quality=80)
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        images_payload.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64_img}"
            }
        })
        
    return images_payload, total_pages

# ========================================================
# 🧹 تنظيف واستخراج كائن الـ JSON بأمان تام
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
        fixes = ["}", "]}", "]}}", '"}]}']
        for fix in fixes:
            try:
                return json.loads(candidate + fix)
            except Exception:
                pass
        raise ValueError(f"تعذر استخراج كائن JSON صالح من الرد: {clean_text[:120]}")

# ========================================================
# 🚀 دالة توليد الاختبار (عربية فصحى مع نظام التبديل الذكي)
# ========================================================
def generate_quiz_from_pdf(pdf_bytes, subject, title, num_q, diff, allow_tf, make_summary):
    images_content, total_pages = convert_pdf_to_real_images(pdf_bytes, max_pages=6)
    if not images_content:
        raise ValueError("ملف الـ PDF فارغ.")

    types_desc = "جميع الأسئلة اختيار من متعدد بـ 4 خيارات."
    if allow_tf:
        types_desc += " مع إمكانية تضمين أسئلة صح أو خطأ بخيارين: 1) صح، 2) خطأ."

    prompt_text = f"""
أنت موجه تربوي وخبير امتحانات متخصص في مادة ({subject}).
أمامك صور صفحات الدرس المرفقة لدرس: ({title}) وعددها ({total_pages}) صفحة.

⚠️ قواعد اللغة والتنسيق الصارمة جداً:
1. لغة الاختبار هي اللغة العربية الفصحى حصراً بنسبة 100%.
2. يُمنع منعاً باتاً كتابة أي جمل أو عبارات أو كلمات باللغة الإنجليزية.
3. الاستثناء الوحيد المسموح به بالإنجليزية هو "الضرورة القصوى فقط" للرموز العلمية العالمية التي ليس لها بديل عربي نهائياً (مثل الرموز الوراثية: Bb, F1, P، أو اختصارات الأحماض: DNA, RNA, ATP). عدا ذلك، كل شيء يجب أن يكون عربياً خالصاً.

المطلوب:
1. استخرج بالضبط {num_q} أسئلة بمستوى صعوبة ({diff}) من صلب الصفحات المعروضة لقياس الفهم الحقيقي.
2. نمط الأسئلة: {types_desc}.
3. إذا كان make_summary = {make_summary}، اكتب ملخصاً شاملاً لأهم مفاهيم الدرس في حقل summary باللغة العربية الفصحى في 4 نقاط رئيسية.

أرجع كائن JSON حصرياً وصالحاً 100% بالهيكل التالي:
{{
  "summary": "نص الملخص باللغة العربية الفصحى...",
  "questions": [
    {{
      "id": 1,
      "question": "نص السؤال بالعربية الفصحى فقط؟",
      "options": ["الخيار الأول", "الخيار الثاني", "الخيار الثالث", "الخيار الرابع"],
      "correct_index": 0,
      "explanation": "شرح الإجابة باللغة العربية الفصحى"
    }}
  ]
}}
ملاحظة: correct_index هو رقم الفهرس للإجابة الصحيحة (0 للخيار الأول، 1 للثاني، 2 للثالث، 3 للرابع).
"""

    user_payload = [{"type": "text", "text": prompt_text}] + images_content

    candidate_models = [
        "openrouter/free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "google/gemma-4-26b-a4b-it:free"
    ]

    last_error = None
    for model_name in candidate_models:
        try:
            response = openrouter_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": user_payload}
                ],
                temperature=0.2,
            )

            if response.choices and response.choices[0].message.content:
                raw_text = response.choices[0].message.content
                return clean_and_parse_json(raw_text)
        except Exception as e:
            last_error = e
            if "429" in str(e) or "404" in str(e) or "rate-limited" in str(e):
                continue
            raise e

    raise last_error

# ========================================================
# ⚡ دوال التحليلات والمعلم الذكي (OpenRouter الموحد)
# ========================================================
def analyze_class_submissions(subject, submissions_data):
    prompt = f"""
أنت مستشار تربوي. إليك بيانات أداء الطلاب في اختبارات مادة ({subject}):
{json.dumps(submissions_data, ensure_ascii=False)}

المطلوب: قدم تقريراً تشخيصياً واضحاً باللغة العربية الفصحى للأستاذ عن نقاط الضعف وتوصيات الحصة القادمة.
"""
    completion = openrouter_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openrouter/free",
        temperature=0.2
    )
    return completion.choices[0].message.content

def ask_ai_tutor(question, student_ans, correct_ans, explanation):
    prompt = f"""
أنت معلم خصوصي ودود ومشجع وصبور. اشرح للطالب باللغة العربية الفصحى حصراً وبأسلوب مبسط ومشجع لماذا إجابته كانت غير دقيقة، وكيف يفهم الإجابة الصحيحة بسهولة ودون تعقيد:
- السؤال: {question}
- إجابة الطالب: {student_ans}
- الإجابة الصحيحة: {correct_ans}
- التفسير: {explanation}
"""
    completion = openrouter_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openrouter/free",
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

        # أربعة تبويبات متكاملة للمعلم
        tab1, tab_edit, tab2, tab3 = st.tabs([
            "✨ إنشاء اختبار ذكي من الـ PDF",
            "✏️ تحرير وإضافة أسئلة يدوياً",
            "📚 بنك الاختبارات المتاحة", 
            "📊 تحليلات وتقارير الأداء"
        ])

        # --- التبويب 1: إنشاء اختبار بالذكاء الاصطناعي ---
        with tab1:
            st.subheader("🤖 توليد اختبار دقيق بقراءة بصرية لكامل صفحات الدرس")
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
                with st.spinner("جاري قراءة صفحات الـ PDF وصياغة الأسئلة بدقة بالعربية الفصحى..."):
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

        # --- التبويب 2: تحرير وتعديل وإضافة أسئلة يدوياً ---
        with tab_edit:
            st.subheader(f"✏️ تحرير وإضافة أسئلة لاختبارات مادة ({subject})")
            quizzes_list_res = supabase.table("quizzes").select("id, lesson_title, quiz_code, questions").eq("subject", subject).order("created_at", desc=True).execute()

            if quizzes_list_res.data:
                quiz_map = {f"{q['lesson_title']} (كود: {q.get('quiz_code')})": q for q in quizzes_list_res.data}
                selected_quiz_label = st.selectbox("اختر الاختبار الذي تريد تعديله أو إضافة أسئلة له:", list(quiz_map.keys()))
                active_edit_quiz = quiz_map[selected_quiz_label]
                quiz_id = active_edit_quiz["id"]
                current_qs = list(active_edit_quiz.get("questions", []))

                st.markdown(f"### 📋 الأسئلة الحالية (العدد: {len(current_qs)} سؤال)")
                
                updated_qs = []

                for q_idx, q in enumerate(current_qs):
                    with st.expander(f"السؤال {q_idx + 1}: {q.get('question', '')[:60]}..."):
                        edit_q_text = st.text_input(f"نص السؤال {q_idx + 1}:", value=q.get("question", ""), key=f"eq_text_{quiz_id}_{q_idx}")
                        
                        opts = q.get("options", ["", "", "", ""])
                        while len(opts) < 4:
                            opts.append("")

                        c_opt1, c_opt2 = st.columns(2)
                        with c_opt1:
                            opt0 = st.text_input(f"الخيار 1:", value=opts[0], key=f"eopt0_{quiz_id}_{q_idx}")
                            opt1 = st.text_input(f"الخيار 2:", value=opts[1], key=f"eopt1_{quiz_id}_{q_idx}")
                        with c_opt2:
                            opt2 = st.text_input(f"الخيار 3:", value=opts[2], key=f"eopt2_{quiz_id}_{q_idx}")
                            opt3 = st.text_input(f"الخيار 4:", value=opts[3], key=f"eopt3_{quiz_id}_{q_idx}")

                        c_corr, c_del = st.columns([3, 1])
                        with c_corr:
                            curr_corr = int(q.get("correct_index", 0))
                            edit_corr = st.selectbox(
                                "الخيار الصحيح:",
                                [0, 1, 2, 3],
                                index=curr_corr if curr_corr in [0, 1, 2, 3] else 0,
                                format_func=lambda x: f"الخيار رقم {x + 1}",
                                key=f"ecorr_{quiz_id}_{q_idx}"
                            )
                        with c_del:
                            st.write("")
                            st.write("")
                            if st.button("🗑️ حذف هذا السؤال", key=f"del_single_q_{quiz_id}_{q_idx}"):
                                current_qs.pop(q_idx)
                                supabase.table("quizzes").update({"questions": current_qs}).eq("id", quiz_id).execute()
                                st.success("تم حذف السؤال بنجاح!")
                                st.rerun()

                        edit_exp = st.text_area("تفسير الإجابة الصحيحة:", value=q.get("explanation", ""), key=f"eexp_{quiz_id}_{q_idx}")

                        updated_qs.append({
                            "id": q_idx + 1,
                            "question": edit_q_text,
                            "options": [opt0, opt1, opt2, opt3],
                            "correct_index": edit_corr,
                            "explanation": edit_exp
                        })

                if st.button("💾 حفظ كافة التعديلات على الأسئلة", type="primary"):
                    supabase.table("quizzes").update({"questions": updated_qs}).eq("id", quiz_id).execute()
                    st.success("🎉 تم حفظ جميع التعديلات بنجاح!")
                    st.rerun()

                st.divider()

                # قسم إضافة سؤال جديد يدوياً
                st.markdown("### ➕ إضافة سؤال يدوي جديد إلى هذا الاختبار:")
                with st.form(f"manual_add_q_form_{quiz_id}"):
                    new_q_text = st.text_input("نص السؤال الجديد:")
                    n_col1, n_col2 = st.columns(2)
                    with n_col1:
                        new_o1 = st.text_input("الخيار 1:")
                        new_o2 = st.text_input("الخيار 2:")
                    with n_col2:
                        new_o3 = st.text_input("الخيار 3:")
                        new_o4 = st.text_input("الخيار 4:")

                    new_corr_idx = st.selectbox("رقم الخيار الصحيح:", [0, 1, 2, 3], format_func=lambda x: f"الخيار رقم {x + 1}")
                    new_explanation = st.text_area("تفسير الإجابة الصحيحة:")

                    add_submit = st.form_submit_button("➕ حفظ وإضافة السؤال إلى الاختبار", type="primary")

                    if add_submit:
                        if not new_q_text.strip() or not new_o1.strip() or not new_o2.strip():
                            st.error("يرجى كتابة نص السؤال مع خيارين على الأقل.")
                        else:
                            new_q_obj = {
                                "id": len(current_qs) + 1,
                                "question": new_q_text.strip(),
                                "options": [new_o1.strip(), new_o2.strip(), new_o3.strip(), new_o4.strip()],
                                "correct_index": new_corr_idx,
                                "explanation": new_explanation.strip()
                            }
                            current_qs.append(new_q_obj)
                            supabase.table("quizzes").update({"questions": current_qs}).eq("id", quiz_id).execute()
                            st.success("🎉 تمت إضافة السؤال الجديد بنجاح!")
                            st.rerun()
            else:
                st.info("لا توجد اختبارات منشأة لهذه المادة حتى الآن. أنشئ اختباراً أولاً لتتمكن من تحريره.")

        # --- التبويب 3: بنك الاختبارات المتاحة ---
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

                        if st.button("🗑️ حذف هذا الاختبار بالكامل", key=f"del_all_{qz['id']}"):
                            supabase.table("quizzes").delete().eq("id", qz['id']).execute()
                            st.rerun()
            else:
                st.info("لا توجد اختبارات منشورة حتى الآن.")

        # --- التبويب 4: النتائج والتحليلات ---
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
                    total_qs = len(active_quiz)
                    for idx, q in enumerate(active_quiz):
                        # عرض السؤال داخل بطاقة تفاعلية عصرية
                        st.markdown(f"""
                        <div class="quiz-card">
                            <span class="q-badge">السؤال {idx + 1} من {total_qs}</span>
                            <h3 style="margin-top: 4px; color: #F8FAFC !important; font-size: 1.15rem; line-height: 1.6;">{q['question']}</h3>
                        </div>
                        """, unsafe_allow_html=True)

                        opts_text = [o[1] for o in q["options"]]
                        user_choices[idx] = st.radio(
                            "اختر الإجابة المناسبة:",
                            options=list(range(len(opts_text))),
                            format_func=lambda x, texts=opts_text: texts[x],
                            key=f"field_{target_quiz['id']}_{idx}",
                            index=None,
                            label_visibility="collapsed"
                        )
                        st.write("")

                    finish_btn = st.form_submit_button("📩 إنهاء الاختبار واعتماد النتيجة", type="primary", use_container_width=True)

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

                score = res_data['score']
                total = res_data['total']
                pct = (score / total) * 100

                # تحديد الوسام واللون
                badge_title = "🏆 عبقري ومتميز!" if pct >= 85 else ("🌟 بطل، نتيجة رائعة!" if pct >= 65 else "💪 بداية موفقة، راجع أخطاءك لتتفوق!")
                badge_color = "#10B981" if pct >= 65 else "#F59E0B"

                # كرت دارك فخم ومتناسق مع الوضع الليلي بنصوص واضحة ومقروءة
                st.markdown(f"""
                <div style="background: #1E293B; border-radius: 20px; padding: 30px; text-align: center; border: 1.5px solid #334155; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 25px;">
                    <div style="font-size: 3rem; margin-bottom: 8px;">{badge_title.split()[0]}</div>
                    <h2 style="color: #F8FAFC !important; margin: 0; font-weight: 800; font-size: 1.8rem;">{badge_title}</h2>
                    <p style="color: #94A3B8 !important; font-size: 1.15rem; margin-top: 8px; margin-bottom: 18px;">
                        أحسنت يا <b style="color: #60A5FA !important;">{student_name}</b>، إليك تفاصيل نتيجتك:
                    </p>
                    <div style="display: inline-block; background: rgba(16, 185, 129, 0.15); color: #34D399; padding: 12px 32px; border-radius: 30px; font-weight: 900; font-size: 1.8rem; border: 1.5px solid #10B981;">
                        {score} من {total} ({pct:.0f}%)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### 🔍 مراجعة الأسئلة وتفسير الإجابات:")
                for idx, item in enumerate(res_data["details"]):
                    if item["is_correct"]:
                        st.markdown(f"""
                        <div class="correct-box">
                            <span style="color: #15803D; font-weight: 800; font-size: 1.05rem;">✅ السؤال {idx+1}: {item['question']}</span>
                            <div style="margin-top: 8px; color: #166534;"><b>إجابتك الصحيحة:</b> {item['chosen']}</div>
                            <div style="margin-top: 6px; font-size: 0.9rem; color: #15803D;">💡 <b>التفسير:</b> {item['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="wrong-box">
                            <span style="color: #B91C1C; font-weight: 800; font-size: 1.05rem;">❌ السؤال {idx+1}: {item['question']}</span>
                            <div style="margin-top: 8px; color: #991B1B;"><b>إجابتك:</b> {item['chosen']}</div>
                            <div style="margin-top: 4px; color: #15803D;"><b>الإجابة الصحيحة النموذجية:</b> {item['correct']}</div>
                            <div style="margin-top: 6px; font-size: 0.9rem; color: #B91C1C;">💡 <b>التفسير:</b> {item['explanation']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        # زر المعلم الذكي
                        tutor_key = f"tutor_ans_{target_quiz['id']}_{idx}"
                        if st.button(f"🤖 اطلب من المعلم الذكي توضيح هذا الخطأ", key=f"tutor_btn_{target_quiz['id']}_{idx}"):
                            with st.spinner("المعلم الذكي يجهز لك الشرح المبسط..."):
                                explanation_text = ask_ai_tutor(
                                    item["question"], item["chosen"], item["correct"], item["explanation"]
                                )
                                st.session_state[tutor_key] = explanation_text

                        if tutor_key in st.session_state:
                            st.info(f"👨‍🏫 **المعلم الذكي:**\n\n{st.session_state[tutor_key]}")

                    st.write("")
