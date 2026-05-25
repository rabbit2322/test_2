import streamlit as st
import time
import random
import math
import base64
import gspread

# 페이지 설정
st.set_page_config(page_title="RST 테스트", layout="centered")

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

# 📢 [순수 파이썬 기본 기능] 어떤 외부 라이브러리도 쓰지 않고 WAV 바이너리를 만드는 함수
def generate_pure_metronome(bpm, duration_seconds=10):
    sample_rate = 22050
    num_channels = 1
    bytes_per_sample = 2  # 16-bit PCM
    
    beat_interval = 60.0 / bpm
    click_duration = 0.05
    click_samples = int(sample_rate * click_duration)
    total_samples = int(sample_rate * duration_seconds)
    
    # 순수 파이썬 리스트로 오디오 데이터 초기화 (기본값 무음 = 0)
    audio_data = [0] * total_samples
    
    # 880Hz 고음 클릭 사인파 생성
    click_wave = []
    for i in range(click_samples):
        t = i / sample_rate
        # 볼륨을 적절히 조절한 16비트 정수형 값 생성
        sample = int(math.sin(2 * math.pi * 880 * t) * 16000)
        click_wave.append(sample)
        
    # 일정 간격(BPM)마다 클릭음 심기
    current_time = 0.0
    while current_time < duration_seconds:
        start_idx = int(current_time * sample_rate)
        for i in range(click_samples):
            idx = start_idx + i
            if idx < total_samples:
                audio_data[idx] = click_wave[i]
        current_time += beat_interval
        
    # 16비트 정수형 리스트를 바이트 데이터로 변환
    data_bytes = bytearray()
    for sample in audio_data:
        # 2바이트 signed 리틀 엔디안 변환
        data_bytes.extend(sample.to_bytes(2, byteorder='little', signed=True))
        
    # WAV 헤더 수동 작성
    data_size = len(data_bytes)
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    
    header = bytearray()
    header.extend(b'RIFF')
    header.extend((36 + data_size).to_bytes(4, 'little'))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))
    header.extend((1).to_bytes(2, 'little'))
    header.extend((num_channels).to_bytes(2, 'little'))
    header.extend((sample_rate).to_bytes(4, 'little'))
    header.extend((byte_rate).to_bytes(4, 'little'))
    header.extend((block_align).to_bytes(2, 'little'))
    header.extend((bytes_per_sample * 8).to_bytes(2, 'little'))
    header.extend(b'data')
    header.extend((data_size).to_bytes(4, 'little'))
    
    return bytes(header + data_bytes)

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
# 2. RST 안내 및 테스트 페이지
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
    
    # 🌟 각 처치(Treatment)별로 완전히 독립된 UI 컨테이너와 고유 Key를 제공하여 removeChild 에러 해결
    if treatment == "silent":
        st.subheader("🤫 현재 처치: 무음 환경")
        st.write("아무런 소리가 나지 않는 상태입니다. 준비가 되면 아래 '지금 클릭!' 버튼을 누르세요.")
    else:
        st.subheader(f"⏱️ 현재 처치: {treatment} 메트로놈 무한 재생 중")
        st.write("메트로놈 소리가 무한 반복됩니다. 박자를 들으면서 준비가 되면 '지금 클릭!' 버튼을 누르세요.")
        
        bpm_value = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_value, duration_seconds=10)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        # 🌟 HTML 컴포넌트가 꼬이지 않도록 처치명을 ID로 박아 캐싱 에러 방지
        audio_html = f"""
            <audio autoplay loop id="audio_{treatment}" style="width: 100%;">
                <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    
    st.write("---")
    
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()
        
    # 고유 키값을 부여하여 버튼이 씹히거나 브라우저가 폭주하는 현상 제어
    if st.button("🎯 지금 클릭!", use_container_width=True, key=f"btn_click_{treatment}"):
        end_time = time.time()
        reaction_time = round(end_time - st.session_state.start_time, 3)
        st.session_state.survey_data["reaction_time"] = reaction_time
        
        if "start_time" in st.session_state:
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