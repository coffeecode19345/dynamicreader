import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from googletrans import Translator
import webvtt
import whisper
import os
import tempfile
import sqlite3
import json
from datetime import datetime
import traceback  # For better error handling

# -----------------------------
# Helper to format seconds → VTT
def seconds_to_vtt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
# -----------------------------

DB_FILE = "videos.db"
JSON_BACKUP = "inputs.json"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS videos
                 (number TEXT UNIQUE, link TEXT, author TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

def store_in_db(number, link, author):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute("INSERT OR REPLACE INTO videos (number, link, author, timestamp) VALUES (?, ?, ?, ?)",
              (number, link, author, timestamp))
    conn.commit()
    conn.close()

def load_json_backup():
    if os.path.exists(JSON_BACKUP):
        with open(JSON_BACKUP, 'r') as f:
            return json.load(f)
    return []

def save_to_json_backup(input_value):
    backups = load_json_backup()
    backups.append({"input": input_value, "timestamp": datetime.now().isoformat()})
    with open(JSON_BACKUP, 'w') as f:
        json.dump(backups, f)

def get_video_info(url):
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_video(url, output_path):
    ydl_opts = {'outtmpl': output_path, 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# -----------------------------
# Streamlit app
# -----------------------------
st.title("Video Streamer with Advanced Features")
init_db()

user_input = st.text_input("Enter the full link or the video number (e.g., 1123503)")

if user_input:
    save_to_json_backup(user_input)

    if user_input.isdigit():
        number = user_input
        url = f"https://hsex.icu/video-{user_input}.htm"
    else:
        url = user_input
        import re
        match = re.search(r'video-(\d+)\.htm', url)
        number = match.group(1) if match else "unknown"

    try:
        info = get_video_info(url)
        video_url = info['url']
        title = info['title']
        author = info.get('uploader', info.get('channel', 'Unknown'))

        st.write(f"**Title:** {title}")
        st.write(f"**Author:** {author}")

        store_in_db(number, url, author)

        st.video(video_url)
        st.markdown(f"[⬇️ Download video directly (MP4)]({video_url})")

        if st.button("Generate Auto-Translated English Captions"):
            with st.spinner("Processing video for captions... This may take a while."):
                try:
                    with tempfile.TemporaryDirectory(dir="/tmp") as tmpdir:
                        video_path = os.path.join(tmpdir, "temp.mp4")
                        audio_path = os.path.join(tmpdir, "temp.wav")
                        vtt_path = os.path.join(tmpdir, "captions.vtt")

                        download_video(url, video_path)

                        # Extract audio
                        video = VideoFileClip(video_path)
                        video.audio.write_audiofile(audio_path)

                        # Whisper transcription
                        model = whisper.load_model("tiny")
                        result = model.transcribe(audio_path, fp16=False)

                        translator = Translator()
                        vtt_content = "WEBVTT\n\n"
                        for seg in result['segments']:
                            start = seconds_to_vtt_time(seg['start'])
                            end = seconds_to_vtt_time(seg['end'])
                            text = seg['text']
                            if result.get('language', 'en') != 'en':
                                text = translator.translate(text, dest='en').text
                            vtt_content += f"{start} --> {end}\n{text}\n\n"

                        with open(vtt_path, "w") as f:
                            f.write(vtt_content)

                        st.success("✅ Captions generated and saved to VTT.")
                        st.download_button("Download Captions (VTT)", open(vtt_path, "rb"), "captions.vtt")
                except Exception:
                    st.error("Error generating captions.")
                    st.info(f"Full traceback:\n{traceback.format_exc()}")

        if st.button("Download as .AVI"):
            with st.spinner("Converting to AVI..."):
                try:
                    with tempfile.TemporaryDirectory(dir="/tmp") as tmpdir:
                        video_path = os.path.join(tmpdir, "temp.mp4")
                        avi_path = os.path.join(tmpdir, "video.avi")
                        download_video(url, video_path)
                        video = VideoFileClip(video_path)
                        video.write_videofile(avi_path, codec='libxvid')
                        st.download_button("Download AVI", open(avi_path, "rb"), file_name="video.avi")
                except Exception:
                    st.error("Error converting to AVI.")
                    st.info(f"Full traceback:\n{traceback.format_exc()}")

    except Exception:
        st.error("Error processing video.")
        st.info(f"Full traceback:\n{traceback.format_exc()}")

# Show stored videos
if st.button("View Stored Videos"):
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT * FROM videos").fetchall()
    conn.close()
    if rows:
        for row in rows:
            st.write(row)
    else:
        st.write("No videos stored yet.")

# Show JSON backups
if st.button("View Input Backup"):
    backups = load_json_backup()
    st.write(backups if backups else "No backups yet.")
