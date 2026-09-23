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
    "أ. فتوح": {"password": "math123", "subject": "الرياضيات"},
    "أ. رجب": {"password": "islamic123", "subject": "التربية الإسلامية"}
}

st.set_page_config(page_title="منصة منارة التعليمية", layout="wide")
st.title("🎓 نظام الاختبارات الذكي (منارة)")

role = st.sidebar.radio("اختر الدور:", ["👨‍🏫 الأستاذ", "👨‍🎓 الطالب"])

if 'logged_teacher' not in st.session_state:
    st.session_state['logged_teacher'] = None

# دالة معالجة واستخراج الـ JSON بأمان كامل
def parse_questions_data(raw_data):
    if not raw_data:
        return []
    
    # إذا كانت البيانات قادمة كـ String
    if isinstance(raw_data, str):
        try:
            parsed = json.loads(raw_data)
            return parse_questions_data(parsed)
        except Exception:
            # محاولة استخراج صيغة القائمة JSON باستخدام Regular Expression
            match = re.search(r'\[\s*\{.*\}\s*\]', raw_data, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            return []
            
    # إذا كانت البيانات List
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

أرجع فقط قائمة JSON حصرية بنفس الشكل التالي تماماً وبدون أي نصوص إضافية:
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
                                {"role": "system", "content": "أنت مساعد تعليمي تخرج النتائج بصيغة JSON فقط."},
                                {"role": "user", "content": prompt}
                            ],
                            model="qwen/qwen3.8-27b",
                            temperature=0.1
                        )
                        
                        raw_response = response.choices[0].message.content.strip()
                        
                        # استخراج الـ JSON
                        quiz_json = parse_questions_data(raw_response)
                        
                        if not quiz_json:
                            # محاولة تنظيف بسيطة في حال عدم المطابقة
                            clean_str = raw_response.replace("```json", "").replace("
