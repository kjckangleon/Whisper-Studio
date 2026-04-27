# 🎙️ Whisper Studio

A modern desktop GUI application for OpenAI Whisper built with Python
Tkinter + TkinterDnD2.\
It provides drag-and-drop transcription, real-time progress tracking,
GPU detection, and live subtitle-style output.

------------------------------------------------------------------------

## ✨ Features

-   Drag & drop audio/video files
-   Supports mp4, mkv, mov, avi, mp3, wav, m4a, flac, webm
-   OpenAI Whisper integration
-   Model selection: tiny, base, small, medium, large
-   Tasks: transcribe / translate
-   Output formats: srt, vtt, txt, tsv, json
-   Real-time progress bar with ETA
-   GPU detection (CUDA / Apple MPS / CPU fallback)
-   Live transcription segment output
-   Cancel processing anytime
-   Copy logs to clipboard
-   Modern dark-themed UI

------------------------------------------------------------------------

## 📦 Installation

### Clone repository

git clone https://github.com/kjckangleon/whisper-studio.git cd
whisper-studio

### Install dependencies

pip install openai-whisper pip install tkinterdnd2 pip install torch

------------------------------------------------------------------------

## ⚙️ FFmpeg Requirement

Windows: https://ffmpeg.org/download.html

Mac: brew install ffmpeg

Linux: sudo apt install ffmpeg

------------------------------------------------------------------------

## 🚀 Run Application

python main.py

------------------------------------------------------------------------

## 🧠 How It Works

-   Select or drag a media file
-   App detects GPU availability
-   Whisper runs via subprocess
-   Output is streamed live
-   Regex parser extracts timestamps
-   UI updates progress + ETA in real time

------------------------------------------------------------------------

## ⚡ Model Guide

tiny → fastest, lowest accuracy\
base → fast, basic accuracy\
small → balanced\
medium → recommended default\
large → slow but highest accuracy

------------------------------------------------------------------------

## 🖥️ GPU Support

CUDA / MPS / CPU fallback

------------------------------------------------------------------------

## 👨‍💻 Author

Karl

------------------------------------------------------------------------

## 📜 License

MIT License
