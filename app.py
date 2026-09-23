import streamlit as st
import pypdf
import json
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
    "أ. رجب": {"password": "islamic123", "subject": "التربية الإسلامية"}
}

st.set_page_config(page_title="منصة منارة التعليمية", layout="wide")
st.title("🎓 نظام الاختبارات الذكي (منارة)")

role = st.sidebar.radio("اختر الدور:", ["👨‍🏫 الأستاذ", "👨‍🎓 الطالب"])

if 'logged_teacher' not in st.session_state:
    st.session_state['logged_teacher'] = None

# دالة مساعدة لفك وإصلاح بيانات الأسئلة بجميع أشكالها
def parse_questions_data(raw_data):
    if not raw_data:
        return []
    if isinstance(raw_data, str):
        try:
            parsed = json.loads(raw_data)
            return parse_questions_data(parsed)
        except Exception:
            return []
    elif isinstance(raw_data, list):
        if len(raw_data) > 0 and isinstance(raw_data[0], str):
            try:
                return [json.loads(item) if isinstance(item, str) else item for item in raw_data]
            except Exception:
                pass
        return raw_data
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
            
        tab1, tab2 = st.tabs([f"أنشئ اختبار لمادة ({current_subject})", "نتائج الطلاب"])
        
        with tab1:
            uploaded_file = st.file_uploader("ارفع ملف الدرس (PDF)", type=["pdf"])
            
            if uploaded_file and st.button("توليد الاختبار"):
                with st.spinner(f"جاري توليد 7 أسئلة لمادة {current_subject}..."):
                    try:
                        pdf_reader = pypdf.PdfReader(uploaded_file)
                        raw_text = ""
                        for page in pdf_reader.pages:
                            raw_text += (page.extract_text() or "") + "\n"
                        
                        lines = raw_text.split('\n')
                        cleaned_lines = []
                        ignored_phrases = ["الإجابة أسفل السؤال", "المدرس", "The answer is given"]
                        
                        for line in lines:
                            if not any(phrase in line for phrase in ignored_phrases):
                                cleaned_lines.append(line)
                        
                        clean_text = "\n".join(cleaned_lines)
                        short_text = clean_text[:5000]
                        
                        prompt = f"""
أنت معلم متخصص في مادة ({current_subject}). أمامك نص دراسي مصفّى. 
اصنع منه 7 أسئلة اختيار من متعدد دقيقة تعتمد على النص المرفق.

يجب أن ترجع النتيجة كـ JSON صريح فقط بدون أي مقدمات أو كلام خارجي.
التنسيق المطلوب تماماً:
[
  {{
    "id": 1,
    "question": "نص السؤال الأول",
    "options": ["أ) الخيار الأول", "ب) الخيار الثاني", "ج) الخيار الثالث", "د) الخيار الرابع"],
    "correct": "أ"
  }}
]

نص الدرس:
{short_text}
"""

                        response = groq_client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "أنت مساعد تعليمي يخرج البيانات بصيغة JSON حصرية."},
                                {"role": "user", "content": prompt}
                            ],
                            model="qwen/qwen3.8-27b",
                            temperature=0.1
                        )
                        
                        raw_response = response.choices[0].message.content.strip()
                        
                        backticks = chr(96) * 3
                        if backticks in raw_response:
                            parts = raw_response.split(backticks)
                            if len(parts) > 1:
                                raw_response = parts[1]
                                if raw_response.startswith("json"):
                                    raw_response = raw_response[4:]
                        
                        quiz_json = json.loads(raw_response.strip())
                        
                        # حفظ الاختبار في قاعدة البيانات
                        supabase.table("quizzes").upsert({
                            "subject": current_subject,
                            "questions": quiz_json
                        }, on_conflict="subject").execute()
                        
                        # حفظ في الجلسة للحصول على Preview فوراً
                        st.session_state[f"preview_{current_subject}"] = quiz_json
                        st.success(f"تم حفظ ونشر اختبار مادة {current_subject} (7 أسئلة) بنجاح!")
                        
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء معالجة الاختبار: {e}")

            # قراءة وعرض المعاينة (Preview) فوراً للأستاذ
            quiz_to_preview = st.session_state.get(f"preview_{current_subject}", None)
            
            if not quiz_to_preview:
                try:
                    res = supabase.table("quizzes").select("questions").eq("subject", current_subject).execute()
                    if res.data:
                        quiz_to_preview = parse_questions_data(res.data[0]['questions'])
                except Exception:
                    pass
            
            if quiz_to_preview:
                st.write("---")
                st.subheader(f"📋 معاينة (Preview) اختبار مادة ({current_subject}):")
                for q in quiz_to_preview:
                    if isinstance(q, dict):
                        st.markdown(f"**س{q.get('id', '')}: {q.get('question', '')}**")
                        for opt in q.get('options', []):
                            st.write(f"- {opt}")
                        st.markdown(f"✅ **الإجابة الصحيحة:** ({q.get('correct', '')})")
                        st.write("---")

        with tab2:
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
                    q_correct = q.get('correct', '')
                    
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
