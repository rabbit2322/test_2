import streamlit as st
import time
import random
import math
import base64
import gspread
import hashlib
from datetime import time as dt_time  # 수면 시간 설정을 위한 안전한 임포트

# 페이지 설정
st.set_page_config(page_title="RSPAN 작업기억 테스트", layout="centered")

# 실험용 RSPAN 문장 데이터 풀
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

# 순수 메트로놈 오디오 생성 함수 (WAV 바이너리)
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
# [1] 사전 설문조사 페이지
# -------------------------------------------------------------------------
if st.session_state.page == "survey_pre":
    st.title("📋 실험 전 사전 설문조사")
    st.write("본 연구 데이터 수집을 위해 아래 문항에 응답해 주세요.")
    
    name = st.text_input("참여자 이름 / 고유 식별 ID")
    age = st.number_input("나이 (만 나이 기준)", min_value=19, max_value=29, value=23)
    gender = st.selectbox("성별", ["여성", "남성"])
    
    # 수정 완료: dt_time 객체를 직접 전달하여 안전하게 초기값 설정
    sleep_time = st.time_input("어제 수면 시간 (취침 시각)", value=dt_time(23, 0))
    
    fatigue = st.slider("현재 본인이 느끼는 피로도는 어느 정도입니까? (1: 매우 개운함 ~ 5: 매우 피로함)", 1, 5, 3)
    noise_sensitivity = st.slider("평소 일상생활 소음에 얼마나 민감하십니까? (1: 매우 둔감함 ~ 5: 매우 민감함)", 1, 5, 3)
    sound_preference = st.radio("평소 어떤 음향 환경을 선호하십니까?", 
                                ["완전한 무음 상태", "적당한 백색소음(카페, 자연음)", "잔잔한 음악이나 가요", "일정한 박자의 비트나 메트로놈"])
    
    if st.button("실험 환경 확인 및 테스트 시작", use_container_width=True):
        if name:
            # 해시 기반 실험 조건 무작위 배정
            hash_val = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
            treatments = ["silent", "60bpm", "130bpm"]
            assigned_treatment = treatments[hash_val % 3]
            
            st.session_state.survey_data.update({
                "name": name, "age": age, "gender": gender,
                "sleep_time": sleep_time.strftime("%H:%M"), "fatigue": fatigue,
                "noise_sensitivity": noise_sensitivity, "sound_preference": sound_preference,
                "treatment": assigned_treatment
            })
            
            # 문장 셔플 및 정/오답 셋팅
            shuffled_pool = random.sample(RSPAN_RAW_SENTENCES, len(RSPAN_RAW_SENTENCES))
            processed_sentences = []
            
            for item in shuffled_pool:
                template = item["template"]
                p1, p2, p3 = template.find("{"), template.find("|"), template.find("}")
                word_true = template[p1+1:p2]
                word_false = template[p2+1:p3]
                
                is_correct_type = random.choice([True, False])
                chosen_word = word_true if is_correct_type else word_false
                final_text = template[:p1] + chosen_word + template[p3+1:]
                
                processed_sentences.append({"text": final_text, "correct": is_correct_type})
                
            st.session_state.set_size = 10
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
            st.error("참여자 이름을 정확하게 기입해주셔야 배정이 완료됩니다.")

# -------------------------------------------------------------------------
# [2] 본 실험 인지 태스크 수행 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_test":
    treatment = st.session_state.survey_data["treatment"]
    st.title(f"🕹️ RSPAN 인지 테스트 진행 중 ({treatment})")
    
    # 소음 자극 자동 재생 처리
    if treatment != "silent":
        bpm_val = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_val, duration_seconds=15)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        st.markdown(f'<audio autoplay loop id="audio_{treatment}"><source src="data:audio/wav;base64,{audio_base64}" type="audio/wav"></audio>', unsafe_allow_html=True)

    idx = st.session_state.current_step
    
    if st.session_state.sub_stage == "sentence":
        st.subheader(f"📊 문장 판단 (진행도: {idx + 1} / {st.session_state.set_size})")
        current_sentence = st.session_state.selected_sentences[idx]["text"]
        
        st.info(f"**[제시 문장]** {current_sentence}")
        st.write("위 문장은 문맥 흐름상 올바른 문장입니까?")
        
        if st.session_state.sentence_start_time == 0.0:
            st.session_state.sentence_start_time = time.time()
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⭕ TRUE (맞는 문장)", use_container_width=True, key=f"t_btn_{idx}"):
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

    elif st.session_state.sub_stage == "letter":
        st.subheader("💡 나타난 글자의 알파벳 자음을 기억하세요")
        tgt = st.session_state.selected_letters[idx]
        
        placeholder = st.empty()
        placeholder.markdown(f"<h1 style='text-align: center; font-size: 130px; color: #FF4B4B; font-weight: bold;'>{tgt}</h1>", unsafe_allow_html=True)
        time.sleep(0.5)
        placeholder.empty()
        
        if idx + 1 < st.session_state.set_size:
            st.session_state.current_step += 1
            st.session_state.sub_stage = "sentence"
        else:
            st.session_state.page = "rspan_recall"
        st.rerun()

# -------------------------------------------------------------------------
# [3] 알파벳 자음 순서 회상 키패드 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_recall":
    st.title("⌨️ 자음 회상 단계")
    st.write("화면에 제시되었던 알파벳 자음들을 **순서대로** 선택하십시오.")
    st.warning(f"참여자 입력 궤적: {' ➔ '.join(st.session_state.user_recalled_letters)}")
    
    pad_cols = st.columns(4)
    for i, letter in enumerate(LETTERS_POOL):
        with pad_cols[i % 4]:
            if st.button(letter, use_container_width=True, key=f"recall_matrix_{letter}"):
                st.session_state.user_recalled_letters.append(letter)
                st.rerun()
                
    st.write("---")
    c_clear, c_sub = st.columns(2)
    with c_clear:
        if st.button("🗑️ 선택 내역 전체 초기화", use_container_width=True):
            st.session_state.user_recalled_letters = []
            st.rerun()
    with c_sub:
        if st.button("최종 과제 채점 및 제출", use_container_width=True, type="primary"):
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
# [4] 사후 집중도 주관 설문조사 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 사후 평가 문항")
    
    satisfaction = st.slider("방금 진행한 인지 과제 중 자신의 집중도 자가평가 수치를 선택해 주세요. (1: 매우 산만함 ~ 5: 완벽히 집중함)", 1, 5, 3)
    feedback = st.text_area("그 외 소음 조건 환경에서 느껴진 주관적 반응 기술")
    
    if st.button("실험 데이터 전송 및 최종 마감", use_container_width=True, type="primary"):
        st.session_state.survey_data.update({"satisfaction": satisfaction, "feedback": feedback})
        
        with st.spinner("클라우드 데이터베이스 전송 트래픽 처리 중..."):
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
                st.error(f"시트 바인딩 중 오류 발생: {e}")
                st.info("임시 확인용 데이터 로그:")
                st.code(str(st.session_state.survey_data))

# -------------------------------------------------------------------------
# [5] 최종 마감 완료 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "complete":
    st.title("🎉 실험 제출 완료")
    st.success("모든 테스트와 설문이 완료되었습니다. 참여해 주셔서 대단히 감사합니다.")
    st.balloons()
    st.json(st.session_state.survey_data)