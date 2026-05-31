import streamlit as st
import time
import random
import math
import base64
import os
import gspread
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime
import json 


# 페이지 기본 설정
st.set_page_config(page_title="RSPAN 작업기억 테스트", layout="centered")

# --- [데이터 로드 함수] ---
@st.cache_data
def load_all_data():
    sentences = []
    if os.path.exists("span.txt"):
        with open("span.txt", "r", encoding="utf-8") as f:
            sentences = [{"template": line.strip()} for line in f if line.strip()]
    
    df = pd.DataFrame(columns=['code', 'treatment', 'time_slot'])
    if os.path.exists("participant_list.csv"):
        df = pd.read_csv("participant_list.csv")
        df.columns = df.columns.str.strip().str.lower()
    return sentences, df

# --- [구글 시트 연결 함수] ---
@st.cache_resource 
def get_google_sheet():
    # secrets.toml에서 정보를 가져옵니다. 
    # (JSON 전체를 가져오는지, 개별 키를 가져오는지 확인 후 수정)
    creds_dict = st.secrets["gspread_credentials"]
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_url(st.secrets["connections"]["gsheets"]["spreadsheet"]).sheet1
    return sh

# 데이터 초기 로드
RSPAN_RAW_SENTENCES, MASTER_DF = load_all_data()

# 전역 알파벳 자음 풀
LETTERS_POOL = ["F", "H", "J", "K", "L", "N", "P", "Q", "R", "S", "T", "Y"]e

# 페이지 설정
# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "instruction"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}
if "current_block" not in st.session_state:
    st.session_state.current_block = 1
if "block_results" not in st.session_state:
    st.session_state.block_results = {}
if "user_info" not in st.session_state:
    st.session_state.user_info = None
    
# 코드 상단 세션 상태 초기화 부분 바로 아래에 추가
if st.session_state.page != "instruction":
    st.sidebar.warning("⚠️ 주의: 새로고침을 하면 실험 데이터가 초기화됩니다.")

# 순수 메트로놈 오디오 생성 함수 (WAV 바이너리)
def generate_pure_metronome(bpm, duration_seconds=30):
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

def get_metronome_sound():
    # 샘플링 레이트
    sample_rate = 44100
    # 주파수 (440Hz: A4음)
    frequency = 440
    # 재생 시간 (0.5초)
    duration = 0.5
    
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # 사인파 생성
    wave = 0.5 * np.sin(2 * np.pi * frequency * t)
    return wave

# 블록별 세트 크기 정의
def get_set_size():
    mapping = {1: 3, 2: 5, 3: 7}
    return mapping.get(st.session_state.current_block, 3)

# 새 블록 시작 시 태스크 상태 초기화 함수
def init_block_task():
    set_size = get_set_size()
    
    # 문장 파일 로드 예외 처리
    if not RSPAN_RAW_SENTENCES:
        st.error("🚨 'span.txt' 파일이 없거나 비어 있어 실험을 진행할 수 없습니다.")
        st.stop()
        
    shuffled_pool = random.sample(RSPAN_RAW_SENTENCES, min(set_size, len(RSPAN_RAW_SENTENCES)))
    
    while len(shuffled_pool) < set_size:
        shuffled_pool.append(random.choice(RSPAN_RAW_SENTENCES))
        
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
        
    st.session_state.set_size = set_size
    st.session_state.current_step = 0
    st.session_state.sub_stage = "sentence"
    st.session_state.selected_sentences = processed_sentences
    st.session_state.selected_letters = random.sample(LETTERS_POOL, set_size)
    
    st.session_state.user_sentence_answers = []
    st.session_state.user_recalled_letters = []
    st.session_state.sentence_start_time = 0.0
    st.session_state.total_sentence_rt = 0.0

# -------------------------------------------------------------------------
# [0] 실험 사전 안내 페이지
# -------------------------------------------------------------------------

if st.session_state.page == "instruction":
    st.title("🔬 Reading Span Task (RST) 실험 안내")
    st.write("본 실험은 언어 처리 능력과 작업 기억 용량(Working Memory Capacity)을 측정하기 위한 검사입니다.")
    
    st.markdown("""
    ### 💡 실험 진행 방식
    본 실험은 총 **3개의 단계(Block)**로 구성되어 있으며, 갈수록 기억해야 하는 항목이 많아집니다.
    * **1단계 (Block 1):** 총 3개의 문장 판단 + 3개의 글자 기억
    * **2단계 (Block 2):** 총 5개의 문장 판단 + 5개의 글자 기억
    * **3단계 (Block 3):** 총 7개의 문장 판단 + 7개의 글자 기억
    
    ### 🕹️ 세부 수행 흐름
    1. 화면에 문장이 제시되면 문맥이 올바른지 **⭕(TRUE)** 또는 **❌(FALSE)** 버튼을 눌러 빠르게 판단합니다.
    2. 문장 판단 직후 화면에 **알파벳 자음 한 글자**가 0.5초 동안 나타났다 사라집니다. 이 글자를 순서대로 머릿속에 기억하셔야 합니다.
    3. 지정된 세트가 끝나면 키패드가 나타납니다. 방금 보았던 알파벳들을 **나타났던 순서 그대로** 마우스로 클릭하여 입력해 주세요.
    
    ### 🎧 사전 준비 사항
    * 테스트 진행 시간: 00분 ~ 00분
    * **이어폰/헤드폰 착용:** 실험 중 제시되는 소리를 명확히 듣기 위해 반드시 이어폰이나 헤드폰을 착용해 주세요.
    * **음량 조절:** 아래 '소리 테스트' 버튼을 눌러 소리를 확인하고, 본인이 편안하게 들을 수 있는 적절한 크기로 조절해 주세요.
    """)
    st.info("⚠️ 주의: 문장 판단을 너무 오래 지연하거나 알파벳을 임의로 적으면 정상적인 측정이 되지 않습니다.")

    st.write("---")
    
    # [추가] 소리 테스트 섹션
    st.subheader("🔊 음량 확인 및 테스트")
    
    if st.button("소리 테스트 재생"):
        sound_data = get_metronome_sound()
        # 데이터가 담긴 넘파이 배열을 직접 재생
        st.audio(sound_data, sample_rate=44100)
        
    st.write("위 버튼을 눌러 소리가 정상적으로 들리는지 확인하고, 기기의 볼륨을 조절해 주세요.")

    st.write("---")
    
    # 코드 입력 및 실험 시작
    user_code = st.text_input("참여자 코드를 입력하세요", placeholder="코드를 입력하고 아래 버튼을 누르세요")
    
# [참여자 코드 확인 로직]
if st.button("안내 확인 및 실험 시작하기", use_container_width=True, type="primary"):
    if not user_code:
        st.warning("참여자 코드를 입력해 주세요.")
    else:
        # 데이터프레임의 'code' 열을 문자열로 통일 후 비교
        search_result = MASTER_DF[MASTER_DF['code'].astype(str).str.strip() == str(user_code).strip()]
        
        if not search_result.empty:
            p_data = search_result.iloc[0]
            
            # 시간대 제한 체크 (들여쓰기 수정 완료)
            now_hour = datetime.now().hour
            current_slot = "AM" if now_hour < 12 else "PM"
            
            if str(p_data['time_slot']).strip().upper() != current_slot:
                st.error(f"지금은 {current_slot}입니다. 배정된 시간대인 {p_data['time_slot']}에 접속하세요.")
            else:
                st.session_state.survey_data.update(p_data.to_dict())
                st.session_state.page = "survey_pre"
                st.rerun()
        else:
            st.error("등록되지 않은 참여자 코드입니다.")
    

# -------------------------------------------------------------------------
# [1] 1. 사전 설문조사 (Pre-test Questionnaire)
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_pre":
    st.title("📋 1. 사전 설문조사 (Pre-test Questionnaire)")
    st.write("연구 분석을 위해 아래 문항에 응답해 주시기 바랍니다.")
    
    # 파일 부재 시 설문 진입 단계에서 사전 경고 처리
    if not RSPAN_RAW_SENTENCES:
        st.error("⚠️ 경고: 폴더 내 'span.txt' 파일이 누락되었거나 비어 있습니다. 파일 배치를 확인해 주세요.")
    
    # 피험자 연령: 만 ( )세 (만 19세~29세)
    age = st.number_input("피험자 연령: 만 ( )세 (만 19세~29세)", min_value=19, max_value=29, value=23)
    
    # 전일 수면 시간: ( )시 ( )분 취침
    st.write("**전일 수면 시간**")
    c_hour, c_min = st.columns(2)
    with c_hour:
        sleep_hour = st.selectbox("시 (Hour)", options=[f"{i:02d}" for i in range(24)], index=23)
    with c_min:
        sleep_min = st.selectbox("분 (Minute)", options=[f"{i:02d}" for i in range(0, 60, 10)], index=0)
    
    # 주관적인 현재 피로도 (1: 매우 개운함 ~ 5: 매우 피로함)
    fatigue = st.slider("주관적인 현재 피로도 (1: 매우 개운함 ~ 5: 매우 피로함)", 1, 5, 3)
    
    # 주관적인 소음 민감도 (1: 매우 둔감함 ~ 5: 매우 민감함)
    noise_sensitivity = st.slider("주관적인 소음 민감도 (1: 매우 둔감함 ~ 5: 매우 민감함)", 1, 5, 3)
    
    # 평소 선호하는 음향 학습 환경을 선택해주세요.
    sound_pref_type = st.radio(
        "평소 선호하는 음향 학습 환경을 선택해주세요.",
        [
            "완전한 정적 (예: 무음 환경)",
            "지속적인 백색소음 (예: 팬 소리, 빗소리 등)",
            "적당한 생활 소음이 있는 환경 (예: 카페 등)",
            "기타 (자유 기술)"
        ]
    )
    
    # [수정] 기타 선택 시 입력창만 표시
    if sound_pref_type == "기타 (자유 기술)":
        sound_preference_detail = st.text_input("기타 (자유 기술) 내용을 적어주세요. (예: 잔잔한 클래식 음악 등)", placeholder="여기에 자유롭게 작성")
        final_sound_preference = f"기타: {sound_preference_detail}"
    else:
        final_sound_preference = sound_pref_type
    
    if st.button("실험 환경 조건 무작위 배정 및 테스트 시작", use_container_width=True, type="primary"):
        anon_seed = str(time.time()) + str(age) + str(fatigue)
        hash_val = int(hashlib.md5(anon_seed.encode('utf-8')).hexdigest(), 16)
        
        st.session_state.survey_data.update({
            "age": age,
            "sleep_time": f"{sleep_hour}:{sleep_min}",
            "fatigue": fatigue,
            "noise_sensitivity": noise_sensitivity,
            "sound_preference": final_sound_preference
        })
        
        st.session_state.current_block = 1
        st.session_state.page = "block_intro"
        st.rerun()

# -------------------------------------------------------------------------
# [1-5] 각 단계(Block) 시작 전 대기 및 설명 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "block_intro":
    block = st.session_state.current_block
    set_size = get_set_size()
    
    st.title(f"🏁 {block}단계 테스트 시작 안내")
    st.markdown(f"""
    지금부터 **{block}단계** 테스트를 시작합니다.
    
    * 이번 단계에서는 총 **{set_size}개**의 문장 판단과 **{set_size}개**의 알파벳 자음이 제시됩니다.
    * 문장 참/거짓 판단을 마치는 즉시 알파벳이 등장하니 집중해 주시기 바랍니다.
    
    준비가 완료되었다면 아래 버튼을 눌러 시작하세요.
    """)
    
    if st.button(f"{block}단계 과제 시작하기", use_container_width=True, type="primary"):
        init_block_task()
        st.session_state.page = "rspan_test"
        st.rerun()

# -------------------------------------------------------------------------
# [2] 본 실험 인지 태스크 수행 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_test":
    treatment = st.session_state.survey_data["treatment"]
    block = st.session_state.current_block
    
    st.title(f"🕹️ RSPAN 테스트 진행 중 [현재 {block}단계 / 총 3단계]")
    st.subheader(f"🔊 소음 자극 환경 조건: {treatment.upper()}")
    
    if treatment != "silent":
        bpm_val = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_val, duration_seconds=40)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        st.markdown(f'<audio autoplay loop id="audio_{treatment}"><source src="data:audio/wav;base64,{audio_base64}" type="audio/wav"></audio>', unsafe_allow_html=True)

    idx = st.session_state.current_step
    
    if st.session_state.sub_stage == "sentence":
        st.markdown(f"### 📊 문장 진위 판단 (`{idx + 1}` / `{st.session_state.set_size}`개 제시됨)")
        current_sentence = st.session_state.selected_sentences[idx]["text"]
        
        st.info(f"**[제시 문장]** {current_sentence}")
        st.write("위 문장의 맥락 흐름이 자연스럽고 올바른가요?")
        
        if st.session_state.sentence_start_time == 0.0:
            st.session_state.sentence_start_time = time.time()
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⭕ TRUE (맞는 문장)", use_container_width=True, key=f"b_{block}_t_{idx}"):
                st.session_state.total_sentence_rt += (time.time() - st.session_state.sentence_start_time)
                st.session_state.user_sentence_answers.append(st.session_state.selected_sentences[idx]["correct"] == True)
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()
        with col2:
            if st.button("❌ FALSE (틀린 문장)", use_container_width=True, key=f"b_{block}_f_{idx}"):
                st.session_state.total_sentence_rt += (time.time() - st.session_state.sentence_start_time)
                st.session_state.user_sentence_answers.append(st.session_state.selected_sentences[idx]["correct"] == False)
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()

    elif st.session_state.sub_stage == "letter":
        st.subheader("💡 나타난 알파벳 자음을 기억하세요!")
        tgt = st.session_state.selected_letters[idx]
        
        placeholder = st.empty()
        placeholder.markdown(f"<h1 style='text-align: center; font-size: 140px; color: #FF4B4B; font-weight: bold;'>{tgt}</h1>", unsafe_allow_html=True)
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
    block = st.session_state.current_block
    set_size = st.session_state.set_size
    
    st.title(f"⌨️ 자음 회상 키패드 [{block}단계 - 목표 개수: {set_size}개]")
    st.write(f"방금 제시되었던 자음 **{set_size}개**를 순서대로 선택해 주세요.")
    
    st.warning(f"현재 참여자 입력 궤적: {' ➔ '.join(st.session_state.user_recalled_letters)}")
    
    pad_cols = st.columns(4)
    for i, letter in enumerate(LETTERS_POOL):
        with pad_cols[i % 4]:
            if st.button(letter, use_container_width=True, key=f"b_{block}_pad_{letter}"):
                st.session_state.user_recalled_letters.append(letter)
                st.rerun()
                
    st.write("---")
    
    c_back, c_clear, c_sub = st.columns([1, 1, 2])
    with c_back:
        if st.button("⬅️ 마지막 글자 취소", use_container_width=True):
            if len(st.session_state.user_recalled_letters) > 0:
                st.session_state.user_recalled_letters.pop()
            st.rerun()
    with c_clear:
        if st.button("🗑️ 전체 초기화", use_container_width=True):
            st.session_state.user_recalled_letters = []
            st.rerun()
            
    with c_sub:
        if st.button("이 단계 제출 및 기록", use_container_width=True, type="primary"):
            user_len = len(st.session_state.user_recalled_letters)
            
            if user_len < set_size:
                st.error(f"🚨 입력된 글자가 부족합니다! 현재 {user_len}개 선택하셨습니다. 목표 수치인 {set_size}개를 정확히 맞춰 제출해 주세요.")
            elif user_len > set_size:
                st.error(f"🚨 입력된 글자가 너무 많습니다! 현재 {user_len}개 선택하셨습니다. 목표 수치인 {set_size}개를 정확히 맞춰 제출해 주세요.")
            else:
                correct = st.session_state.selected_letters
                user = st.session_state.user_recalled_letters
                
                score = sum(1 for u, c in zip(user, correct) if u == c)
                accuracy = round((sum(st.session_state.user_sentence_answers) / set_size) * 100, 1)
                mean_rt = round(st.session_state.total_sentence_rt / set_size, 3)
                
                st.session_state.block_results[f"b{block}_score"] = f"{score}/{set_size}"
                st.session_state.block_results[f"b{block}_accuracy"] = f"{accuracy}%"
                st.session_state.block_results[f"b{block}_rt"] = mean_rt
                
                if st.session_state.current_block < 3:
                    st.session_state.current_block += 1
                    st.session_state.page = "block_intro"
                else:
                    st.session_state.page = "survey_post"
                st.rerun()

# -------------------------------------------------------------------------
# [4] 2. 사후 설문조사 (Post-test Questionnaire)
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 2. 사후 설문조사 (Post-test Questionnaire)")
    st.write("모든 테스트 태스크가 완료되었습니다. 마지막 문항에 성실히 답변해 주세요.")
    
    # 테스트 중 주관적인 본인의 집중도 (1: 매우 산만함 ~ 5: 완벽히 집중함)
    satisfaction = st.slider("테스트 중 주관적인 본인의 집중도 (1: 매우 산만함 ~ 5: 완벽히 집중함)", 1, 5, 3)
    
    # 소음조건 영향 및 상세 안내 가이드라인
    st.caption("💡 예시 안내: 음향이 집중, 기억 회상, 심리적 부담 등에 어떤 영향을 주었는지 간략히 기술해 주십시오.")
    feedback = st.text_area(
        "배정된 소음 조건이 테스트 과정 중 본인의 기억력이나 집중력에 어떤 영향을 줬는지 1~2줄 내외로 작성해 주세요.",
        placeholder="예시: 소리의 박자가 빨라질 때 흐름이 흐트러져 단어 기억에 부담을 느꼈습니다. / 무음 상태라 오롯이 문장 분석에만 몰입하기 수월했습니다."
    )
    
    st.markdown("---")
    st.subheader("📞 연락처 수집 (선택 사항)")
    phone_number = st.text_input("휴대폰 번호 입력 (예: 010-XXXX-XXXX)", placeholder="선택 사항이므로 기입하지 않으셔도 무방합니다.")
    
    if st.button("최종 실험 결과 데이터베이스 전송", use_container_width=True, type="primary"):
        # 설문 데이터 업데이트
        st.session_state.survey_data.update({
            "satisfaction": satisfaction, 
            "feedback": feedback if feedback else "내용 미입력",
            "phone_number": phone_number if phone_number else "미입력"
        })
        st.session_state.survey_data.update(st.session_state.block_results)
        
        # 데이터 전송 시도
        try:
            sheet = get_google_sheet()
            
            # 시트에 기록할 행 데이터 구성
            row = [
                st.session_state.survey_data.get("code", ""),
                st.session_state.survey_data.get("treatment", ""),
                st.session_state.survey_data.get("age", ""),
                st.session_state.survey_data.get("b1_score", ""),
                st.session_state.survey_data.get("b1_accuracy", ""),
                st.session_state.survey_data.get("b1_rt", ""),
                st.session_state.survey_data.get("b2_score", ""),
                st.session_state.survey_data.get("b2_accuracy", ""),
                st.session_state.survey_data.get("b2_rt", ""),
                st.session_state.survey_data.get("b3_score", ""),
                st.session_state.survey_data.get("b3_accuracy", ""),
                st.session_state.survey_data.get("b3_rt", ""),
                st.session_state.survey_data.get("satisfaction", ""),
                st.session_state.survey_data.get("feedback", ""),
                st.session_state.survey_data.get("phone_number", "")
            ]
            sheet.append_row(row)
            st.session_state.page = "complete"
            st.rerun()
        except Exception as e:
            st.error(f"전송 실패: {e}")
            
elif st.session_state.page == "complete":
    st.balloons()
    st.title("🎉 실험이 완료되었습니다!")
    st.success("소중한 참여 감사합니다. 창을 닫아주셔도 좋습니다.")