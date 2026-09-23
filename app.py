import streamlit as st
import pypdf
import json
from groq import Groq
from supabase import create_client, Client

# 1. مفاتيح الربط مباشرة (لضمان عمل التطبيق بدون مشاكل Secrets)
SUPABASE_URL = "https://yaedsonblycyqchkrgdk.supabase.co"
SUPABASE_KEY = "sb_publishable_Q0iq5flGZxer4V6lrdar-w_5ya0PxwC"
GROQ_API_KEY = "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"

# إنشاء عميل Supabase و Groq
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# 2. حسابات الأساتذة والمواد المسندة
TEACHERS_DB = {
    "أ. عماد": {"password": "bio123", "subject": "الأحياء"},
    "أ. أحمد": {"password": "math123", "subject": "الرياضيات"},
    "أ. عمر": {"password": "physics123", "subject": "الفيزياء"}
}

st.set_page_config(page_title="منصة منارة التعليمية", layout="wide")
st.title("🎓 نظام الاختبارات الذكي (منارة)")

role = st.sidebar.radio("اختر الدور:", ["👨‍🏫 الأستاذ", "👨‍🎓 الطالب"])

if 'logged_teacher' not in st.session_state:
    st.session_state['logged_teacher'] = None

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
                        ignored_phrases = ["Imad Odeh", "عماد عودة", "الإجابة أسفل السؤال", "المدرس", "The answer is given"]
                        
                        for line in lines:
                            if not any(phrase in line for phrase in ignored_phrases):
                                cleaned_lines.append(line)
                        
                        clean_text = "\n".join(cleaned_lines)
                        short_text = clean_text[:5000]
                        
                        prompt = f"""
أنت معلم متخصص في مادة ({current_subject}). أمامك نص دراسي مصفّى. 
اصنع منه 7 أسئلة اختيار من متعدد دقيقة تعتمد على النص المرفق.

يجب أن ترجع النتيجة كـ JSON صريح فقط بدون أي مقدمات.
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
                        
                        # حفظ الاختبار في قاعدة بيانات Supabase
                        supabase.table("quizzes").upsert({
                            "subject": current_subject,
                            "questions": quiz_json
                        }).execute()
                        
                        st.success(f"تم حفظ ونشر اختبار مادة {current_subject} (7 أسئلة) في قاعدة البيانات بنجاح!")
                        
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء معالجة الاختبار: {e}")

            # قراءة ومعاينة الاختبار من قاعدة البيانات
            res = supabase.table("quizzes").select("questions").eq("subject", current_subject).execute()
            if res.data:
                st.write("---")
                st.subheader(f"📋 معاينة اختبار مادة {current_subject} (من قاعدة البيانات):")
                quiz_data = res.data[0]['questions']
                for q in quiz_data:
                    st.write(f"**س{q['id']}: {q['question']}**")
                    for opt in q['options']:
                        st.write(f"- {opt}")
                    st.write(f"✅ **الإجابة الصحيحة:** ({q['correct']})")
                    st.write("---")

        with tab2:
            st.subheader(f"📊 نتائج إجابات الطلاب لمادة ({current_subject})")
            
            # جلب نتائج المادة الحالية من قاعدة البيانات
            res_sub = supabase.table("submissions").select("*").eq("subject", current_subject).order("created_at", desc=True).execute()
            
            if res_sub.data:
                for sub in res_sub.data:
                    st.write(f"👤 **اسم الطالب:** {sub['student_name']}")
                    st.write(f"💯 **الدرجة:** {sub['score']} من {sub['total']}")
                    st.write("**تفاصيل إجابات الطالب:**")
                    for detail in sub['details']:
                        st.write(f"- {detail['question']} | إجابة الطالب: ({detail['student_ans']}) | الإجابة الصحيحة: ({detail['correct_ans']})")
                    st.write("---")
            else:
                st.info(f"لا توجد إجابات مقدمة لمادة {current_subject} حتى الآن.")

# ---------------------------------------------------------
# بوابة الطالب
# ---------------------------------------------------------
elif role == "👨‍🎓 الطالب":
    st.header("بوابة الطالب")
    
    # جلب قائمة المواد المتاحة لها اختبارات من قاعدة البيانات
    res_quizzes = supabase.table("quizzes").select("subject, questions").execute()
    
    if res_quizzes.data:
        available_subjects = [item['subject'] for item in res_quizzes.data]
        selected_subject = st.selectbox("📚 اختر المادة التي تريد تقديم اختبارها:", available_subjects)
        
        student_name = st.text_input("اسم الطالب الكامل:")
        
        st.write("---")
        st.subheader(f"📝 اختبار مادة: {selected_subject}")
        
        # اختيار أسئلة المادة المحددة
        selected_quiz_data = next(item['questions'] for item in res_quizzes.data if item['subject'] == selected_subject)
        
        user_answers = {}
        all_answered = True
        
        for q in selected_quiz_data:
            st.markdown(f"#### س{q['id']}: {q['question']}")
            
            chosen = st.radio(
                "اختر الإجابة:", 
                q['options'], 
                index=None,
                key=f"q_{selected_subject}_{q['id']}"
            )
            
            if chosen is None:
                all_answered = False
                chosen_char = None
            else:
                chosen_char = chosen.split(")")[0].strip() if ")" in chosen else chosen[0]
            
            user_answers[q['id']] = {
                "chosen_char": chosen_char,
                "question": q['question'],
                "correct_char": q['correct']
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
                
                # حفظ النتيجة في Supabase
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
        st.info("لا توجد أي اختبارات متاحة حالياً لأي مادة. يرجى انتظار الأساتذة لتوليد الاختبارات.")
