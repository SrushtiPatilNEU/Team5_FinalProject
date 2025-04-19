import streamlit as st
import requests
from datetime import date, timedelta
import io
import base64

# API endpoint
BACKEND_URL = "https://api-620400361669.us-central1.run.app"
st.set_page_config(page_title="Smart Travel Itinerary", layout="wide", page_icon="✈️")

# --- CSS Styling ---
st.markdown("""
<style>
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.user-msg, .bot-msg {
    padding: 10px 15px;
    border-radius: 12px;
    max-width: 70%;
    word-wrap: break-word;
}
.user-msg {
    background-color: #d1e7dd;
    align-self: flex-end;
    text-align: right;
}
.bot-msg {
    background-color: #f0f0f0;
    align-self: flex-start;
    text-align: left;
}
</style>
""", unsafe_allow_html=True)

# --- Reset Button ---
if st.sidebar.button("🔄 Reset App"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- Download PDF Helper ---
def create_download_link(pdf_bytes, filename):
    try:
        b64 = base64.b64encode(pdf_bytes.read()).decode()
        return f'''
        <a href="data:application/pdf;base64,{b64}" download="{filename}" 
           style="display:inline-block;padding:12px 20px;background-color:#3b82f6;color:white;
                  text-decoration:none;border-radius:8px;font-weight:600;text-align:center;">
            ⬇️ Download PDF Itinerary
        </a>
        '''
    except Exception:
        st.error("Error creating download link.")
        return ""

# --- Sidebar Form ---
with st.sidebar:
    st.title("Plan Your Trip")
    with st.form("travel_form"):
        city = st.selectbox("Destination City", ["New York", "San Francisco", "Chicago", "Seattle", "Las Vegas", "Los Angeles"])
        today = date.today()

        # Default values
        default_start = st.session_state.get("start_date", today + timedelta(days=1))
        default_end = st.session_state.get("end_date", default_start + timedelta(days=2))

        # Inputs
        start_date = st.date_input("Start Date", value=default_start, min_value=today + timedelta(days=1))
        end_date = st.date_input("End Date", value=default_end, min_value=today + timedelta(days=1))

        # Validate dates (after user selection)
        if end_date < start_date:
            st.warning("⚠️ End date cannot be before start date.")
            st.stop()

        preference = st.selectbox("Package", [
            "Suggest an itinerary with Tours, Accommodation, Things to do",
            "Suggest an itinerary with Accommodation, Things to do",
            "Suggest an itinerary with Things to do"
        ])
        budget = st.select_slider("Budget", options=["low", "medium", "high"], value="medium")
        submitted = st.form_submit_button("Generate Itinerary")

# --- Store to Session & Rerun ---
if submitted:
    st.session_state.clear()
    st.session_state.submitted = True
    st.session_state.city = city
    st.session_state.start_date = start_date
    st.session_state.end_date = end_date
    st.session_state.preference = preference
    st.session_state.budget = budget
    st.session_state.loading = True
    st.session_state.chat_history = []
    st.rerun()

# --- Generate Itinerary ---
if st.session_state.get("loading", False):
    st.info("⏳ Generating itinerary, please wait...")
    with st.spinner("Working on it..."):
        payload = {
            "city": st.session_state.city,
            "start_date": str(st.session_state.start_date),
            "end_date": str(st.session_state.end_date),
            "preference": st.session_state.preference,
            "travel_type": "Solo",
            "adults": 1,
            "kids": 0,
            "budget": st.session_state.budget,
            "include_tours": "Tours" in st.session_state.preference,
            "include_accommodation": "Accommodation" in st.session_state.preference,
            "include_things": "Things to do" in st.session_state.preference
        }

        try:
            res = requests.post(f"{BACKEND_URL}/generate-itinerary", json=payload, timeout=180)
            res.raise_for_status()
            data = res.json()
            st.session_state.itinerary_html = data["data"]["itinerary_html"]
            st.session_state.itinerary_text = data["data"]["itinerary_text"]
            st.session_state.generated_itinerary = data["data"]["itinerary_text"]

            pdf_response = requests.post(
                f"{BACKEND_URL}/generate-pdf",
                json={
                    "city": payload["city"],
                    "itinerary": st.session_state.itinerary_text,
                    "start_date": str(st.session_state.start_date)
                },
                timeout=60
            )
            pdf_response.raise_for_status()
            st.session_state.pdf_bytes = io.BytesIO(pdf_response.content)

            st.session_state.loading = False
            st.rerun()

        except Exception as e:
            st.session_state.loading = False
            st.error(f"❌ Failed to generate itinerary: {e}")
            st.stop()

# --- Display Itinerary ---
if st.session_state.get("itinerary_html"):
    st.success("✅ Your personalized itinerary is ready!")
    tabs = st.tabs(["📋 Itinerary", "📄 PDF Download", "💬 Ask About Your Itinerary"])

    with tabs[0]:
        st.components.v1.html(
            f"<html><body>{st.session_state.itinerary_html}</body></html>",
            height=800, scrolling=True
        )

    with tabs[1]:
        if "pdf_bytes" in st.session_state:
            st.markdown(create_download_link(st.session_state.pdf_bytes, f"{st.session_state.city}_Itinerary.pdf"), unsafe_allow_html=True)
        else:
            st.warning("PDF not available.")

    with tabs[2]:
        st.markdown("### 💬 Ask About Your Itinerary")
        question_key = f"question_input_{len(st.session_state.get('chat_history', []))}"
        question = st.text_input("Ask your question:", key=question_key)

        if st.button("Ask Question"):
            if question.strip():
                with st.spinner("Finding answers..."):
                    try:
                        res = requests.post(
                            f"{BACKEND_URL}/ask",
                            json={"itinerary": st.session_state.generated_itinerary, "question": question},
                            timeout=60
                        )
                        res.raise_for_status()
                        answer = res.json().get("answer")
                        st.session_state.chat_history.append((question, answer))
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            else:
                st.warning("Please enter a question.")

        if st.session_state.get("chat_history"):
            st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
            for q, a in st.session_state.chat_history[::-1]:
                st.markdown(f"""
                <div class='chat-row'>
                    <div class='label'>You</div>
                    <div class='chat-user'>{q}</div>
                </div>
                <div class='chat-row'>
                    <div class='label'>Response</div>
                    <div class='chat-bot'>{a}</div>
                </div><br>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# --- Welcome Message ---
elif not st.session_state.get("submitted"):
    st.markdown("## 👋 Welcome to Smart Travel Itinerary")
    st.markdown("Use the sidebar to generate your personalized travel plan with tours, stays, and hidden gems.")
