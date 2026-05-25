import streamlit as st
import time
import pandas as pd
import random
import numpy as np
import math
import io
import scipy.io.wavfile as wavfile
import base64
import gspread

# 페이지 설정
st.set_page_config(page_title="RST 테스트", layout="centered")

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

# 📢 [순수 파이썬] 메트로놈 소리 실시간 생성 함수
def generate_metronome_sound(bpm, duration_seconds=10):
    sample_rate = 22050  # 오디오 샘플링 레이트
    total_samples = int(sample_rate * duration_seconds)
    t = np.linspace(0, duration_seconds, total_samples, endpoint=False)
    
    # 빈 오디오 배열 생성
    audio_signal = np.zeros(total_samples)
    
    # BPM에 따른 1비트당 시간 간격 (60bpm = 1초에 한 번, 130bpm = 약 0.46초에 한 번)
    beat_interval = 60.0 / bpm
    click_duration = 0.05  # "삑" 소리가 날 길이 (0.05초)
    click_samples = int(sample_rate * click_duration)
    
    # 0.05초짜리 880Hz(고음 피치) 사인파 클릭음 생성
    t_click = np.linspace(0, click_duration, click_samples, endpoint=False)
    click_wave = np.sin(2 * math.pi * 880 * t_click) * 0.5  # 볼륨 조절
    
    # 지정된 간격마다 클릭음 심기
    current_time = 0.0
    while current_time < duration_seconds:
        start_idx = int(current_time * sample_rate)
        end_idx = start_idx + click_samples
        if end_idx < total_samples:
            audio_signal[start_idx:end_idx] = click_wave
        current_time += beat_interval
        
    return audio_signal, sample_rate

# -------------------------------------------------------------------------
# 1. 사전 설문조사 페이지
# -------------------------------------------------------------------------
if st.session_state.page == "survey_pre":
    st.title("📋 사전 설문조사")
    st.write("테스트 진행 전 아래 설문에 응답해주세요.")
    
    name = st.text_input("참여자 이름/ID")
    age = st.number_input("나이", min_value=1, max_value=100, value=20)
    gender = st.selectbox("성별", ["선택 안 함", "남성", "여성"])
    
    if st.button("다음 단계로 이동"):
        if name:
            st.session_state.survey_data["name"] = name
            st.session_state.survey_data["age"] = age
            st.session_state.survey_data["gender"] = gender
            st.session_state.page = "rst_instr"
            st.rerun()
        else:
            st.error("이름 또는 ID를 입력해주세요.")

# -------------------------------------------------------------------------
# 2. RST 안내 및 테스트 페이지 (메트로놈 무한 루프 적용)
# -------------------------------------------------------------------------
elif st.session_state.page == "rst_instr":
    st.title("🎵 RST (반응 시간 테스트) 안내")
    st.write("이제 테스트가 시작됩니다. 화면에 지시사항이 나오면 확인 후 아래 버튼을 최대한 빠르게 눌러주세요.")
    
    if st.button("테스트 시작"):
        treatments = ["60bpm", "130bpm", "silent"]
        st.session_state.current_treatment = random.choice(treatments)
        st.session_state.survey_data["treatment"] = st.session_state.current_treatment
        st.session_state.page = "rst_test"
        st.rerun()

elif st.session_state.page == "rst_test":
    st.title("🕹️ RST 진행 중")
    treatment = st.session_state.current_treatment
    
    if treatment == "silent":
        with st.container(key="silent_container"):
            st.subheader("🤫 현재 처치: 무음 환경")
            st.write("아무런 소리가 나지 않는 상태입니다. 준비가 되면 아래 '지금 클릭!' 버튼을 누르세요.")
    else:
        with st.container(key="music_container"):
            st.subheader(f"⏱️ 현재 처치: {treatment} 메트로놈 무한 재생 중")
            st.write("메트로놈 소리가 무한 반복됩니다. 박자를 들으면서 준비가 되면 '지금 클릭!' 버튼을 누르세요.")
            
            # 1. 파이썬 코드로 10초 분량의 기본 메트로놈 음원 생성
            bpm_value = 60 if treatment == "60bpm" else 130
            audio_data, sample_rate = generate_metronome_sound(bpm_value, duration_seconds=10)
            
            # 2. 오디오 데이터를 바이너리로 변환 (브라우저 호환성을 위해 int16 변환)
            virtual_file = io.BytesIO()
            audio_int16 = (audio_data * 32767).astype(np.int16)
            wavfile.write(virtual_file, sample_rate, audio_int16)
            audio_bytes = virtual_file.getvalue()
            
            # 3. HTML5 audio 태그에 'loop'와 'autoplay' 속성을 넣어 무한 반복 플레이어 심기
            audio_base64 = base64.b64encode(audio_bytes).decode()
            audio_html = f"""
                <audio autoplay loop style="width: 100%;">
                    <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                    Your browser does not support the audio element.
                </audio>
            """
            st.markdown(audio_html, unsafe_allow_html=True)
    
    st.write("---")
    
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()
        
    if st.button("🎯 지금 클릭!", use_container_width=True, key="click_btn"):
        end_time = time.time()
        reaction_time = round(end_time - st.session_state.start_time, 3)
        st.session_state.survey_data["reaction_time"] = reaction_time
        
        del st.session_state.start_time
        st.session_state.page = "survey_post"
        st.rerun()

# -------------------------------------------------------------------------
# 3. 사후 설문조사 및 데이터 저장
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 사후 설문조사")
    st.write("테스트가 끝났습니다. 마지막 설문에 응답해주세요.")
    
    satisfaction = st.slider("방금 들은 환경은 어떠셨나요? (1: 매우 나쁨 ~ 5: 매우 좋음)", 1, 5, 3)
    feedback = st.text_area("기타 의견")
    
    if st.button("최종 제출"):
        st.session_state.survey_data["satisfaction"] = satisfaction
        st.session_state.survey_data["feedback"] = feedback
        
        with st.spinner("구글 시트에 데이터를 안전하게 저장 중입니다..."):
            try:
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                
                gc = gspread.public_api()
                sh = gc.open_by_url(sheet_url)
                worksheet = sh.get_worksheet(0)
                
                row_data = [
                    st.session_state.survey_data.get("name", ""),
                    st.session_state.survey_data.get("age", ""),
                    st.session_state.survey_data.get("gender", ""),
                    st.session_state.survey_data.get("treatment", ""),
                    st.session_state.survey_data.get("reaction_time", ""),
                    st.session_state.survey_data.get("satisfaction", ""),
                    st.session_state.survey_data.get("feedback", "")
                ]
                
                worksheet.append_row(row_data)
                st.session_state.page = "complete"
                st.rerun()
                
            except Exception as e:
                st.error(f"구글 시트 저장 실패: {e}")
                st.info("실험 데이터 백업:")
                st.code(str(st.session_state.survey_data))

# -------------------------------------------------------------------------
# 4. 완료 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "complete":
    st.title("🎉 제출 완료")
    st.success("모든 테스트와 설문이 완료되었습니다. 참여해 주셔서 감사합니다!")