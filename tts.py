import streamlit as st
import edge_tts
import asyncio
import os
import smtplib
from email.mime.text import MimeText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import tempfile
import zipfile
from io import BytesIO

# Page config
st.set_page_config(page_title="Text to MP3 Converter", page_icon="🎙️", layout="centered")

# Title and description
st.title("🎙️ Text to MP3 Converter with Edge TTS")
st.markdown("Upload text files, convert them to speech using **EDGE TTS**, and get the MP3 files emailed to you!")

# Default voice
DEFAULT_VOICE = "en-IN-NeerjaNeural"

# Email configuration (you can move these to secrets or environment variables)
# For production, use st.secrets instead of hardcoding
EMAIL_ADDRESS = st.text_input("Your Email Address", placeholder="you@example.com", help="We'll send the MP3 files to this email")
EMAIL_PASSWORD = st.text_input("Email App Password", type="password", help="Use app-specific password for Gmail/Outlook")
SMTP_SERVER = st.selectbox("SMTP Server", ["smtp.gmail.com", "smtp.outlook.com", "smtp.mail.yahoo.com"])
SMTP_PORT = 587

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

# Function to send email with MP3 attachment
def send_email_with_attachment(recipient_email, subject, body, attachment_path, sender_email, sender_password, smtp_server, smtp_port):
    """Send email with MP3 attachment"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach body
        msg.attach(MimeText(body, 'plain'))
        
        # Attach file
        with open(attachment_path, 'rb') as file:
            part = MIMEBase('audio', 'mp3')
            part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment_path)}"')
            msg.attach(part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True, "Email sent successfully!"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

# Function to process single file
async def process_single_file(uploaded_file, temp_dir, file_index):
    """Process a single uploaded file"""
    file_name = uploaded_file.name
    file_content = read_text_file(uploaded_file)
    
    if file_content is None:
        return None, f"❌ Failed to read {file_name}", None
    
    if not file_content.strip():
        return None, f"⚠️ {file_name} is empty", None
    
    # Create MP3 file path
    mp3_filename = f"output_{file_index}_{os.path.splitext(file_name)[0]}.mp3"
    mp3_path = os.path.join(temp_dir, mp3_filename)
    
    # Convert to speech
    try:
        await text_to_speech(file_content, mp3_path, DEFAULT_VOICE)
        return mp3_path, f"✅ Converted: {file_name} → {mp3_filename}", file_name
    except Exception as e:
        return None, f"❌ Error converting {file_name}: {str(e)}", None

# Main application
st.markdown("---")

# Upload options
upload_option = st.radio("Choose upload option:", ["Single File", "Batch of 5 Files"])

uploaded_files = []
single_file = None

if upload_option == "Single File":
    single_file = st.file_uploader("Upload a text file", type=['txt'], key="single")
    if single_file:
        uploaded_files = [single_file]
else:
    batch_files = st.file_uploader("Upload up to 5 text files", type=['txt'], accept_multiple_files=True, key="batch")
    if batch_files and len(batch_files) > 5:
        st.warning("Please upload maximum 5 files. Only first 5 will be processed.")
        uploaded_files = batch_files[:5]
    elif batch_files:
        uploaded_files = batch_files

# Process button
if st.button("🚀 Convert and Send", type="primary"):
    if not uploaded_files:
        st.error("Please upload at least one text file.")
    elif not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        st.error("Please provide email credentials.")
    else:
        # Create temporary directory for MP3 files
        with tempfile.TemporaryDirectory() as temp_dir:
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            # Process each file
            for idx, file in enumerate(uploaded_files):
                status_text.write(f"📄 Processing {idx+1}/{len(uploaded_files)}: {file.name}...")
                
                mp3_path, message, original_name = await process_single_file(file, temp_dir, idx+1)
                results.append((mp3_path, message, original_name))
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            # Send emails
            st.markdown("---")
            st.subheader("📧 Sending emails...")
            
            successful_sends = 0
            for idx, (mp3_path, message, original_name) in enumerate(results):
                if mp3_path and os.path.exists(mp3_path):
                    status_text.write(f"📧 Sending email for {original_name}...")
                    
                    subject = f"Your MP3 Conversion: {original_name}"
                    body = f"Dear User,\n\nYour text file '{original_name}' has been successfully converted to speech using Edge TTS.\n\nPlease find attached the MP3 file.\n\nBest regards,\nTTS Converter"
                    
                    success, msg = send_email_with_attachment(
                        EMAIL_ADDRESS, subject, body, mp3_path,
                        EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT
                    )
                    
                    if success:
                        successful_sends += 1
                        st.success(f"✅ {original_name} - Email sent!")
                    else:
                        st.error(f"❌ {original_name} - {msg}")
                else:
                    st.error(f"❌ {original_name or f'File {idx+1}'} - Conversion failed")
            
            # Final summary
            st.markdown("---")
            if successful_sends == len(uploaded_files):
                st.success(f"🎉 All {successful_sends} files processed and sent successfully!")
            elif successful_sends > 0:
                st.warning(f"⚠️ {successful_sends}/{len(uploaded_files)} files sent successfully.")
            else:
                st.error("❌ No files were sent. Please check the errors above.")
            
            # Display all messages
            st.subheader("📋 Processing Log:")
            for _, message, _ in results:
                st.text(message)

# Instructions
with st.expander("📖 How to use this app"):
    st.markdown("""
    ### Setup Instructions:
    1. **Get Email App Password**:
       - For Gmail: Enable 2FA and generate an App Password
       - For Outlook: Use your regular password or App Password
    
    2. **Upload Text Files**:
       - Single file: Choose one .txt file
       - Batch: Choose up to 5 .txt files
    
    3. **Enter Email Credentials**:
       - Your email address
       - App password (not your regular password)
    
    4. **Click Convert & Send**
    
    ### Features:
    - Uses **Edge TTS** (Microsoft's neural voices)
    - Default voice: **en-IN-NeerjaNeural** (Indian English female)
    - Each file gets converted individually
    - You receive separate emails for each MP3
    - Works with large text files
    
    ### Note:
    - Text files must be UTF-8 encoded
    - For batch processing, files are processed sequentially
    - MP3 files are deleted from server after sending
    """)

# Footer
st.markdown("---")
st.markdown("Built with Streamlit + Edge TTS | © 2024")
