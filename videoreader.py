import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
from googletrans import Translator
import webvtt
import whisper
import os
import tempfile

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

user_input = st.text_input("Enter the full link or the video number (e.g., 1123503)")

if user_input:
    if user_input.isdigit():
        url = f"https://hsex.icu/video-{user_input}.htm"
    else:
        url = user_input
    
    try:
        info = get_video_info(url)
        video_url = info['url']  # Direct video URL
        title = info['title']
        author = info.get('uploader', info.get('channel', 'Unknown'))
        
        st.write(f"Title: {title}")
        st.write(f"Author: {author}")
        st.write(f"Categorized under author: {author}")
        
        # Stream the video
        st.video(video_url)
        
        # Provide direct download link for external recorders
        st.markdown(f"[Download video directly (MP4)]({video_url})")
        
        # Generate and add captions
        if st.button("Generate Auto-Translated English Captions"):
            with st.spinner("Processing video for captions... This may take a while."):
                # Create temporary files
                with tempfile.TemporaryDirectory() as tmpdir:
                    video_path = os.path.join(tmpdir, "temp.mp4")
                    audio_path = os.path.join(tmpdir, "temp.wav")
                    vtt_path = os.path.join(tmpdir, "captions.vtt")
                    
                    # Download video
                    download_video(url, video_path)
                    
                    # Extract audio
                    video = VideoFileClip(video_path)
                    audio = video.audio
                    audio.write_audiofile(audio_path)
                    
                    # Transcribe with Whisper
                    model = whisper.load_model("base")
                    result = model.transcribe(audio_path)
                    
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
            
        # Download in .avi format
        if st.button("Download as .AVI"):
            with st.spinner("Converting and preparing download..."):
                with tempfile.TemporaryDirectory() as tmpdir:
                    video_path = os.path.join(tmpdir, "temp.mp4")
                    avi_path = os.path.join(tmpdir, "video.avi")
                    
                    download_video(url, video_path)
                    
                    video = VideoFileClip(video_path)
                    video.write_videofile(avi_path, codec='libxvid')  # AVI codec
                    
                    with open(avi_path, "rb") as f:
                        st.download_button("Download AVI", f, file_name="video.avi")
    
    except Exception as e:
        st.error(f"Error processing video: {str(e)}")
        st.info("Make sure yt-dlp supports this site. If not, you may need to update yt-dlp or find another way to extract the video URL.")
