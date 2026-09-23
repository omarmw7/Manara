import streamlit as st
import pypdf
import json
import re
from groq import Groq
from supabase import create_client, Client

# قراءة مفاتيح Supabase من Streamlit Secrets
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception as e:
    st.error("يرجى إعداد مفاتيح Supabase (Secrets) في لوحة تحكم Streamlit Cloud أولاً.")
    st.stop()

# مفتاح Groq
GROQ_API_KEY = "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"

# إنشاء عميل Supabase و Groq
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# حسابات الأساتذة والمواد
TEACHERS_DB = {
    "أ. عمر": {"password": "bio123", "subject": "الأحياء"},
    "أ. سيد": {"password": "math123", "subject": "الرياضيات"},
    "أ. رجب": {"password": "islamic123", "subject": "التربية الإسلامية"},
    "أ. محمد": {"password": "chm123", "subject": "الكيمياء"}
}

st.set_page_config(page_title="منصة منارة التعليمية", layout="wide")

# تنسيق CSS لضبط المحاذاة والعربي والإنجليزي
st.markdown("""
    <style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
    p, div, span, h1, h2, h3, h4, label {
        text-align: right !important;
        unicode-bidi: plaintext !important;
    }
    .stRadio label {
        direction: rtl !important;
        text-align: right !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎓 نظام الاختبارات الذكي (منارة)")

role = st.sidebar.radio("اختر الدور:", ["👨‍🏫 الأستاذ", "👨‍🎓 الطالب"])

if 'logged_teacher' not in st.session_state:
    st.session_state['logged_teacher'] = None

# دالة معالجة واستخراج الـ JSON بأمان كامل
def parse_questions_data(raw_data):
    if not raw_data:
        return []
    if isinstance(raw_data, str):
        try:
            parsed = json.loads(raw_data)
            return parse_questions_data(parsed)
        except Exception:
            clean_text = re.sub(r'```(?:json)?', '', raw_data, flags=re.IGNORECASE).strip()
            clean_text = clean_text.replace('```', '').strip()
            try:
                return json.loads(clean_text)
            except Exception:
                match = re.search(r'\[\s*\{.*\}\s*\]', raw_data, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except Exception:
                        pass
                return []
    elif isinstance(raw_data, list):
        clean_list = []
        for item in raw_data:
            if isinstance(item, str):
                try:
                    clean_list.append(json.loads(item))
                except Exception:
                    pass
            elif isinstance(item, dict):
                clean_list.append(item)
        return clean_list
    return []

# ---------------------------------------------------------
# بوابة الأستاذ
# ---------------------------------------------------------
if role == "👨‍🏫 الأستاذ":
    st.header("بوابة الأستاذ")
    
    if not st.session_state['logged_teacher']:
        st.subheader("🔒 تسجيل الدخول لأساتذة المواد")
        teacher_name = st.selectbox("اختر اسم الأستاذ:", list(TEACHERS_DB.keys()))
        password_input = st.text_input("أدخل كلمة المرور:", type="password")
        
        if st.button("تسجيل الدخول"):
            if password_input == TEACHERS_DB[teacher_name]["password"]:
                st.session_state['logged_teacher'] = teacher_name
                st.success(f"أهلاً بك {teacher_name}! تم تسجيل الدخول لـ ({TEACHERS_DB[teacher_name]['subject']})")
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة!")
    else:
        current_teacher = st.session_state['logged_teacher']
        current_subject = TEACHERS_DB[current_teacher]["subject"]
        
        st.sidebar.info(f"👨‍🏫 **المعلم الحالي:** {current_teacher}\n\n📚 **المادة:** {current_subject}")
        if st.sidebar.button("🔒 تسجيل الخروج"):
            st.session_state['logged_teacher'] = None
            st.rerun()
            
        tab1, tab2, tab3, tab4 = st.tabs([
            f"أنشئ اختبار بالذكاء الاصطناعي", 
            "إضافة أسئلة يدوياً / تحرير", 
            "سجل الأنشطة والاختبارات (History)", 
            "نتائج الطلاب"
        ])
        
        # ---------------------------------------------------------
        # التبويب 1: توليد بالذكاء الاصطناعي مع تحديد عدد الأسئلة
        # ---------------------------------------------------------
        with tab1:
            st.subheader(f"🤖 توليد اختبار لمادة ({current_subject})")
            uploaded_file = st.file_uploader("ارفع ملف الدرس (PDF)", type=["pdf"])
            num_questions = st.number_input("اختر عدد الأسئلة المطلوبة:", min_value=1, max_value=20, value=5)
            
            if uploaded_file and st.button("توليد الاختبار"):
                with st.spinner(f"جاري توليد {num_questions} أسئلة لمادة {current_subject}..."):
                    try:
                        pdf_reader = pypdf.PdfReader(uploaded_file)
                        raw_text = ""
                        for page in pdf_reader.pages:
                            raw_text += (page.extract_text() or "") + "\n"
                        
                        lines = raw_text.split('\n')
                        cleaned_lines = [l for l in lines if not any(p in l for p in ["الإجابة أسفل السؤال", "المدرس", "The answer is given"])]
                        clean_text = "\n".join(cleaned_lines)[:5000]
                        
                        prompt = f"""
أنت معلم متخصص في مادة ({current_subject}). أمامك نص دراسي مصفّى. 
اصنع منه بالضبط {num_questions} أسئلة اختيار من متعدد دقيقة.

تنسيق الخيارات المعتمد: "1) الخيار", "2) الخيار", "3) الخيار", "4) الخيار".
أرجع فقط قائمة JSON حصرية بنفس الشكل التالي تماماً:
[
  {{
    "id": 1,
    "question": "نص السؤال الأول",
    "options": ["1) الخيار الأول", "2) الخيار الثاني", "3) الخيار الثالث", "4) الخيار الرابع"],
    "correct": "1"
  }}
]

نص الدرس:
{clean_text}
"""
                        response = groq_client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "أنت مساعد تعليمي تخرج النتائج بصيغة JSON فقط."},
                                {"role": "user", "content": prompt}
                            ],
                            model="qwen/qwen3.8-27b",
                            temperature=0.1
                        )
                        
                        raw_response = response.choices[0].message.content.strip()
                        quiz_json = parse_questions_data(raw_response)

                        if quiz_json:
                            supabase.table("quizzes").upsert({
                                "subject": current_subject,
                                "questions": quiz_json
                            }, on_conflict="subject").execute()
                            
                            st.session_state[f"editing_quiz_{current_subject}"] = quiz_json
                            st.success(f"تم حفظ ونشر اختبار مادة {current_subject} ({len(quiz_json)} أسئلة) بنجاح!")
                        else:
                            st.error("فشل في صياغة الأسئلة، يرجى المحاولة مرة أخرى.")
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء معالجة الاختبار: {e}")

        # ---------------------------------------------------------
        # التبويب 2: إضافة أسئلة يدوياً وتحرير الأسئلة الحالية
        # ---------------------------------------------------------
        with tab2:
            st.subheader(f"🛠️ تحرير وإضافة الأسئلة لمادة ({current_subject})")
            
            # جلب الأسئلة الحالية
            if f"editing_quiz_{current_subject}" not in st.session_state:
                try:
                    res = supabase.table("quizzes").select("questions").eq("subject", current_subject).execute()
                    if res.data and len(res.data) > 0:
                        st.session_state[f"editing_quiz_{current_subject}"] = parse_questions_data(res.data[0]['questions'])
                    else:
                        st.session_state[f"editing_quiz_{current_subject}"] = []
                except Exception:
                    st.session_state[f"editing_quiz_{current_subject}"] = []

            current_questions = st.session_state[f"editing_quiz_{current_subject}"]

            # عرض وتحرير الأسئلة الحالية
            if current_questions:
                st.markdown("### ✏️ الأسئلة الحالية (يمكنك تعديلها وتحديثها):")
                updated_questions = []
                for idx, q in enumerate(current_questions):
                    with st.expander(f"السؤال {idx + 1}: {q.get('question', '')}"):
                        q_text = st.text_input(f"نص السؤال {idx + 1}:", value=q.get('question', ''), key=f"q_text_{idx}")
                        opts = q.get('options', ["1) ", "2) ", "3) ", "4) "])
                        
                        opt1 = st.text_input(f"الخيار 1:", value=opts[0] if len(opts)>0 else "1) ", key=f"opt1_{idx}")
                        opt2 = st.text_input(f"الخيار 2:", value=opts[1] if len(opts)>1 else "2) ", key=f"opt2_{idx}")
                        opt3 = st.text_input(f"الخيار 3:", value=opts[2] if len(opts)>2 else "3) ", key=f"opt3_{idx}")
                        opt4 = st.text_input(f"الخيار 4:", value=opts[3] if len(opts)>3 else "4) ", key=f"opt4_{idx}")
                        
                        raw_correct = str(q.get('correct', '1')).strip()
                        default_idx = ["1", "2", "3", "4"].index(raw_correct) if raw_correct in ["1", "2", "3", "4"] else 0
                        
                        correct_ans = st.selectbox(
                            f"الإجابة الصحيحة للسؤال {idx + 1}:", 
                            ["1", "2", "3", "4"], 
                            index=default_idx,
                            key=f"corr_{idx}"
                        )
                        
                        updated_questions.append({
                            "id": idx + 1,
                            "question": q_text,
                            "options": [opt1, opt2, opt3, opt4],
                            "correct": correct_ans
                        })
                
                if st.button("💾 حفظ والتحديث النهائي للأسئلة"):
                    st.session_state[f"editing_quiz_{current_subject}"] = updated_questions
                    supabase.table("quizzes").upsert({
                        "subject": current_subject,
                        "questions": updated_questions
                    }, on_conflict="subject").execute()
                    st.success("تم تحديث الاختبار بنجاح!")
                    st.rerun()

            st.write("---")
            st.markdown("### ➕ إضافة سؤال يدوي جديد:")
            with st.form("add_manual_question"):
                new_q_text = st.text_input("السؤال الجديد:")
                new_opt1 = st.text_input("الخيار 1:", value="1) ")
                new_opt2 = st.text_input("الخيار 2:", value="2) ")
                new_opt3 = st.text_input("الخيار 3:", value="3) ")
                new_opt4 = st.text_input("الخيار 4:", value="4) ")
                new_correct = st.selectbox("رقم الإجابة الصحيحة:", ["1", "2", "3", "4"])
                
                submit_new = st.form_submit_button("إضافة السؤال للاختبار")
                
                if submit_new and new_q_text:
                    new_q_obj = {
                        "id": len(current_questions) + 1,
                        "question": new_q_text,
                        "options": [new_opt1, new_opt2, new_opt3, new_opt4],
                        "correct": new_correct
                    }
                    current_questions.append(new_q_obj)
                    st.session_state[f"editing_quiz_{current_subject}"] = current_questions
                    
                    supabase.table("quizzes").upsert({
                        "subject": current_subject,
                        "questions": current_questions
                    }, on_conflict="subject").execute()
                    st.success("تم إضافة السؤال الجديد وحفظ الاختبار بنجاح!")
                    st.rerun()

        # ---------------------------------------------------------
        # التبويب 3: السجل والتاريخ (History)
        # ---------------------------------------------------------
        with tab3:
            st.subheader(f"📜 سجل الاختبارات المتاحة لمادة ({current_subject})")
            try:
                res_hist = supabase.table("quizzes").select("*").eq("subject", current_subject).execute()
                if res_hist.data:
                    for item in res_hist.data:
                        st.write(f"📌 **المادة:** {item['subject']}")
                        questions_list = parse_questions_data(item['questions'])
                        st.write(f"🔢 **عدد الأسئلة:** {len(questions_list)}")
                        with st.expander("عرض تفاصيل الاختبار الحالي"):
                            for q in questions_list:
                                if isinstance(q, dict):
                                    st.markdown(f"**س{q.get('id', '')}: {q.get('question', '')}**")
                                    for opt in q.get('options', []):
                                        st.write(f"- {opt}")
                                    st.write(f"✅ الإجابة الصحيحة: ({q.get('correct', '')})")
                                    st.write("---")
                else:
                    st.info("لا يوجد سجل اختبارات سابق لهذه المادة.")
            except Exception as e:
                st.error(f"خطأ في قراءة السجل: {e}")

        # ---------------------------------------------------------
        # التبويب 4: نتائج الطلاب
        # ---------------------------------------------------------
        with tab4:
            st.subheader(f"📊 نتائج إجابات الطلاب لمادة ({current_subject})")
            try:
                res_sub = supabase.table("submissions").select("*").eq("subject", current_subject).order("created_at", desc=True).execute()
                if res_sub.data:
                    for sub in res_sub.data:
                        st.write(f"👤 **اسم الطالب:** {sub['student_name']}")
                        st.write(f"💯 **الدرجة:** {sub['score']} من {sub['total']}")
                        st.write("**تفاصيل إجابات الطالب:**")
                        for detail in sub.get('details', []):
                            st.write(f"- {detail.get('question', '')} | إجابة الطالب: ({detail.get('student_ans', '')}) | الإجابة الصحيحة: ({detail.get('correct_ans', '')})")
                        st.write("---")
                else:
                    st.info(f"لا توجد إجابات مقدمة لمادة {current_subject} حتى الآن.")
            except Exception:
                st.info(f"لا توجد إجابات مقدمة لمادة {current_subject} حتى الآن.")

# ---------------------------------------------------------
# بوابة الطالب
# ---------------------------------------------------------
elif role == "👨‍🎓 الطالب":
    st.header("بوابة الطالب")
    
    try:
        res_quizzes = supabase.table("quizzes").select("subject, questions").execute()
    except Exception:
        res_quizzes = None
        
    if res_quizzes and res_quizzes.data:
        available_subjects = [item['subject'] for item in res_quizzes.data]
        selected_subject = st.selectbox("📚 اختر المادة التي تريد تقديم اختبارها:", available_subjects)
        
        student_name = st.text_input("اسم الطالب الكامل:")
        
        st.write("---")
        st.subheader(f"📝 اختبار مادة: {selected_subject}")
        
        raw_selected = next(item['questions'] for item in res_quizzes.data if item['subject'] == selected_subject)
        selected_quiz_data = parse_questions_data(raw_selected)
        
        user_answers = {}
        all_answered = True
        
        if selected_quiz_data and len(selected_quiz_data) > 0:
            for q in selected_quiz_data:
                if isinstance(q, dict):
                    q_id = q.get('id', 1)
                    q_text = q.get('question', '')
                    q_options = q.get('options', [])
                    q_correct = str(q.get('correct', ''))
                    
                    st.markdown(f"#### س{q_id}: {q_text}")
                    
                    chosen = st.radio(
                        "اختر الإجابة:", 
                        q_options, 
                        index=None,
                        key=f"q_{selected_subject}_{q_id}"
                    )
                    
                    if chosen is None:
                        all_answered = False
                        chosen_char = None
                    else:
                        chosen_char = chosen.split(")")[0].strip() if ")" in chosen else chosen[0]
                    
                    user_answers[q_id] = {
                        "chosen_char": chosen_char,
                        "question": q_text,
                        "correct_char": q_correct
                    }
                    st.write("")
            
            if st.button("تسليم الحل"):
                if not student_name:
                    st.warning("يرجى كتابة اسمك الكامل قبل إرسال الحل.")
                elif not all_answered:
                    st.warning("يرجى الإجابة عن جميع الأسئلة قبل تسليم الحل.")
                else:
                    score = 0
                    total = len(selected_quiz_data)
                    details = []
                    
                    for q_id, ans in user_answers.items():
                        is_correct = (ans['chosen_char'] == ans['correct_char'])
                        if is_correct:
                            score += 1
                        
                        details.append({
                            "question": ans['question'],
                            "student_ans": ans['chosen_char'],
                            "correct_ans": ans['correct_char']
                        })
                    
                    supabase.table("submissions").insert({
                        "student_name": student_name,
                        "subject": selected_subject,
                        "score": score,
                        "total": total,
                        "details": details
                    }).execute()
                    
                    st.balloons()
                    st.success(f"تم تسليم إجابة اختبار {selected_subject} بنجاح يا {student_name}! درجتك هي: {score} من {total}")
        else:
            st.warning("عذراً، لم يتم إنشاء أسئلة جديدة بعد لهذه المادة. يرجى الدخول كمعلم وتوليد اختبار جديد.")
    else:
        st.info("لا توجد أي اختبارات متاحة حالياً لأي مادة. يرجى الدخول من حساب الأستاذ وتوليد اختبار أولاً.")
