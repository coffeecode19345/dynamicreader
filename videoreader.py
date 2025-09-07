import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
from googletrans import Translator
import webvtt
import whisper
import os
import tempfile
import sqlite3
import json
from datetime import datetime
import traceback  # For better error handling

# Database setup
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

# Function to extract video info and direct URL
def get_video_info(url):
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info

# Function to download video
def download_video(url, output_path):
    ydl_opts = {'outtmpl': output_path, 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# Main app
st.title("Video Streamer with Advanced Features")

init_db()  # Initialize database

user_input = st.text_input("Enter the full link or the video number (e.g., 1123503)")

if user_input:
    save_to_json_backup(user_input)  # Save input to JSON backup
    
    if user_input.isdigit():
        number = user_input
        url = f"https://hsex.icu/video-{user_input}.htm"
    else:
        url = user_input
        # Extract number from URL if possible
        import re
        match = re.search(r'video-(\d+)\.htm', url)
        number = match.group(1) if match else "unknown"
    
    try:
        info = get_video_info(url)
        video_url = info['url']  # Direct video URL
        title = info['title']
        author = info.get('uploader', info.get('channel', 'Unknown'))
        
        st.write(f"Title: {title}")
        st.write(f"Author: {author}")
        st.write(f"Categorized under author: {author}")
        
        # Store in database
        store_in_db(number, url, author)
        
        # Stream the video
        st.video(video_url)
        
        # Provide direct download link for external recorders
        st.markdown(f"[Download video directly (MP4)]({video_url})")
        
        # Generate and add captions
        if st.button("Generate Auto-Translated English Captions"):
            with st.spinner("Processing video for captions... This may take a while."):
                try:
                    # Create temporary files in /tmp for cloud compatibility
                    with tempfile.TemporaryDirectory(dir="/tmp") as tmpdir:
                        video_path = os.path.join(tmpdir, "temp.mp4")
                        audio_path = os.path.join(tmpdir, "temp.wav")
                        vtt_path = os.path.join(tmpdir, "captions.vtt")
                        
                        # Download video
                        download_video(url, video_path)
                        
                        # Extract audio
                        video = VideoFileClip(video_path)
                        audio = video.audio
                        audio.write_audiofile(audio_path)
                        
                        # Transcribe with Whisper - load model here to avoid startup crash
                        model = whisper.load_model("tiny")  # Use "tiny" for lower memory/ faster on cloud
                        result = model.transcribe(audio_path, fp16=False)  # Force CPU mode
                        
                        # Translate segments
                        translator = Translator()
                        vtt = webvtt.WebVTT()
                        for segment in result['segments']:
                            start = webvtt.from_seconds(segment['start'])
                            end = webvtt.from_seconds(segment['end'])
                            text = segment['text']
                            # Translate if not English (Whisper detects language)
                            if result.get('language', 'en') != 'en':
                                translated = translator.translate(text, dest='en').text
                            else:
                                translated = text
                            caption = webvtt.Caption(start, end, translated)
                            vtt.captions.append(caption)
                        
                        vtt.save(vtt_path)
                        
                        # Display video with captions
                        st.video(video_url, subtitles=vtt_path)
                except Exception as e:
                    st.error(f"Error generating captions: {str(e)}")
                    st.info("Check if FFmpeg is installed and site is supported. Full traceback: {traceback.format_exc()}")
            
        # Download in .avi format
        if st.button("Download as .AVI"):
            with st.spinner("Converting and preparing download..."):
                try:
                    # Create temporary files in /tmp
                    with tempfile.TemporaryDirectory(dir="/tmp") as tmpdir:
                        video_path = os.path.join(tmpdir, "temp.mp4")
                        avi_path = os.path.join(tmpdir, "video.avi")
                        
                        download_video(url, video_path)
                        
                        video = VideoFileClip(video_path)
                        video.write_videofile(avi_path, codec='libxvid')  # AVI codec
                        
                        with open(avi_path, "rb") as f:
                            st.download_button("Download AVI", f, file_name="video.avi")
                except Exception as e:
                    st.error(f"Error converting to AVI: {str(e)}")
                    st.info("Ensure FFmpeg is available. Full traceback: {traceback.format_exc()}")
    
    except Exception as e:
        st.error(f"Error processing video: {str(e)}")
        st.info("Make sure yt-dlp supports this site. If not, you may need to update yt-dlp or find another way to extract the video URL. Full traceback: {traceback.format_exc()}")

# Display stored videos (optional, for viewing the dataset)
if st.button("View Stored Videos"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM videos")
    rows = c.fetchall()
    conn.close()
    if rows:
        st.write("Stored Videos:")
        for row in rows:
            st.write(row)
    else:
        st.write("No videos stored yet.")

# Display JSON backup (optional)
if st.button("View Input Backup"):
    backups = load_json_backup()
    if backups:
        st.write("Input Backups:")
        for backup in backups:
            st.write(backup)
    else:
        st.write("No backups yet.")
