import streamlit as st
import pypdf
import json
from groq import Groq

# 1. مفتاح Groq الخاص بك
GROQ_API_KEY = "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"

# 2. حسابات الأساتذة والمواد المسندة لكل منهم
TEACHERS_DB = {
    "أ. عمر": {"password": "bio123", "subject": "الأحياء"},
    "أ. أحمد": {"password": "math123", "subject": "الرياضيات"},
    "أ. فتوح": {"password": "physics123", "subject": "الفيزياء"}
}

client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="منصة منارة التعليمية", layout="wide")
st.title("🎓 نظام الاختبارات الذكي (منارة)")

role = st.sidebar.radio("اختر الدور:", ["👨‍🏫 الأستاذ", "👨‍🎓 الطالب"])

# تهيئة المتغيرات في الجلسة لتخزين الاختبارات والنتائج حسب المادة
if 'quizzes' not in st.session_state:
    st.session_state['quizzes'] = {}  # مثال: {"الأحياء": [...], "الرياضيات": [...]}
if 'submissions' not in st.session_state:
    st.session_state['submissions'] = []
if 'logged_teacher' not in st.session_state:
    st.session_state['logged_teacher'] = None

# ---------------------------------------------------------
# بوابة الأستاذ
# ---------------------------------------------------------
if role == "👨‍🏫 الأستاذ":
    st.header("بوابة الأستاذ")
    
    # 1. شاشة تسجيل الدخول للأستاذ
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
                with st.spinner(f"جاري توليد اختبار مادة {current_subject}..."):
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
                        short_text = clean_text[:3500]
                        
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

                        response = client.chat.completions.create(
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
                        
                        # حفظ الاختبار تحت اسم المادة الخاصة بالأستاذ
                        st.session_state['quizzes'][current_subject] = quiz_json
                        st.success(f"تم توليد ونشر اختبار مادة {current_subject} بنجاح!")
                        
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء معالجة الاختبار: {e}")

            # معاينة اختبار المادة الحالية إن وجد
            if current_subject in st.session_state['quizzes']:
                st.write("---")
                st.subheader(f"📋 معاينة اختبار مادة {current_subject}:")
                for q in st.session_state['quizzes'][current_subject]:
                    st.write(f"**س{q['id']}: {q['question']}**")
                    for opt in q['options']:
                        st.write(f"- {opt}")
                    st.write(f"✅ **الإجابة الصحيحة:** ({q['correct']})")
                    st.write("---")

        with tab2:
            st.subheader(f"📊 نتائج إجابات الطلاب لمادة ({current_subject})")
            
            # تصفية نتائج الطلاب الخاصة بمادة هذا الأستاذ فقط
            subject_submissions = [s for s in st.session_state['submissions'] if s['subject'] == current_subject]
            
            if subject_submissions:
                for sub in subject_submissions:
                    st.write(f"👤 **اسم الطالب:** {sub['name']}")
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
    
    # اختيار المادة المراد الإجابة عنها
    available_subjects = list(st.session_state['quizzes'].keys())
    
    if available_subjects:
        selected_subject = st.selectbox("📚 اختر المادة التي تريد تقديم اختبارها:", available_subjects)
        
        student_name = st.text_input("اسم الطالب الكامل:")
        
        st.write("---")
        st.subheader(f"📝 اختبار مادة: {selected_subject}")
        
        quiz_data = st.session_state['quizzes'][selected_subject]
        user_answers = {}
        all_answered = True
        
        for q in quiz_data:
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
                total = len(quiz_data)
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
                
                # حفظ النتيجة مع تحديد اسم المادة
                st.session_state['submissions'].append({
                    "name": student_name,
                    "subject": selected_subject,
                    "score": score,
                    "total": total,
                    "details": details
                })
                
                st.balloons()
                st.success(f"تم تسليم إجابة اختبار {selected_subject} بنجاح يا {student_name}! درجتك هي: {score} من {total}")
    else:
        st.info("لا توجد أي اختبارات متاحة حالياً لأي مادة. يرجى انتظار الأساتذة لتوليد الاختبارات.")