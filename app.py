import streamlit as st
import time
import pandas as pd
import random
import gspread

# 페이지 설정
st.set_page_config(page_title="RST 테스트", layout="centered")

# 세션 상태(State) 초기화
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
    
    if treatment == "silent":
        with st.container(key="silent_container"):
            st.subheader("🤫 현재 처치: 무음 환경")
            st.write("아무런 소리가 나지 않는 상태입니다. 준비가 되면 아래 '지금 클릭!' 버튼을 누르세요.")
    else:
        with st.container(key="music_container"):
            st.subheader(f"🎵 현재 처치: {treatment} 음악 재생")
            st.write("아래 유튜브 비디오의 재생 버튼을 누르고 음악을 들으면서 '지금 클릭!' 버튼을 누르세요.")
            
            # 본인의 유튜브 영상 링크 ID가 있다면 뒤에 넣어주세요. (예: dQw4w9WgXcQ)
            if treatment == "60bpm":
                youtube_url = "https://youtu.be/ymJIXzvDvj4?si=54aZDLmc69OhedxV"
            elif treatment == "130bpm":
                youtube_url = "https://youtu.be/koTb8E5PpKM?si=Or_leA5j7EMgLeXP"
                
            st.video(youtube_url, key=f"video_{treatment}")
    
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
    
    satisfaction = st.slider("방금 들은 음악은 어떠셨나요? (1: 매우 나쁨 ~ 5: 매우 좋음)", 1, 5, 3)
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
                
                # 🌟 st.session_data -> st.session_state 로 올바르게 수정 완료!
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