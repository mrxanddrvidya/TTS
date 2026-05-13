import streamlit as st
import edge_tts
import asyncio
import os
import tempfile
import requests
import base64
import shutil
import zipfile
from pathlib import Path
import time

# Page config
st.set_page_config(page_title="Text to MP3 Converter", page_icon="🎙️", layout="centered")

# Custom CSS to keep screen on during processing
st.markdown("""
<style>
    /* Prevent screen sleep during processing */
    @keyframes keepAwake {
        0% { opacity: 0.99; }
        100% { opacity: 1; }
    }
    
    .processing-active {
        animation: keepAwake 30s infinite;
    }
    
    /* Loading spinner animation */
    .loader {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Progress bar styling */
    .stProgress > div > div {
        background-color: #667eea;
    }
</style>

<script>
    // Function to keep screen awake using NoSleep.js approach
    function keepScreenAwake() {
        let wakeLock = null;
        
        async function requestWakeLock() {
            try {
                if ('wakeLock' in navigator) {
                    wakeLock = await navigator.wakeLock.request('screen');
                    console.log('Screen wake lock acquired');
                }
            } catch (err) {
                console.log('Wake lock not supported:', err);
            }
        }
        
        function releaseWakeLock() {
            if (wakeLock !== null) {
                wakeLock.release().then(() => {
                    console.log('Screen wake lock released');
                    wakeLock = null;
                });
            }
        }
        
        return { requestWakeLock, releaseWakeLock };
    }
    
    // Expose functions to Streamlit
    window.keepScreenAwake = keepScreenAwake;
</script>
""", unsafe_allow_html=True)

# Title and description
st.title("🎙️ Text to MP3 Converter with Edge TTS")
st.markdown("Upload text files, convert them to speech using **EDGE TTS**, and get the MP3 files emailed to you!")

# Voice options (female voices)
VOICE_OPTIONS = {
    "en-IN-NeerjaNeural (Indian English - Default)": "en-IN-NeerjaNeural",
    "en-US-JennyNeural (US English)": "en-US-JennyNeural",
    "en-US-AriaNeural (US English)": "en-US-AriaNeural",
    "en-GB-SoniaNeural (UK English)": "en-GB-SoniaNeural",
    "en-GB-LibbyNeural (UK English)": "en-GB-LibbyNeural",
    "en-AU-NatashaNeural (Australian English)": "en-AU-NatashaNeural",
    "en-CA-ClaraNeural (Canadian English)": "en-CA-ClaraNeural",
    "hi-IN-SwaraNeural (Hindi - Female)": "hi-IN-SwaraNeural"
}

# Default voice (Neerja)
DEFAULT_VOICE = "en-IN-NeerjaNeural"

# Voice selection in sidebar
st.sidebar.header("🎤 Voice Settings")
selected_voice_name = st.sidebar.selectbox(
    "Select Voice (Female Voices)",
    options=list(VOICE_OPTIONS.keys()),
    index=0  # Default to Neerja
)
selected_voice = VOICE_OPTIONS[selected_voice_name]

st.sidebar.info(f"Current voice: **{selected_voice_name.split('(')[0].strip()}**")

# Hardcoded email configuration
FROM_EMAIL = "PBTTS <onboarding@resend.dev>"
TO_EMAIL = "mrxanddrvidya2023@gmail.com"

# Create persistent directory for MP3 files and zip files
MP3_STORAGE_DIR = "converted_mp3s"
ZIP_STORAGE_DIR = "converted_zips"
if not os.path.exists(MP3_STORAGE_DIR):
    os.makedirs(MP3_STORAGE_DIR)
if not os.path.exists(ZIP_STORAGE_DIR):
    os.makedirs(ZIP_STORAGE_DIR)

# Resend API configuration (from secrets)
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "")

# Initialize session state for downloaded files
if 'converted_files' not in st.session_state:
    st.session_state.converted_files = []
if 'conversion_status' not in st.session_state:
    st.session_state.conversion_status = {}
if 'processing' not in st.session_state:
    st.session_state.processing = False

# Function to zip a file
def zip_file(file_path, zip_name=None):
    """Create a zip file from the given file"""
    if zip_name is None:
        zip_name = Path(file_path).stem + ".zip"
    
    zip_path = os.path.join(ZIP_STORAGE_DIR, zip_name)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, arcname=os.path.basename(file_path))
    
    return zip_path

# Async function to convert text to speech with progress tracking
async def text_to_speech(text, output_file, voice=DEFAULT_VOICE, progress_callback=None):
    """Convert text to speech using Edge TTS with progress tracking"""
    communicate = edge_tts.Communicate(text, voice)
    
    # For long files, we can't get granular progress, but we can simulate
    if progress_callback:
        progress_callback(0.5)  # Started
    
    await communicate.save(output_file)
    
    if progress_callback:
        progress_callback(1.0)  # Completed

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

# Function to send email with attachment (supports MP3 or ZIP)
def send_email_with_attachment(recipient_email, subject, body, attachment_path, api_key, from_email, is_zip=False):
    """Send email with MP3 or ZIP attachment using Resend API"""
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
        content_type = "application/zip" if is_zip else "audio/mpeg"
        
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
                    "content_type": content_type
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

# Function to process single file with voice selection
def process_single_file(uploaded_file, file_index, voice, keep_awake_callback=None):
    """Process a single uploaded file"""
    file_name = uploaded_file.name
    file_content = read_text_file(uploaded_file)
    
    if file_content is None:
        return None, f"Failed to read {file_name}", None
    
    if not file_content.strip():
        return None, f"File {file_name} is empty", None
    
    # Create persistent filename
    base_name = Path(file_name).stem
    mp3_filename = f"{file_index}_{base_name}.mp3"
    mp3_path = os.path.join(MP3_STORAGE_DIR, mp3_filename)
    
    try:
        # Run async function synchronously with progress
        async def convert_with_progress():
            await text_to_speech(file_content, mp3_path, voice)
        
        asyncio.run(convert_with_progress())
        
        file_size = os.path.getsize(mp3_path)
        is_large_file = file_size > 30 * 1024 * 1024  # 30MB in bytes
        
        file_info = {
            'name': f"{base_name}.mp3",
            'path': mp3_path,
            'original_name': file_name,
            'size': file_size,
            'timestamp': file_index,
            'is_large': is_large_file,
            'zip_path': None
        }
        
        # If file is large, create a zip version
        if is_large_file:
            zip_filename = f"{file_index}_{base_name}.zip"
            zip_path = zip_file(mp3_path, zip_filename)
            file_info['zip_path'] = zip_path
            file_info['zip_size'] = os.path.getsize(zip_path)
        
        return mp3_path, f"Converted: {file_name}", file_name, file_info
        
    except Exception as e:
        return None, f"Error converting {file_name}: {str(e)}", None, None

# Function to keep screen awake using JavaScript
def keep_screen_awake():
    """Inject JavaScript to keep screen awake during processing"""
    keep_awake_js = """
    <script>
    if (typeof window.wakeLockRequested === 'undefined') {
        window.wakeLockRequested = true;
        let wakeLock = null;
        
        async function requestWakeLock() {
            try {
                if ('wakeLock' in navigator) {
                    wakeLock = await navigator.wakeLock.request('screen');
                    console.log('Screen wake lock acquired for TTS processing');
                    
                    // Re-acquire if page becomes visible again
                    document.addEventListener('visibilitychange', async () => {
                        if (wakeLock !== null && document.visibilityState === 'visible') {
                            wakeLock = await navigator.wakeLock.request('screen');
                        }
                    });
                }
            } catch (err) {
                console.log('Wake lock error:', err);
            }
        }
        
        function releaseWakeLock() {
            if (wakeLock !== null) {
                wakeLock.release().then(() => {
                    console.log('Screen wake lock released');
                    wakeLock = null;
                });
            }
        }
        
        requestWakeLock();
        
        // Store release function for later use
        window.releaseWakeLock = releaseWakeLock;
    }
    </script>
    """
    st.markdown(keep_awake_js, unsafe_allow_html=True)

# Function to release screen wake lock
def release_screen_wake():
    """Release the screen wake lock"""
    release_js = """
    <script>
    if (typeof window.releaseWakeLock === 'function') {
        window.releaseWakeLock();
        window.wakeLockRequested = false;
    }
    </script>
    """
    st.markdown(release_js, unsafe_allow_html=True)

# Function to cleanup old files
def cleanup_old_files(keep_count=10):
    """Keep only the last 'keep_count' files to save space"""
    mp3_files = sorted(
        [f for f in os.listdir(MP3_STORAGE_DIR) if f.endswith('.mp3')],
        key=lambda x: os.path.getmtime(os.path.join(MP3_STORAGE_DIR, x)),
        reverse=True
    )
    
    for old_file in mp3_files[keep_count:]:
        try:
            os.remove(os.path.join(MP3_STORAGE_DIR, old_file))
        except:
            pass
    
    # Clean up old zip files
    zip_files = sorted(
        [f for f in os.listdir(ZIP_STORAGE_DIR) if f.endswith('.zip')],
        key=lambda x: os.path.getmtime(os.path.join(ZIP_STORAGE_DIR, x)),
        reverse=True
    )
    
    for old_file in zip_files[keep_count:]:
        try:
            os.remove(os.path.join(ZIP_STORAGE_DIR, old_file))
        except:
            pass

# Quick Start Guide with new features
with st.expander("📖 Quick Start Guide", expanded=True):
    st.markdown("""
    **Quick Start:**
    1. Select Voice (Sidebar) - Default: en-IN-NeerjaNeural
    2. Upload Text Files (Single or Batch up to 5)
    3. Click "Convert & Auto-Send Email"
    4. Wait for processing - Screen stays awake during long conversions
    5. Check your email - MP3 sent (ZIP compressed if over 30MB)
    6. Download manually from the section below
    
    **✨ New Features:**
    - 📦 **Auto-ZIP**: Files > 30MB are automatically compressed and sent as ZIP
    - 💤 **Screen Keep-Alive**: Screen stays on during long file processing
    - 🎤 **Multiple Female Voices**: Choose from 8 different female voices
    - 📧 **Smart Email**: Automatically handles large file attachments
    
    **📧 Email Configuration:**
    - From: PBTTS &lt;onboarding@resend.dev&gt;
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

# Display uploaded files and voice info
if uploaded_files:
    st.info(f"📁 {len(uploaded_files)} file(s) ready for conversion")
    st.info(f"🎤 Using voice: **{selected_voice_name}**")

# Process button
if st.button("🔄 Convert & Auto-Send Email", type="primary"):
    if not uploaded_files:
        st.error("Please upload at least one text file.")
    else:
        # Keep screen awake during processing
        keep_screen_awake()
        st.session_state.processing = True
        
        # Clear previous session data
        st.session_state.converted_files = []
        st.session_state.conversion_status = {}
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        email_status = st.empty()
        size_warning = st.empty()
        results = []
        
        # Process files sequentially
        for idx, file in enumerate(uploaded_files):
            # Update status
            status_text.info(f"🎙️ Processing file {idx+1}/{len(uploaded_files)}: **{file.name}**")
            
            # Show loading spinner for long files
            with st.spinner(f"Converting {file.name}... This may take a while for large files"):
                # Convert file with selected voice
                mp3_path, message, original_name, file_info = process_single_file(file, idx+1, selected_voice)
            
            if mp3_path and os.path.exists(mp3_path):
                # Store for manual download
                st.session_state.converted_files.append(file_info)
                st.session_state.conversion_status[original_name] = 'converted'
                
                # Display conversion success with size info
                if file_info['is_large']:
                    status_text.success(f"✅ Converted: {file.name} (Size: {file_info['size'] / (1024*1024):.2f} MB - Will be zipped)")
                    size_warning.info(f"📦 File exceeds 30MB, will be compressed to ZIP for email")
                else:
                    status_text.success(f"✅ Converted: {file.name} (Size: {file_info['size'] / 1024:.2f} KB)")
                
                # Send email immediately after conversion
                email_status.info(f"📧 Sending email for: {original_name}...")
                subject = f"Your {'ZIP' if file_info['is_large'] else 'MP3'}: {original_name}"
                
                # Determine which file to send
                attachment_to_send = file_info['zip_path'] if file_info['is_large'] else mp3_path
                is_zip = file_info['is_large']
                
                file_size_display = f"{file_info['size'] / (1024*1024):.2f} MB" if file_info['is_large'] else f"{file_info['size'] / 1024:.2f} KB"
                
                body = f"""
                Your file '{original_name}' has been converted to MP3 using Edge TTS.
                
                Voice: {selected_voice_name}
                Original MP3 size: {file_size_display}
                {'The file was compressed to ZIP format as it exceeded 30MB.' if file_info['is_large'] else ''}
                
                Thank you for using our Text to MP3 Converter!
                """
                
                success, msg = send_email_with_attachment(
                    TO_EMAIL, subject, body, attachment_to_send,
                    RESEND_API_KEY, FROM_EMAIL, is_zip
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
        size_warning.empty()
        
        # Cleanup old files (keep last 10)
        cleanup_old_files(keep_count=10)
        
        # Release screen wake lock
        release_screen_wake()
        st.session_state.processing = False
        
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
                st.success("📧 All files have been sent to mrxanddrvidya2023@gmail.com!")
            else:
                st.info("💾 You can download the converted files from the section below.")
        else:
            st.error("❌ Some files failed to convert")

# Manual download section
st.markdown("---")
st.subheader("💾 Manual Download Section")

if st.session_state.converted_files:
    st.info(f"📀 {len(st.session_state.converted_files)} converted file(s) available for download")
    
    # Sort files by timestamp (newest first)
    sorted_files = sorted(st.session_state.converted_files, key=lambda x: x.get('timestamp', 0), reverse=True)
    
    for file_info in sorted_files:
        # Check if file still exists
        if os.path.exists(file_info['path']):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{file_info['name']}**")
                size_text = f"Original: {file_info['original_name']} | Size: {file_info['size'] / 1024:.2f} KB"
                if file_info['is_large']:
                    size_text += f" | ⚠️ Over 30MB (ZIP available)"
                st.caption(size_text)
            
            with col2:
                col2_1, col2_2 = st.columns(2)
                
                with col2_1:
                    # Read file content for download
                    with open(file_info['path'], 'rb') as f:
                        mp3_data = f.read()
                    
                    st.download_button(
                        label="📥 Download MP3",
                        data=mp3_data,
                        file_name=file_info['name'],
                        mime="audio/mpeg",
                        key=f"download_mp3_{file_info['name']}_{file_info['timestamp']}"
                    )
                
                with col2_2:
                    # If large file, also offer ZIP download
                    if file_info['is_large'] and file_info.get('zip_path') and os.path.exists(file_info['zip_path']):
                        with open(file_info['zip_path'], 'rb') as f:
                            zip_data = f.read()
                        
                        st.download_button(
                            label="📦 Download ZIP",
                            data=zip_data,
                            file_name=f"{Path(file_info['name']).stem}.zip",
                            mime="application/zip",
                            key=f"download_zip_{file_info['name']}_{file_info['timestamp']}"
                        )
            
            with col3:
                if st.session_state.conversion_status.get(file_info['original_name']) == 'emailed':
                    st.success("📧 Sent")
                elif st.session_state.conversion_status.get(file_info['original_name']) == 'email_failed':
                    st.warning("⚠️ Email failed")
                else:
                    st.info("✅ Converted")
        else:
            # File no longer exists, remove from session
            st.session_state.converted_files.remove(file_info)
            st.warning(f"File {file_info['name']} no longer available")
else:
    st.info("No converted files yet. Upload and convert files to see them here.")

# Clear all button
if st.session_state.converted_files:
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🗑️ Clear All Converted Files", type="secondary"):
            # Delete physical files
            for file_info in st.session_state.converted_files:
                try:
                    if os.path.exists(file_info['path']):
                        os.remove(file_info['path'])
                    if file_info.get('zip_path') and os.path.exists(file_info['zip_path']):
                        os.remove(file_info['zip_path'])
                except:
                    pass
            # Clear session state
            st.session_state.converted_files = []
            st.session_state.conversion_status = {}
            st.rerun()
    
    with col2:
        st.caption(f"Storage: {MP3_STORAGE_DIR}/")

# Footer
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: gray;'>
        Made with Edge TTS | Current Voice: {selected_voice_name.split('(')[0].strip()}
    </div>
    """,
    unsafe_allow_html=True
)
