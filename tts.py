import streamlit as st
import edge_tts
import asyncio
import os
import tempfile
import requests
import base64
from pathlib import Path

# Page config
st.set_page_config(page_title="Text to MP3 Converter", page_icon="🎙️", layout="centered")

# Title and description
st.title("🎙️ Text to MP3 Converter with Edge TTS")
st.markdown("Upload text files, convert them to speech using **EDGE TTS**, and get the MP3 files emailed to you via Resend API!")

# Default voice
DEFAULT_VOICE = "en-IN-NeerjaNeural"

# Resend API configuration (from secrets)
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "")
FROM_EMAIL = st.secrets.get("FROM_EMAIL", "onboarding@resend.dev")
TO_EMAIL = st.text_input("Recipient Email Address", placeholder="recipient@example.com", help="Where to send the MP3 files")

# Async function to convert text to speech
async def text_to_speech(text, output_file, voice=DEFAULT_VOICE):
    """Convert text to speech using Edge TTS"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

# Function to read text file
def read_text_file(uploaded_file):
    """Read content from uploaded text file"""
    try:
        content = uploaded_file.read().decode("utf-8")
        return content
    except UnicodeDecodeError:
        try:
            content = uploaded_file.read().decode("latin-1")
            return content
        except:
            return None

# Function to send email using Resend API
def send_email_via_resend(recipient_email, subject, body, attachment_path, api_key, from_email):
    """Send email with MP3 attachment using Resend API"""
    try:
        url = "https://api.resend.com/emails"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Read and encode attachment
        with open(attachment_path, 'rb') as f:
            attachment_content = base64.b64encode(f.read()).decode('utf-8')
        
        filename = os.path.basename(attachment_path)
        
        # Prepare payload
        payload = {
            "from": from_email,
            "to": [recipient_email],
            "subject": subject,
            "html": body.replace("\n", "<br>"),
            "attachments": [
                {
                    "filename": filename,
                    "content": attachment_content,
                    "content_type": "audio/mpeg"
                }
            ]
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return True, "Email sent successfully!"
        else:
            error_detail = response.json().get('message', 'Unknown error')
            return False, f"Resend API error: {error_detail}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

# Function to process single file (synchronous wrapper)
def process_single_file(uploaded_file, temp_dir, file_index):
    """Process a single uploaded file - synchronous wrapper"""
    file_name = uploaded_file.name
    file_content = read_text_file(uploaded_file)
    
    if file_content is None:
        return None, f"Failed to read {file_name}", None
    
    if not file_content.strip():
        return None, f"File {file_name} is empty", None
    
    mp3_filename = f"output_{file_index}_{Path(file_name).stem}.mp3"
    mp3_path = os.path.join(temp_dir, mp3_filename)
    
    try:
        # Run async function synchronously
        asyncio.run(text_to_speech(file_content, mp3_path, DEFAULT_VOICE))
        return mp3_path, f"Converted: {file_name}", file_name
    except Exception as e:
        return None, f"Error converting {file_name}: {str(e)}", None

# Main UI
st.markdown("---")

# Check API key
if not RESEND_API_KEY:
    st.error("⚠️ Resend API Key not found in secrets!")
    st.info("Please add RESEND_API_KEY to .streamlit/secrets.toml")
    st.stop()

# Upload options
upload_option = st.radio("Choose upload option:", ["Single File", "Batch of 5 Files"])

uploaded_files = []

if upload_option == "Single File":
    single_file = st.file_uploader("Upload a text file", type=['txt'], key="single")
    if single_file:
        uploaded_files = [single_file]
else:
    batch_files = st.file_uploader("Upload up to 5 text files", type=['txt'], accept_multiple_files=True, key="batch")
    if batch_files:
        if len(batch_files) > 5:
            st.warning("Maximum 5 files will be processed")
            uploaded_files = batch_files[:5]
        else:
            uploaded_files = batch_files

# Process button
if st.button("🚀 Convert and Send", type="primary"):
    if not uploaded_files:
        st.error("Please upload at least one text file.")
    elif not TO_EMAIL:
        st.error("Please provide recipient email address.")
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            # Process files (no await needed)
            for idx, file in enumerate(uploaded_files):
                status_text.info(f"Processing {idx+1}/{len(uploaded_files)}: {file.name}")
                mp3_path, message, original_name = process_single_file(file, temp_dir, idx+1)
                results.append((mp3_path, message, original_name))
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            # Send emails
            st.markdown("---")
            st.subheader("Sending emails...")
            
            successful = 0
            for mp3_path, message, original_name in results:
                if mp3_path and os.path.exists(mp3_path):
                    subject = f"Your MP3: {original_name}"
                    body = f"Your file '{original_name}' has been converted to MP3 using Edge TTS (Voice: en-IN-NeerjaNeural)."
                    
                    success, msg = send_email_via_resend(
                        TO_EMAIL, subject, body, mp3_path,
                        RESEND_API_KEY, FROM_EMAIL
                    )
                    
                    if success:
                        successful += 1
                        st.success(f"✅ Sent: {original_name}")
                    else:
                        st.error(f"❌ Failed: {original_name} - {msg}")
                else:
                    st.error(f"❌ Failed: {message}")
            
            # Summary
            st.markdown("---")
            if successful == len(uploaded_files):
                st.success(f"🎉 All {successful} files sent successfully!")
            elif successful > 0:
                st.warning(f"⚠️ Sent {successful}/{len(uploaded_files)} files")
            else:
                st.error("❌ No files were sent successfully")

# Instructions
with st.expander("📖 How to use"):
    st.markdown("--")
    **Setup Instructions:**
    
    1. **Get Resend API Key**:
       - Sign up at [Resend.com](https://resend.com)
       - Go to API Keys section
       - Create a new API key
       - Copy the key
    
    2. **Configure Secrets**:
       - Create `.streamlit/secrets.toml` in your app directory
       - Add the following:
