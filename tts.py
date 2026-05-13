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
st.markdown("Upload text files, convert them to speech using **EDGE TTS**, and get the MP3 files emailed to you!")

# Default voice
DEFAULT_VOICE = "en-IN-NeerjaNeural"

# Hardcoded email configuration
FROM_EMAIL = "onboarding@resend.dev"
TO_EMAIL = "mrxanddrvidya2023@gmail.com"

# Resend API configuration (from secrets)
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "")

# Initialize session state for downloaded files
if 'converted_files' not in st.session_state:
    st.session_state.converted_files = []
if 'conversion_status' not in st.session_state:
    st.session_state.conversion_status = {}

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
        
        # Store file info for manual download
        file_info = {
            'name': f"{Path(file_name).stem}.mp3",
            'path': mp3_path,
            'original_name': file_name,
            'size': os.path.getsize(mp3_path)
        }
        
        return mp3_path, f"Converted: {file_name}", file_name, file_info
    except Exception as e:
        return None, f"Error converting {file_name}: {str(e)}", None, None

# Quick Start Guide
with st.expander("📖 Quick Start Guide", expanded=True):
    st.markdown("""
    **Quick Start:**
    1. Upload Text Files (Single or Batch up to 5)
    2. Click "Convert & Auto-Send Email"
    3. Wait for processing - Each file converts sequentially
    4. Check your email - MP3 sent to mrxanddrvidya2023@gmail.com
    5. Download manually from the download section if needed
    
    **✨ Features:**
    - Auto-email: MP3 sent immediately after each conversion
    - Manual download: Download MP3 files directly from app
    - Batch processing: Up to 5 files at once
    - Indian English voice: en-IN-NeerjaNeural
    
    **📧 Email Configuration (Hardcoded):**
    - From: onboarding@resend.dev
    - To: mrxanddrvidya2023@gmail.com
    """)

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

# Display uploaded files
if uploaded_files:
    st.info(f"📁 {len(uploaded_files)} file(s) ready for conversion")

# Process button
if st.button("🔄 Convert & Auto-Send Email", type="primary"):
    if not uploaded_files:
        st.error("Please upload at least one text file.")
    else:
        # Clear previous session data
        st.session_state.converted_files = []
        st.session_state.conversion_status = {}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            progress_bar = st.progress(0)
            status_text = st.empty()
            email_status = st.empty()
            results = []
            
            # Process files sequentially
            for idx, file in enumerate(uploaded_files):
                # Update status
                status_text.info(f"🎙️ Processing file {idx+1}/{len(uploaded_files)}: **{file.name}**")
                
                # Convert file
                mp3_path, message, original_name, file_info = process_single_file(file, temp_dir, idx+1)
                
                if mp3_path and os.path.exists(mp3_path):
                    # Store for manual download
                    st.session_state.converted_files.append(file_info)
                    st.session_state.conversion_status[original_name] = 'converted'
                    
                    # Display conversion success
                    status_text.success(f"✅ Converted: {file.name}")
                    
                    # Send email immediately after conversion
                    email_status.info(f"📧 Sending email for: {original_name}...")
                    subject = f"Your MP3: {original_name}"
                    body = f"""
                    Your file '{original_name}' has been converted to MP3 using Edge TTS.
                    
                    Voice: en-IN-NeerjaNeural (Indian English)
                    File size: {file_info['size'] / 1024:.2f} KB
                    
                    Thank you for using our Text to MP3 Converter!
                    """
                    
                    success, msg = send_email_via_resend(
                        TO_EMAIL, subject, body, mp3_path,
                        RESEND_API_KEY, FROM_EMAIL
                    )
                    
                    if success:
                        email_status.success(f"📧 Email sent for: {original_name}")
                        st.session_state.conversion_status[original_name] = 'emailed'
                    else:
                        email_status.warning(f"⚠️ Email failed for {original_name}: {msg}")
                        st.session_state.conversion_status[original_name] = 'email_failed'
                else:
                    status_text.error(f"❌ {message}")
                    st.session_state.conversion_status[original_name] = 'failed'
                
                # Update progress
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            # Clear status messages after processing
            status_text.empty()
            email_status.empty()
            
            # Summary
            st.markdown("---")
            successful_conversions = sum(1 for status in st.session_state.conversion_status.values() if status in ['converted', 'emailed', 'email_failed'])
            successful_emails = sum(1 for status in st.session_state.conversion_status.values() if status == 'emailed')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Files Processed", successful_conversions)
            with col2:
                st.metric("Emails Sent", successful_emails)
            with col3:
                st.metric("Total Files", len(uploaded_files))
            
            if successful_conversions == len(uploaded_files):
                st.success(f"🎉 All {successful_conversions} files converted successfully!")
                if successful_emails == len(uploaded_files):
                    st.balloons()
                    st.success("📧 All MP3 files have been sent to mrxanddrvidya2023@gmail.com!")
                else:
                    st.info("💾 You can download the converted MP3 files from the section below.")
            else:
                st.error("❌ Some files failed to convert")

# Manual download section
st.markdown("---")
st.subheader("💾 Manual Download Section")

if st.session_state.converted_files:
    st.info(f"📀 {len(st.session_state.converted_files)} converted file(s) available for download")
    
    for file_info in st.session_state.converted_files:
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            st.write(f"**{file_info['name']}**")
            st.caption(f"Original: {file_info['original_name']} | Size: {file_info['size'] / 1024:.2f} KB")
        
        with col2:
            # Read file content for download
            with open(file_info['path'], 'rb') as f:
                mp3_data = f.read()
            
            st.download_button(
                label="📥 Download MP3",
                data=mp3_data,
                file_name=file_info['name'],
                mime="audio/mpeg",
                key=f"download_{file_info['name']}"
            )
        
        with col3:
            if st.session_state.conversion_status.get(file_info['original_name']) == 'emailed':
                st.success("📧 Sent")
            elif st.session_state.conversion_status.get(file_info['original_name']) == 'email_failed':
                st.warning("⚠️ Email failed")
            else:
                st.info("✅ Converted")
else:
    st.info("No converted files yet. Upload and convert files to see them here.")

# Clear all button
if st.session_state.converted_files:
    if st.button("🗑️ Clear All Converted Files"):
        st.session_state.converted_files = []
        st.session_state.conversion_status = {}
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Made with ❤️ using Edge TTS | Voice: en-IN-NeerjaNeural (Indian English)
    </div>
    """,
    unsafe_allow_html=True
)
