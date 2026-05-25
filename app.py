import streamlit as st
import time
import pandas as pd
import random
import numpy as np
import math
import io
import base64
import gspread

# 페이지 설정
st.set_page_config(page_title="RST 테스트", layout="centered")

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

# 📢 [순수 파이썬] scipy 없이 직접 WAV 바이너리를 빌드하는 함수
def generate_metronome_wav_bytes(bpm, duration_seconds=10):
    sample_rate = 22050
    total_samples = int(sample_rate * duration_seconds)
    
    # 1. 빈 오디오 신호 배열 생성
    audio_signal = np.zeros(total_samples, dtype=np.int16)
    
    # 2. 박자 및 간격 계산
    beat_interval = 60.0 / bpm
    click_duration = 0.05
    click_samples = int(sample_rate * click_duration)
    
    # 3. 0.05초짜리 880Hz 고음 클릭음 생성
    t_click = np.linspace(0, click_duration, click_samples, endpoint=False)
    # int16 범위(최대 32767)에 맞춰 소리 신호 증폭
    click_wave = (np.sin(2 * math.pi * 880 * t_click) * 16000).astype(np.int16)
    
    # 4. 루프를 돌며 지정된 간격마다 클릭음 심기
    current_time = 0.0
    while current_time < duration_seconds:
        start_idx = int(current_time * sample_rate)
        end_idx = start_idx + click_samples
        if end_idx < total_samples:
            audio_signal[start_idx:end_idx] = click_wave
        current_time += beat_interval
        
    # 5. 🌟 외부 라이브러리(scipy) 없이 WAV 파일 헤더를 수동으로 직접 작성
    num_channels = 1
    bytes_per_sample = 2
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    data_size = total_samples * bytes_per_sample
    
    header = bytearray()
    header.extend(b'RIFF')
    header.extend((36 + data_size).to_bytes(4, 'little'))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))
    header.extend((1).to_bytes(2, 'little')) # PCM 포맷
    header.extend((num_channels).to_bytes(2, 'little'))
    header.extend((sample_rate).to_bytes(4, 'little'))
    header.extend((byte_rate).to_bytes(4, 'little'))
    header.extend((block_align).to_bytes(2, 'little'))
    header.extend((bytes_per_sample * 8).to_bytes(2, 'little'))
    header.extend(b'data')
    header.extend((data_size).to_bytes(4, 'little'))
    
    # 헤더와 데이터 결합하여 완벽한 WAV 바이너리 데이터 반환
    return bytes(header) + audio_signal.tobytes()

# -------------------------------------------------------------------------
# 1. 사전 설문조사 페이지
# -------------------------------------------------------------------------
if st.session_state.page == "survey_pre":
    st.title("📋 사전 설문조사")
    st.write("테스트 진행 전 아래 설문에 응답해주세요.")
    
    name = st.text_input("참여자 이름/ID")
    age = st.number_input("나이", min_value=1, max_value=100, value=20)
    gender = st.selectbox("성별", ["선택 안 함", "남성", "여성"])