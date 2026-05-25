import streamlit as st
from streamlit_gsheets import GSheetsConnection
import time
import pandas as pd
import random  # 코드 최상단에 이 줄이 없다면 추가해주세요!

# 페이지 설정
st.set_page_config(page_title="RST 테스트", layout="centered")

# 구글 시트 연결 초기화 (내부적으로 무료 API 사용)
conn = st.connection("gsheets", type=GSheetsConnection)

# 세션 상태(State) 초기화 - 페이지 이동 및 데이터 임시 저장용
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

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
# 2. RST 안내 및 테스트 페이지 (60BPM, 130BPM, 무음 랜덤 버전)
# -------------------------------------------------------------------------
elif st.session_state.page == "rst_instr":
    st.title("🎵 RST (반응 시간 테스트) 안내")
    st.write("이제 테스트가 시작됩니다. 화면에 지시사항이 나오면 확인 후 아래 버튼을 최대한 빠르게 눌러주세요.")
    
    if st.button("테스트 시작"):
        # 🎲 세 가지 처치 중 하나를 무작위로 선택하여 세션에 저장
        # (참여자마다 독립적으로 랜덤 배정됩니다)
        treatments = ["60bpm", "130bpm", "silent"]
        st.session_state.current_treatment = random.choice(treatments)
        
        # 사후 설문조사 결과와 함께 저장하기 위해 미리 기록
        st.session_state.survey_data["treatment"] = st.session_state.current_treatment
        
        st.session_state.page = "rst_test"
        st.rerun()

elif st.session_state.page == "rst_test":
    st.title("🕹️ RST 진행 중")
    
    # 현재 배정된 처치 확인
    treatment = st.session_state.current_treatment
    
    # 1. 무음(silent) 처치일 때
    if treatment == "silent":
        st.subheader("🤫 현재 처치: 무음 환경")
        st.write("아무런 소리가 나지 않는 상태입니다. 준비가 되면 아래 '지금 클릭!' 버튼을 누르세요.")
    
    # 2. 음악(60bpm 또는 130bpm) 처치일 때
    else:
        st.subheader(f"🎵 현재 처치: {treatment} 음악 재생")
        st.write("아래 유튜브 비디오의 재생 버튼을 누르고 음악을 들으면서, 준비가 되면 '지금 클릭!' 버튼을 누르세요.")
        
        # 각 조건에 맞는 유튜브 링크 설정 (본인의 유튜브 링크로 대체하세요)
        if treatment == "60bpm":
            youtube_url = "https://youtu.be/ymJIXzvDvj4?si=54aZDLmc69OhedxV"
        elif treatment == "130bpm":
            youtube_url = "https://youtu.be/koTb8E5PpKM?si=Or_leA5j7EMgLeXP"
            
        st.video(youtube_url)
    
    st.write("---")
    
    # 시간 측정 시작 점 (페이지가 로드된 시점)
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()
        
    if st.button("🎯 지금 클릭!", use_container_width=True):
        end_time = time.time()
        # 소수점 3자리까지 초 단위 계산
        reaction_time = round(end_time - st.session_state.start_time, 3)
        st.session_state.survey_data["reaction_time"] = reaction_time
        
        # 임시 변수 삭제 후 이동
        del st.session_state.start_time
        st.session_state.page = "survey_post"
        st.rerun()

# -------------------------------------------------------------------------
# 3. 사후 설문조사 및 데이터 저장
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 사후 설문조사")
    st.write("테스트가 끝났습니다. 마지막 설문에 응답해주세요.")
    
    satisfaction = st.slider("방금 들은 음악은 어떠셨나요? (1: 매우 나쁨 ~ 5: 매우 좋음)", 1, 5, 3)
    feedback = st.text_area("기타 의견")
    
    if st.button("최종 제출"):
        st.session_state.survey_data["satisfaction"] = satisfaction
        st.session_state.survey_data["feedback"] = feedback
        
        # 구글 시트에 데이터 누적 저장 프로세스
        try:
            # 기존 데이터 읽기
            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([st.session_state.survey_data])
            updated_df = pd.concat([existing_data, new_row], ignore_index=True)
            
            # 구글 시트에 업데이트
            conn.update(worksheet="Sheet1", data=updated_df)
            st.session_state.page = "complete"
            st.rerun()
        except Exception as e:
            st.error("데이터 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

# -------------------------------------------------------------------------
# 4. 완료 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "complete":
    st.title("🎉 제출 완료")
    st.success("모든 테스트와 설문이 완료되었습니다. 참여해 주셔서 감사합니다!")