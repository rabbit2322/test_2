import streamlit as st
import time
import random
import math
import base64
import gspread

# 페이지 설정
st.set_page_config(page_title="RSPAN 작업기억 테스트", layout="centered")

# -------------------------------------------------------------------------
# 실험용 자음 리스트 및 테스트 문장 풀(Pool) 정의
# -------------------------------------------------------------------------
LETTERS_POOL = ["B", "F", "H", "J", "K", "L", "M", "Q", "R", "X"]

SENTENCE_POOL = [
    {"text": "경찰관은 짐의 면허증과 자동차 등록증을 보여달라고 요구했다.", "correct": True},
    {"text": "엄격한 채식주의자인 제니퍼는 치킨이나 소고기를 전혀 먹지 않는다.", "correct": True},
    {"text": "낸시의 주방은 목수개미와 잔디깎이 기계로 가득 차 있었다.", "correct": False},  # 잔디깎이 기계가 주방에?
    {"text": "마크는 세탁기에 세제를 너무 많이 넣어서 거품이 넘쳐흘렀다.", "correct": True},
    {"text": "서커스 천막은 수많은 동물들과 광대들, 손톱깎이로 붐볐다.", "correct": False}, # 손톱깎이로 붐빌 수 없음
    {"text": "곰은 꿀을 들고 가는 국립공원 산림경비대원의 뒤를 쫓아갔다.", "correct": True},
    {"text": "존스 씨는 아들에게 고양이에게 물을 주고 잔디를 깎으라고 말했다.", "correct": False}, # 고양이에게 물을 주는게 아니라 식물
    {"text": "신부는 결혼식 도중에 감동을 받아 눈물을 흘렸다.", "correct": True},
    {"text": "음주 운전자는 통제력을 잃고 도로 표지판을 들이받고 체포되었다.", "correct": True},
    {"text": "도둑은 창문을 깨고 조용히 헤드폰 안으로 기어 들어갔다.", "correct": False}, # 헤드폰 안으로 들어갈 수 없음
]

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

# 📢 [순수 파이썬 기본 기능] 어떤 외부 라이브러리도 쓰지 않고 메트로놈 WAV 바이너리를 만드는 함수
def generate_pure_metronome(bpm, duration_seconds=15):
    sample_rate = 22050
    num_channels = 1
    bytes_per_sample = 2  # 16-bit PCM
    
    beat_interval = 60.0 / bpm
    click_duration = 0.05
    click_samples = int(sample_rate * click_duration)
    total_samples = int(sample_rate * duration_seconds)
    
    audio_data = [0] * total_samples
    
    # 880Hz 고음 클릭 사인파 생성
    click_wave = []
    for i in range(click_samples):
        t = i / sample_rate
        sample = int(math.sin(2 * math.pi * 880 * t) * 16000)
        click_wave.append(sample)
        
    current_time = 0.0
    while current_time < duration_seconds:
        start_idx = int(current_time * sample_rate)
        for i in range(click_samples):
            idx = start_idx + i
            if idx < total_samples:
                audio_data[idx] = click_wave[i]
        current_time += beat_interval
        
    data_bytes = bytearray()
    for sample in audio_data:
        data_bytes.extend(sample.to_bytes(2, byteorder='little', signed=True))
        
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
            st.session_state.page = "rspan_instr"
            st.rerun()
        else:
            st.error("이름 또는 ID를 입력해주세요.")

# -------------------------------------------------------------------------
# 2. RSPAN 안내 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_instr":
    st.title("🎵 Reading Span Task (RSPAN) 안내")
    st.write("""
    본 검사는 배경 음이 깔린 상태에서 **문장 판단**과 **글자 기억**을 동시에 수행하는 작업 기억 검사입니다.
    
    1. 화면에 문장이 나타나면, 읽어보고 문맥상 말이 되는지 **[O]**, 말이 안 되는지 **[X]** 빠르게 선택합니다.
    2. 문장 판단 직후, 화면에 **영어 자음 한 글자**가 1초 동안 나타났다 사라집니다. 이 글자를 순서대로 기억하세요.
    3. 몇 개의 문장과 글자가 반복된 후(**한 세트 완료**), 방금 보았던 글자들을 **나온 순서대로** 마우스로 클릭하여 맞추시면 됩니다.
    """)
    st.info("⚠️ 주의: 메트로놈 소리는 검사가 완전히 끝날 때까지 무한 반복 재생됩니다.")
    
    if st.button("테스트 시작"):
        # 실험 환경 처치 랜덤 배정 (무음, 60bpm, 130bpm)
        treatments = ["60bpm", "130bpm", "silent"]
        st.session_state.current_treatment = random.choice(treatments)
        st.session_state.survey_data["treatment"] = st.session_state.current_treatment
        
        # RSPAN 변수 초기화 (여기서는 표준 축약형으로 1세트당 3개의 문제를 푸는 세트 구성)
        st.session_state.set_size = 3
        st.session_state.current_step = 0 # 세트 내 현재 진행 단계 (0, 1, 2)
        st.session_state.sub_stage = "sentence" # sentence -> letter 전환 제어용
        
        # 이번 세트에 쓰일 랜덤 문장 및 글자 추출
        st.session_state.selected_sentences = random.sample(SENTENCE_POOL, st.session_state.set_size)
        st.session_state.selected_letters = random.sample(LETTERS_POOL, st.session_state.set_size)
        
        # 정답 및 반응 데이터 기록용
        st.session_state.user_sentence_answers = []
        st.session_state.user_recalled_letters = []
        st.session_state.sentence_start_time = 0.0
        st.session_state.total_sentence_rt = 0.0
        
        st.session_state.page = "rspan_test"
        st.rerun()

# -------------------------------------------------------------------------
# 3. RSPAN 테스트 본 페이지 (문장 판단 -> 알파벳 노출 반복 루프)
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_test":
    treatment = st.session_state.current_treatment
    st.title(f"🕹️ RSPAN 테스트 진행 중 ({treatment})")
    
    # [오디오 주입] 무음이 아니면 메트로놈 루프 무한 재생
    if treatment != "silent":
        bpm_value = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_value, duration_seconds=15)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
            <audio autoplay loop id="audio_{treatment}">
                <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)

    # 현재 단계 인덱스
    idx = st.session_state.current_step
    
    # (A) 문장 판단 서브 단계
    if st.session_state.sub_stage == "sentence":
        st.subheader(f"⏱️ 과제 {idx + 1} : 문장 진위 판단")
        current_sentence = st.session_state.selected_sentences[idx]["text"]
        
        st.info(f"**[문장]** {current_sentence}")
        st.write("위 문장은 논리적으로 말이 되는 문장입니까?")
        
        # 반응시간 측정 시작
        if st.session_state.sentence_start_time == 0.0:
            st.session_state.sentence_start_time = time.time()
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⭕ 말이 된다 (True)", use_container_width=True, key=f"true_{idx}"):
                rt = time.time() - st.session_state.sentence_start_time
                st.session_state.total_sentence_rt += rt
                is_correct = st.session_state.selected_sentences[idx]["correct"] == True
                st.session_state.user_sentence_answers.append(is_correct)
                
                # 다음 서브 단계(글자 노출)로 전환
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()
                
        with col2:
            if st.button("❌ 말이 안 된다 (False)", use_width=True, key=f"false_{idx}"):
                rt = time.time() - st.session_state.sentence_start_time
                st.session_state.total_sentence_rt += rt
                is_correct = st.session_state.selected_sentences[idx]["correct"] == False
                st.session_state.user_sentence_answers.append(is_correct)
                
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()

    # (B) 글자 노출 서브 단계 (1초 후 자동으로 화면 전환 효과 구현)
    elif st.session_state.sub_stage == "letter":
        st.subheader("💡 기억하세요!")
        target_letter = st.session_state.selected_letters[idx]
        
        # 중앙에 거대하고 굵게 글자 표시
        st.markdown(f"<h1 style='text-align: center; font-size: 100px; color: #FF4B4B;'>{target_letter}</h1>", unsafe_allow_html=True)
        
        # 1초 타임아웃 대기 후 상태 업데이트
        time.sleep(1.0)
        
        # 세트 내 문장이 더 남았으면 다음 문제로, 다 끝났으면 회상(Recall) 페이지로 이동
        if idx + 1 < st.session_state.set_size:
            st.session_state.current_step += 1
            st.session_state.sub_stage = "sentence"
        else:
            st.session_state.page = "rspan_recall"
        st.rerun()

# -------------------------------------------------------------------------
# 4. RSPAN 회상(Recall) 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_recall":
    st.title("🧠 글자 회상 단계 (Recall)")
    st.write("방금 보았던 글자들을 **나왔던 순서대로 똑같이** 선택해 주세요.")
    
    # 현재 선택한 글자들 시각화
    st.warning(f"내가 입력한 순서: {' ➔ '.join(st.session_state.user_recalled_letters)}")
    
    # 10개의 자음 패드 매트릭스 생성 (3열 배치)
    cols = st.columns(4)
    for i, letter in enumerate(LETTERS_POOL):
        with cols[i % 4]:
            # 이미 고른 글자는 비활성화 느낌을 주거나 중복 방지 처리 가능
            if st.button(letter, use_container_width=True, key=f"pad_{letter}"):
                st.session_state.user_recalled_letters.append(letter)
                st.rerun()
                
    st.write("---")
    col_clear, col_submit = st.columns(2)
    with col_clear:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.user_recalled_letters = []
            st.rerun()
            
    with col_submit:
        if st.button("정답 제출하기 ➔", use_container_width=True, type="primary"):
            # 채점 진행
            correct_letters = st.session_state.selected_letters
            user_letters = st.session_state.user_recalled_letters
            
            # 1. 글자 완벽 매칭 스코어 (순서와 글자가 완벽히 맞은 개수)
            match_count = 0
            for u, c in zip(user_letters, correct_letters):
                if u == c:
                    match_count += 1
            
            # 2. 문장 진위 판단 정확도 계산
            sentence_accuracy = round(sum(st.session_state.user_sentence_answers) / st.session_state.set_size * 100, 1)
            # 평균 문장 반응시간
            avg_sentence_rt = round(st.session_state.total_sentence_rt / st.session_state.set_size, 3)
            
            # 최종 분석 결과 세션에 보관
            st.session_state.survey_data["rspan_score"] = f"{match_count}/{st.session_state.set_size}"
            st.session_state.survey_data["sentence_accuracy"] = f"{sentence_accuracy}%"
            st.session_state.survey_data["reaction_time"] = avg_sentence_rt
            
            st.session_state.page = "survey_post"
            st.rerun()

# -------------------------------------------------------------------------
# 5. 사후 설문조사 및 데이터 저장
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 사후 설문조사")
    st.write("검사가 종료되었습니다. 마지막 설문에 응답해주세요.")
    
    satisfaction = st.slider("방금 진행한 테스트 환경의 집중도는 어떠셨나요? (1: 매우 산만함 ~ 5: 매우 집중됨)", 1, 5, 3)
    feedback = st.text_area("테스트 중 느낀 점이나 특이사항을 적어주세요.")
    
    if st.button("최종 데이터 서버 제출"):
        st.session_state.survey_data["satisfaction"] = satisfaction
        st.session_state.survey_data["feedback"] = feedback
        
        with st.spinner("구글 시트에 실험 결과를 연산하여 영구 저장 중입니다..."):
            try:
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                
                gc = gspread.public_api()
                sh = gc.open_by_url(sheet_url)
                worksheet = sh.get_worksheet(0)
                
                # 컬럼 순서 일치: 이름, 나이, 성별, 처치조건, 글자맞춘개수, 문장정확도, 평균문장반응시간, 만족도, 피드백
                row_data = [
                    st.session_state.survey_data.get("name", ""),
                    st.session_state.survey_data.get("age", ""),
                    st.session_state.survey_data.get("gender", ""),
                    st.session_state.survey_data.get("treatment", ""),
                    st.session_state.survey_data.get("rspan_score", ""),
                    st.session_state.survey_data.get("sentence_accuracy", ""),
                    st.session_state.survey_data.get("reaction_time", ""),
                    st.session_state.survey_data.get("satisfaction", ""),
                    st.session_state.survey_data.get("feedback", "")
                ]
                
                worksheet.append_row(row_data)
                st.session_state.page = "complete"
                st.rerun()
                
            except Exception as e:
                st.error(f"구글 시트 클라우드 저장 실패: {e}")
                st.info("실험 데이터 유실 방지용 로컬 백업 코드:")
                st.code(str(st.session_state.survey_data))

# -------------------------------------------------------------------------
# 6. 완료 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "complete":
    st.title("🎉 모든 실험 완료")
    st.success("RSPAN 검사와 설문 데이터가 정상적으로 전송되었습니다. 참여해 주셔서 대단히 감사합니다!")
    
    # 결과 요약 피드백 창
    st.balloons()
    st.subheader("📊 나의 실험 요약 결과")
    st.json(st.session_state.survey_data)