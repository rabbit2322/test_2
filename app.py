import streamlit as st
import time
import random
import math
import base64
import gspread
import hashlib

# 페이지 기본 설정
st.set_page_config(page_title="RSPAN 작업기억 테스트", layout="centered")

# 전역 알파벳 자음 풀
LETTERS_POOL = ["F", "H", "J", "K", "L", "N", "P", "Q", "R", "S", "T", "Y"]

# RSPAN 문장 데이터베이스 (충분한 양 확보)
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
    {"template": "목수는 새 집의 지붕을 튼튼하게 고치기 위해 하루 종일 {망치|식기세척기}를 사용했다."},
    {"template": "사육사는 배가 고파 울부짖는 아기 사자에게 신선한 {우유|지우개}를 젖병에 담아 먹였다."},
    {"template": "기상청은 내일 오후부터 강한 바람과 함께 많은 {장마비|프린터}가 내릴 것이라고 예보했다."},
    {"template": "화가는 커다란 캔버스 위에 아름다운 정원의 {풍경|선풍기}을 정성스럽게 그려 나갔다."},
    {"template": "독서실에서 공부하던 수험생은 졸음을 쫓기 위해 시원한 {캔커피|슬리퍼}를 마셨다."},
    {"template": "요리사는 잘 익은 토마토와 신선한 야채를 다져서 맛있는 {소스|벽걸이시계}를 만들었다."}
]

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "instruction"  # 안내 페이지부터 시작
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}
if "current_block" not in st.session_state:
    st.session_state.current_block = 1  # 1단계(3개), 2단계(5개), 3단계(7개)
if "block_results" not in st.session_state:
    st.session_state.block_results = {}

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

# 블록별 세트 크기 정의
def get_set_size():
    mapping = {1: 3, 2: 5, 3: 7}
    return mapping.get(st.session_state.current_block, 3)

# 새 블록 시작 시 태스크 상태 초기화 함수
def init_block_task():
    set_size = get_set_size()
    shuffled_pool = random.sample(RSPAN_RAW_SENTENCES, min(set_size, len(RSPAN_RAW_SENTENCES)))
    
    # 부족할 경우 중복 허용 채움
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
    st.title("🔬 Reading Span Task (RSPAN) 실험 안내")
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
    """)
    st.info("⚠️ 주의: 문장 판단을 너무 오래 지연하거나 알파벳을 임의로 적으면 정상적인 측정이 되지 않습니다.")
    
    if st.button("안내를 확인했으며, 사전 설문 시작하기", use_container_width=True, type="primary"):
        st.session_state.page = "survey_pre"
        st.rerun()

# -------------------------------------------------------------------------
# [1] 사전 설문조사 페이지 (문항 대폭 수정)
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_pre":
    st.title("📋 실험 전 사전 설문조사")
    st.write("연구 분석을 위해 솔직하게 응답해 주시기 바랍니다. (참여자 이름은 수집하지 않습니다)")
    
    # 문항 변경: 나이 및 수면 시각 선택 UI 조절
    age = st.number_input("나이 (만 나이 기준)", min_value=15, max_value=50, value=23)
    
    st.write("**어제 수면 시각을 선택해 주세요.**")
    c_hour, c_min = st.columns(2)
    with c_hour:
        sleep_hour = st.selectbox("시 (Hour)", options=[f"{i:02d}" for i in range(24)], index=23)
    with c_min:
        sleep_min = st.selectbox("분 (Minute)", options=[f"{i:02d}" for i in range(0, 60, 10)], index=0)
    
    # 문항 추가: 오전/오후 참여 시간대
    time_of_day = st.radio("현재 참여하고 계신 시간대는 언제입니까?", ["오전 (00:00 ~ 12:00)", "오후 (12:00 ~ 24:00)"])
    
    fatigue = st.slider("현재 본인이 느끼는 피로도는 어느 정도입니까? (1: 매우 개운함 ~ 5: 매우 피로함)", 1, 5, 3)
    noise_sensitivity = st.slider("평소 일상생활 소음에 얼마나 민감하십니까? (1: 매우 둔감함 ~ 5: 매우 민감함)", 1, 5, 3)
    
    # 문항 변경: 주관식 단답형 형태로 수정
    sound_preference = st.text_input("평소 어떤 음향 환경을 선호하십니까? (예: 완전한 무음, 카페 소음, 잔잔한 음악 등 옆에 한줄로 적어달라고 적기)")
    
    if st.button("실험 환경 조건 무작위 배정 및 테스트 시작", use_container_width=True, type="primary"):
        # 익명 난수 기반으로 집단 배정 처리 (이름 제외 대응)
        anon_seed = str(time.time()) + str(age)
        hash_val = int(hashlib.md5(anon_seed.encode('utf-8')).hexdigest(), 16)
        treatments = ["silent", "60bpm", "130bpm"]
        assigned_treatment = treatments[hash_val % 3]
        
        st.session_state.survey_data.update({
            "age": age,
            "sleep_time": f"{sleep_hour}:{sleep_min}",
            "time_of_day": time_of_day,
            "fatigue": fatigue,
            "noise_sensitivity": noise_sensitivity,
            "sound_preference": sound_preference,
            "treatment": assigned_treatment
        })
        
        # 1단계 블록 태스크 초기화 가동
        st.session_state.current_block = 1
        init_block_task()
        st.session_state.page = "rspan_test"
        st.rerun()

# -------------------------------------------------------------------------
# [2] 본 실험 인지 태스크 수행 페이지 (3단계 분할 구조 반영)
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_test":
    treatment = st.session_state.survey_data["treatment"]
    block = st.session_state.current_block
    
    st.title(f"🕹️ RSPAN 테스트 진행 중 [현재 {block}단계 / 총 3단계]")
    st.subheader(f"🔊 소음 자극 환경 조건: {treatment.upper()}")
    
    # 메트로놈 자동 재생 처리
    if treatment != "silent":
        bpm_val = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_val, duration_seconds=40)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        st.markdown(f'<audio autoplay loop id="audio_{treatment}"><source src="data:audio/wav;base64,{audio_base64}" type="audio/wav"></audio>', unsafe_allow_html=True)

    idx = st.session_state.current_step
    
    # 서브 스테이지 1: 문장 판단
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

    # 서브 스테이지 2: 글자 순간 제시
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
# [3] 알파벳 자음 순서 회상 키패드 페이지 (개수 상한/하한 경고 강화)
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_recall":
    block = st.session_state.current_block
    set_size = st.session_state.set_size
    
    st.title(f"⌨️ 자음 회상 키패드 [{block}단계 - 목표 개수: {set_size}개]")
    st.write(f"방금 제시되었던 자음 **{set_size}개**를 순서대로 선택해 주세요.")
    
    st.warning(f"현재 참여자 입력 궤적: {' ➔ '.join(st.session_state.user_recalled_letters)}")
    
    # 키패드 그리드 그리기
    pad_cols = st.columns(4)
    for i, letter in enumerate(LETTERS_POOL):
        with pad_cols[i % 4]:
            if st.button(letter, use_container_width=True, key=f"b_{block}_pad_{letter}"):
                st.session_state.user_recalled_letters.append(letter)
                st.rerun()
                
    st.write("---")
    c_clear, c_sub = st.columns(2)
    with c_clear:
        if st.button("🗑️ 선택 전체 초기화", use_container_width=True):
            st.session_state.user_recalled_letters = []
            st.rerun()
            
    with c_sub:
        if st.button("이 단계 제출 및 기록", use_container_width=True, type="primary"):
            user_len = len(st.session_state.user_recalled_letters)
            
            # 피드백 반영: 자음 입력 개수 과잉 또는 부족 시 경고 문장 발생 후 세션 중단
            if user_len < set_size:
                st.error(f"🚨 입력된 글자가 부족합니다! 현재 {user_len}개 선택하셨습니다. 목표 수치인 {set_size}개를 정확히 맞춰 제출해 주세요.")
            elif user_len > set_size:
                st.error(f"🚨 입력된 글자가 너무 많습니다! 현재 {user_len}개 선택하셨습니다. 목표 수치인 {set_size}개를 정확히 맞춰 제출해 주세요.")
            else:
                # 점수 및 반응속도 집계 저장
                correct = st.session_state.selected_letters
                user = st.session_state.user_recalled_letters
                
                score = sum(1 for u, c in zip(user, correct) if u == c)
                accuracy = round((sum(st.session_state.user_sentence_answers) / set_size) * 100, 1)
                mean_rt = round(st.session_state.total_sentence_rt / set_size, 3)
                
                st.session_state.block_results[f"b{block}_score"] = f"{score}/{set_size}"
                st.session_state.block_results[f"b{block}_accuracy"] = f"{accuracy}%"
                st.session_state.block_results[f"b{block}_rt"] = mean_rt
                
                # 단계 전환 제어 (3단계까지 완료하면 설문 페이지로)
                if st.session_state.current_block < 3:
                    st.session_state.current_block += 1
                    init_block_task()
                    st.session_state.page = "rspan_test"
                else:
                    st.session_state.page = "survey_post"
                st.rerun()

# -------------------------------------------------------------------------
# [4] 사후 집중도 및 기프티콘 추첨 설문조사 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 실험 사후 주관성 평가")
    st.write("모든 태스크가 완료되었습니다. 마지막 문항에 답변해 주세요.")
    
    satisfaction = st.slider("테스트를 진행하는 동안 본인의 집중도는 어떠했습니까? (1: 매우 산만함 ~ 5: 완벽히 집중함)", 1, 5, 3)
    feedback = st.text_area("소음 조건(메트로놈 비트 소리 등)이 인지 태스크 수행에 어떤 영향을 주었는지 자유롭게 적어주세요.")
    
    st.markdown("---")
    st.subheader("🎁 참여 감사 기프티콘 이벤트 (선택사항)")
    st.write("아래에 전화번호를 남겨주시면, 추첨을 통해 감사의 의미로 스타벅스 기프티콘을 발송해 드립니다.")
    phone_number = st.text_input("휴대폰 번호 입력 (예: 010-XXXX-XXXX)", placeholder="선택 사항이므로 기입하지 않으셔도 무방합니다.")
    
    if st.button("최종 실험 결과 데이터베이스 전송", use_container_width=True, type="primary"):
        # 사후 데이터 통합 병합
        st.session_state.survey_data.update({
            "satisfaction": satisfaction, 
            "feedback": feedback,
            "phone_number": phone_number if phone_number else "미입력"
        })
        # 블록별 세부 성적 지표 최종 통합
        st.session_state.survey_data.update(st.session_state.block_results)
        
        with st.spinner("클라우드 데이터베이스 전송 트래픽 처리 중..."):
            try:
                creds = st.secrets["gspread_credentials"]
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                
                client = gspread.service_account_from_dict(creds)
                sheet = client.open_by_url(sheet_url).get_worksheet(0)
                
                # 구글 시트에 행 단위 추가 데이터 적재
                sheet.append_row([
                    st.session_state.survey_data.get("age", ""),
                    st.session_state.survey_data.get("sleep_time", ""),
                    st.session_state.survey_data.get("time_of_day", ""),
                    st.session_state.survey_data.get("fatigue", ""),
                    st.session_state.survey_data.get("noise_sensitivity", ""),
                    st.session_state.survey_data.get("sound_preference", ""),
                    st.session_state.survey_data.get("treatment", ""),
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
                ])
                st.session_state.page = "complete"
                st.rerun()
            except Exception as e:
                st.error(f"시트 바인딩 중 누락 이슈 발생: {e}")
                st.info("임시 확인용 로컬 세션 데이터 캐시 스냅샷:")
                st.code(str(st.session_state.survey_data))

# -------------------------------------------------------------------------
# [5] 최종 마감 완료 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "complete":
    st.title("🎉 테스트 및 설문 제출 완료")
    st.success("모든 실험 프로세스가 안전하게 종료되었습니다. 학술 연구에 귀중한 시간을 내어 참여해 주셔서 대단히 감사합니다.")
    st.balloons()
    st.json(st.session_state.survey_data)