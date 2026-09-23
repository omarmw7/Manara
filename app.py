import streamlit as st
import pypdf
import json
import re
import pandas as pd
from datetime import datetime
from groq import Groq
from supabase import create_client, Client

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception as e:
    st.error("يرجى إعداد مفاتيح Supabase (Secrets) في لوحة تحكم Streamlit Cloud أولاً.")
    st.stop()

GROQ_API_KEY = "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"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

TEACHERS_DB = {
    "أ. عمر": {"password": "bio123", "subject": "الأحياء"},
    "أ. سيد": {"password": "math123", "subject": "الرياضيات"},
    "أ. رجب": {"password": "islamic123", "subject": "التربية الإسلامية"},
    "أ. محمد": {"password": "chm123", "subject": "الكيمياء"}
}

st.set_page_config(page_title="منصة منارة التعليمية", layout="wide")

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

def parse_questions_data(raw_data):
    if not raw_data:
        return []
    if isinstance(raw_data, str):
        try:
            parsed = json.loads(raw_data)
            return parse_questions_data(parsed)
        except Exception:
            clean_text = re.sub(r'```(?:json)?', '', raw_data, flags=re.IGNORECASE).strip()
            clean_text = clean_text.replace('
