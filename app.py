import streamlit as st
import time
import random
import math
import base64
import gspread
import hashlib

# 페이지 설정
st.set_page_config(page_title="RSPAN 작업기억 테스트", layout="centered")

# -------------------------------------------------------------------------
# [요구사항 2] RSPAN 표준 문장 데이터 풀 (총 10개 문장 고정 제공)
# -------------------------------------------------------------------------
RSPAN_RAW_SENTENCES = [
    {"template": "그 작가는 글을 다 쓸 때까지 짧고 빠른 스퍼트로 자신의 {책|악어}을 집필했다."},
    {"template": "경찰관은 불법 유턴을 한 운전자에게 다가가 {면허증|시계탑}과 등록증을 요구했다."},
    {"template": "엄격한 채식주의자인 제니퍼는 회식 자리에서 {치킨|자동차}이나 소고기를 전혀 먹지 않았다."},
    {"template": "마크는 세탁기에 세제를 너무 많이 넣어서 {거품|스마트폰}이 사방으로 넘쳐흘렀다."},
    {"template": "음주 운전자는 통제력을 잃고 도로 {표지판|노트북}을 들이받은 후 체포되었다."},
    {"template": "신부는 결혼식 도중 부모님의 편지를 듣고 감동을 받아 {눈물|손톱깎이}을 흘렸다."},
    {"template": "캠핑장에 나타난 거대한 곰은 맛있는 냄새를 풍기는 {바비큐|잔디깎이}를 향해 걸어왔다."},
    {"template": "지하철 연착으로 인해 출근 시간 대의 플랫폼은 수많은 {직장인|열대과일}들로 붐볐다."},
    {"template": "할머니는 추운 겨울날 거실에 모여 앉아 따뜻한 {목도리|헤드폰}를 뜨개질하셨다."},
    {"template": "목수는 새 집의 지붕을 튼튼하게 고치기 위해 하루 종일 {망치|식기세척기}를 사용했다."}
]

LETTERS_POOL = ["F", "H", "J", "K", "L", "N", "P", "Q", "R", "S", "T", "Y"]

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

# 📢 [순수 파이썬 오디오] 외부 패키지(scipy 등) 없이 메트로놈 원음을 만드는 함수
def generate_pure_metronome(bpm, duration_seconds=20):
    sample_rate = 22050
    num_channels = 1
    bytes_per_sample = 2
    beat_interval = 60.0 / bpm
    click_samples = int(sample_rate * 0.05)
    total_samples = int(sample_rate * duration_seconds)
    
    audio_data = [0] * total_samples
    click_wave = [int(math.sin(2 * math.pi * 880 * (i / sample_rate)) * 16000) for i in range(click_samples)]
    
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
        
    header = bytearray()
    header.extend(b'RIFF')
    header.extend((36 + len(data_bytes)).to_bytes(4, 'little'))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))
    header.extend((1).to_bytes(2, 'little'))
    header.extend((num_channels).to_bytes(2, 'little'))
    header.extend((sample_rate).to_bytes(4, 'little'))
    header.extend((sample_rate * num_channels * bytes_per_sample).to_bytes(4, 'little'))
    header.extend((num_channels * bytes_per_sample).to_bytes(2, 'little'))
    header.extend((bytes_per_sample * 8).to_bytes(2, 'little'))
    header.extend(b'data')
    header.extend((len(data_bytes)).to_bytes(4, 'little'))
    
    return bytes(header + data_bytes)

# -------------------------------------------------------------------------
# [요구사항 1] 사전 조사 페이지
# -------------------------------------------------------------------------
if st.session_state.page == "survey_pre":
    st.title("📋 실험 전 사전 설문조사")
    st.write("본 연구 데이터 수집을 위해 아래 문항에 응답해 주세요.")
    
    name = st.text_input("참여자 이름 / ID")
    
    # 1. 나이 입력 제한 (만 19세 ~ 29세만 가능하도록 딱 제약)
    age = st.number_input("나이 (만 나이 입력)", min_value=19, max_value=29, value=22, 
                          help="본 실험은 만 19세부터 29세까지만 참여가 가능합니다.")
    
    # 2. 성별 (선택안함 없이 남성/여성만 제공)
    gender = st.selectbox("성별", ["남성", "여성"])
    
    # 3. 수면 시간 입력 (00시 00분 타임 셀렉터 포맷)
    sleep_time = st.time_input("어제 수면 시간 (취침 시각)", value=time.fromisoformat("23:00:00"))
    
    # 4. 현재 피로도 척도 (1~5)
    fatigue = st.slider("현재 본인이 느끼는 피로도는 어느 정도입니까? (1: 전혀 안 피곤함 ~ 5: 매우 피로함)", 1, 5, 3)
    
    # 5. 평소 소음 민감도 (1~5)
    noise_sensitivity = st.slider("평소 일상생활 소음에 얼마나 민감하십니까? (1: 전혀 민감하지 않음 ~ 5: 매우 민감함)", 1, 5, 3)
    
    # 6. 평소 선호하는 음향 환경 선호도
    sound_preference = st.radio("평소 공부나 작업 시 어떤 음향 환경을 선호하십니까?", 
                                ["완전한 무음 상태", "적당한 백색소음(카페, 자연음)", "잔잔한 음악이나 가요", "일정한 박자의 비트나 메트로놈"])
    
    if st.button("실험 환경 확인 및 테스트 시작", use_container_width=True):
        if name:
            # -------------------------------------------------------------------------
            # [요구사항 2] 처치 조건 사전 배정 알고리즘
            # -------------------------------------------------------------------------
            # ID 문자열을 해싱하여 무음, 60bpm, 130bpm 중 하나로 고정 고유 매칭 (엑셀 선입력 불필요)
            hash_val = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
            treatments = ["silent", "60bpm", "130bpm"]
            assigned_treatment = treatments[hash_val % 3]
            
            st.session_state.survey_data.update({
                "name": name, "age": age, "gender": gender,
                "sleep_time": sleep_time.strftime("%H:%M"), "fatigue": fatigue,
                "noise_sensitivity": noise_sensitivity, "sound_preference": sound_preference,
                "treatment": assigned_treatment
            })
            
            # 10개 문장을 무작위 셔플링하여 세팅 준비
            shuffled_pool = random.sample(RSPAN_RAW_SENTENCES, len(RSPAN_RAW_SENTENCES))
            processed_sentences = []
            
            for item in shuffled_pool:
                template = item["template"]
                p1 = template.find("{")
                p2 = template.find("|")
                p3 = template.find("}")
                
                word_true = template[p1+1:p2]
                word_false = template[p2+1:p3]
                
                # 50% 확률로 맞는 문장 또는 틀린 문장을 동적으로 조립하여 노출
                is_correct_type = random.choice([True, False])
                chosen_word = word_true if is_correct_type else word_false
                final_text = template[:p1] + chosen_word + template[p3+1:]
                
                processed_sentences.append({"text": final_text, "correct": is_correct_type})
                
            st.session_state.set_size = 10  # 총 10문장 고정
            st.session_state.current_step = 0
            st.session_state.sub_stage = "sentence"
            st.session_state.selected_sentences = processed_sentences
            st.session_state.selected_letters = random.sample(LETTERS_POOL, st.session_state.set_size)
            
            st.session_state.user_sentence_answers = []
            st.session_state.user_recalled_letters = []
            st.session_state.sentence_start_time = 0.0
            st.session_state.total_sentence_rt = 0.0
            
            st.session_state.page = "rspan_test"
            st.rerun()
        else:
            st.error("참여자 이름 또는 ID를 기입해주셔야 실험 배정이 시작됩니다.")

# -------------------------------------------------------------------------
# [요구사항 2] RSPAN 테스트 본 무대 루프
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_test":
    treatment = st.session_state.survey_data["treatment"]
    st.title(f"🕹️ RSPAN 테스트 진행 중 ({treatment})")
    
    # 안정적인 오디오 무한 루프 스트리밍
    if treatment != "silent":
        bpm_val = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_val, duration_seconds=15)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        st.markdown(f'<audio autoplay loop id="audio_{treatment}"><source src="data:audio/wav;base64,{audio_base64}" type="audio/wav"></audio>', unsafe_allow_html=True)

    idx = st.session_state.current_step
    
    if st.session_state.sub_stage == "sentence":
        st.subheader(f"📊 문장 진위 판별 (단계: {idx + 1} / {st.session_state.set_size})")
        current_sentence = st.session_state.selected_sentences[idx]["text"]
        
        st.info(f"**[제시 문장]** {current_sentence}")
        st.write("위 문장은 문맥상 논리적 구조가 올바른 문장입니까?")
        
        if st.session_state.sentence_start_time == 0.0:
            st.session_state.sentence_start_time = time.time()
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⭕ TRUE (올바른 문장)", use_container_width=True, key=f"t_btn_{idx}"):
                st.session_state.total_sentence_rt += (time.time() - st.session_state.sentence_start_time)
                st.session_state.user_sentence_answers.append(st.session_state.selected_sentences[idx]["correct"] == True)
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()
        with col2:
            if st.button("❌ FALSE (틀린 문장)", use_container_width=True, key=f"f_btn_{idx}"):
                st.session_state.total_sentence_rt += (time.time() - st.session_state.sentence_start_time)
                st.session_state.user_sentence_answers.append(st.session_state.selected_sentences[idx]["correct"] == False)
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()

    # [요구사항 2] 글자는 정확히 0.5초 동안만 화면에 노출 후 자동 리런
    elif st.session_state.sub_stage == "letter":
        st.subheader("💡 나타난 글자의 알파벳 자음을 암기하세요")
        tgt = st.session_state.selected_letters[idx]
        
        st.markdown(f"<h1 style='text-align: center; font-size: 120px; color: #FF4B4B; font-weight: bold;'>{tgt}</h1>", unsafe_allow_html=True)
        time.sleep(0.5)  # 단어 노출 정확히 0.5초 유지
        
        if idx + 1 < st.session_state.set_size:
            st.session_state.current_step += 1
            st.session_state.sub_stage = "sentence"
        else:
            st.session_state.page = "rspan_recall"
        st.rerun()

# -------------------------------------------------------------------------
# 자음 복기 입력 매트릭스 패드 단계
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_recall":
    st.title("⌨️ Letter Recall Step")
    st.write("방금 전 화면에 스쳐 지나갔던 자음들을 **나열된 순서대로 정확하게 복기하세요.**")
    st.warning(f"참여자 기입 순서 트랙: {' ➔ '.join(st.session_state.user_recalled_letters)}")
    
    pad_cols = st.columns(4)
    for i, letter in enumerate(LETTERS_POOL):
        with pad_cols[i % 4]:
            if st.button(letter, use_container_width=True, key=f"recall_matrix_{letter}"):
                st.session_state.user_recalled_letters.append(letter)
                st.rerun()
                
    st.write("---")
    c_clear, c_sub = st.columns(2)
    with c_clear:
        if st.button("🗑️ 선택 히스토리 초기화", use_container_width=True):
            st.session_state.user_recalled_letters = []
            st.rerun()
    with c_sub:
        if st.button("최종 과제 채점 및 완료하기", use_container_width=True, type="primary"):
            correct = st.session_state.selected_letters
            user = st.session_state.user_recalled_letters
            
            score = sum(1 for u, c in zip(user, correct) if u == c)
            accuracy = round((sum(st.session_state.user_sentence_answers) / st.session_state.set_size) * 100, 1)
            mean_rt = round(st.session_state.total_sentence_rt / st.session_state.set_size, 3)
            
            st.session_state.survey_data.update({
                "rspan_score": f"{score}/{st.session_state.set_size}",
                "sentence_accuracy": f"{accuracy}%",
                "reaction_time": mean_rt
            })
            st.session_state.page = "survey_post"
            st.rerun()

# -------------------------------------------------------------------------
# [요구사항 3] 사후 설문 조사 (집중도 자가평가 1~5 고정)
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 사후 평가 문항")
    
    satisfaction = st.slider("방금 진행한 인지 과제 중 자신의 집중도 자가평가 수치를 선택해 주세요. (1: 매우 산만함 ~ 5: 완벽히 집중함)", 1, 5, 3)
    feedback = st.text_area("그 외 환경 자극 조건(메트로놈 속도 등)에 대해 느껴진 주관적 반응 기술")
    
    if st.button("실험 최종 보고서 데이터 서버 전송", use_container_width=True, type="primary"):
        st.session_state.survey_data.update({"satisfaction": satisfaction, "feedback": feedback})
        
        with st.spinner("구글 스프레드시트 API 엔진에 연산 데이터를 백업 중입니다..."):
            try:
                creds = st.secrets["gspread_credentials"]
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                
                client = gspread.service_account_from_dict(creds)
                sheet = client.open_by_url(sheet_url).get_worksheet(0)
                
                sheet.append_row([
                    st.session_state.survey_data.get("name", ""),
                    st.session_state.survey_data.get("age", ""),
                    st.session_state.survey_data.get("gender", ""),
                    st.session_state.survey_data.get("sleep_time", ""),
                    st.session_state.survey_data.get("fatigue", ""),
                    st.session_state.survey_data.get("noise_sensitivity", ""),
                    st.session_state.survey_data.get("sound_preference", ""),
                    st.session_state.survey_data.get("treatment", ""),
                    st.session_state.survey_data.get("rspan_score", ""),
                    st.session_state.survey_data.get("sentence_accuracy", ""),
                    st.session_state.survey_data.get("reaction_time", ""),
                    st.session_state.survey_data.get("satisfaction", ""),
                    st.session_state.survey_data.get("feedback", "")
                ])
                st.session_state.page = "complete"
                st.rerun()
            except Exception as e:
                st.error(f"시트 전송 누락 오류가 감지되었습니다: {e}")
                st.info("임시 확인용 로컬 텍스트 백업 파일 코드:")
                st.code(str(st.session_state.survey_data))

elif st.session_state.page == "complete":
    st.title("🎉 실험이 정상적으로 완수되었습니다.")
    st.success("인지 과학 실험 측정치가 클라우드 DB에 무사히 보관되었습니다. 협조에 대단히 감사드립니다.")
    st.balloons()
    st.json(st.session_state.survey_data)