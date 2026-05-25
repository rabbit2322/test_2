import streamlit as st
import time
import pandas as pd
import random
import gspread

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
elif st.session_state.page == "rst_test":
    st.title("🕹️ RST 진행 중")
    
    treatment = st.session_state.current_treatment
    
    # 🌟 모든 조건에서 제목과 안내를 통일하여 화면 구조를 유지합니다.
    st.subheader(f"🎵 현재 테스트 환경에 진입했습니다.")
    st.write("아래 유튜브 비디오의 재생 버튼을 누르고, 준비가 되면 '지금 클릭!' 버튼을 누르세요.")
    
    # 무음 처치일 때도 '소리가 없는 유튜브 영상 링크'를 제공합니다.
    if treatment == "silent":
        # 예시: 10시간짜리 무음 영상 링크 (실제 존재하는 아무 무음 영상이나 넣으시면 됩니다)
        youtube_url = "https://youtu.be/T8BEuSlWXLs?si=YZ7JIy9GyR5ScR5S" 
    elif treatment == "60bpm":
        youtube_url = "https://youtu.be/ymJIXzvDvj4?si=54aZDLmc69OhedxV"
    elif treatment == "130bpm":
        youtube_url = "https://youtu.be/koTb8E5PpKM?si=Or_leA5j7EMgLeXP"
        
    # 🌟 무음이든 음성이든 무조건 st.video를 실행하므로 브라우저가 꼬이지 않습니다.
    st.video(youtube_url)
    
    st.write("---")
    
    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()
        
    if st.button("🎯 지금 클릭!", use_container_width=True):
        end_time = time.time()
        reaction_time = round(end_time - st.session_state.start_time, 3)
        st.session_state.survey_data["reaction_time"] = reaction_time
        
        del st.session_state.start_time
        st.session_state.page = "survey_post"
        st.rerun()

# -------------------------------------------------------------------------
# 3. 사후 설문조사 및 데이터 저장 (gspread 무료 우회 버전)
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 사후 설문조사")
    st.write("테스트가 끝났습니다. 마지막 설문에 응답해주세요.")
    
    satisfaction = st.slider("방금 들은 음악은 어떠셨나요? (1: 매우 나쁨 ~ 5: 매우 좋음)", 1, 5, 3)
    feedback = st.text_area("기타 의견")
    
    if st.button("최종 제출"):
        st.session_state.survey_data["satisfaction"] = satisfaction
        st.session_state.survey_data["feedback"] = feedback
        
        try:
            # 🌟 Streamlit Secrets에 저장된 주소로 구글 시트 연결
            sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
            
            # 링크 공유가 '편집자'로 되어 있다면 이 방식으로 바로 접근 가능합니다.
            gc = gspread.public_api()
            sh = gc.open_by_url(sheet_url)
            worksheet = sh.get_worksheet(0) # 첫 번째 시트 선택
            
            # 저장할 데이터를 순서대로 리스트로 변환
            # (구글 시트 첫 행에 적어둔 순서와 일치해야 합니다)
            row_data = [
                st.session_state.survey_data.get("name", ""),
                st.session_state.survey_data.get("age", ""),
                st.session_state.survey_data.get("gender", ""),
                st.session_state.survey_data.get("treatment", ""),
                st.session_state.survey_data.get("reaction_time", ""),
                st.session_state.survey_data.get("satisfaction", ""),
                st.session_state.survey_data.get("feedback", "")
            ]
            
            # 구글 시트 맨 아래에 데이터 추가
            worksheet.append_row(row_data)
            
            st.session_state.page = "complete"
            st.rerun()
            
        except Exception as e:
            st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")
            st.info("구글 시트가 '링크가 있는 모든 사용자에게 편집자 권한 부여'로 공유되어 있는지 다시 확인해 주세요.")
# -------------------------------------------------------------------------
# 4. 완료 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "complete":
    st.title("🎉 제출 완료")
    st.success("모든 테스트와 설문이 완료되었습니다. 참여해 주셔서 감사합니다!")