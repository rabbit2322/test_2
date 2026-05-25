import streamlit as st
import time
import random
import math
import base64
import gspread

# 페이지 설정
st.set_page_config(page_title="표준 RSPAN 테스트", layout="centered")

# -------------------------------------------------------------------------
# [실험 명세 규격] 자음 풀 및 실제 RSPAN 표준 문장 데이터셋
# -------------------------------------------------------------------------
LETTERS_POOL = ["F", "H", "J", "K", "L", "N", "P", "Q", "R", "S", "T", "Y"]

# 명세서 이미지에 기술된 {단어1|단어2} 형태의 정오판단 로직 반영
RSPAN_SENTENCES = [
    {"text": "The host greeted all the guests and asked them to sit at the {table|sky}.", "correct": True},
    {"text": "John never liked {crowds|chocolate} and that is why he now lives in the country.", "correct": True},
    {"text": "The prosecutor's {case|dish} was lost due to the lack of supporting evidence.", "correct": True},
    {"text": "The gray-stone building was in Atlanta's most central part on a narrow {street|bicycle}.", "correct": True},
    {"text": "It was a gloomy evening, towards the {autumn|match} of the year 1676.", "correct": True},
    {"text": "The principal introduced the new {president|razor} of the junior class.", "correct": True},
    {"text": "Mark told Janet that he would meet {her|a keyboard} after baseball practice.", "correct": True},
    {"text": "The angry {man|mouse} called the senator to complain about the new tax law.", "correct": True},
    {"text": "A strict {vegetarian|teacher} Jennifer does not eat chicken or beef.", "correct": True},
    {"text": "The {hurricane|pudding} destroyed houses in the village and left many homeless.", "correct": True},
    {"text": "The {bear|pencil} chased after the forest ranger who was carrying honey.", "correct": True},
    # 오답 유도용 믹스 문장들
    {"text": "Nancy's kitchen was infested with carpenter ants and {roaches|lawn mowers}.", "correct": False},
    {"text": "Bill complained that the magazine included more ads than {articles|nails}.", "correct": False},
    {"text": "The policeman demanded to see Jim's {license|pumpkin} and registration.", "correct": False},
    {"text": "Mr. Jones asked his son to water the {plants|cats} and mow the lawn.", "correct": False},
    {"text": "The bride's {mother|school} cried during the wedding ceremony.", "correct": False}
]

# 세션 상태(State) 초기화
if "page" not in st.session_state:
    st.session_state.page = "survey_pre"
if "survey_data" not in st.session_state:
    st.session_state.survey_data = {}

# 📢 [초경량 바이너리 오디오] 외부 라이브러리 없이 메트로놈 루프 원음을 조립하는 함수
def generate_pure_metronome(bpm, duration_seconds=15):
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
# 1. 사전 설문조사 단계
# -------------------------------------------------------------------------
if st.session_state.page == "survey_pre":
    st.title("📋 RSPAN 실험 사전 조사")
    name = st.text_input("참여자 이름/ID")
    age = st.number_input("나이", min_value=1, max_value=100, value=20)
    gender = st.selectbox("성별", ["선택 안 함", "남성", "여성"])
    
    if st.button("실험실 입장"):
        if name:
            st.session_state.survey_data.update({"name": name, "age": age, "gender": gender})
            st.session_state.page = "rspan_instr"
            st.rerun()
        else:
            st.error("참여자 식별 ID를 입력해주세요.")

# -------------------------------------------------------------------------
# 2. RSPAN 표준 실험 가이드 페이지
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_instr":
    st.title("🧠 Automated Reading Span Task")
    st.write("""
    본 검사는 인지심리학 표준 작업기억(Working Memory) 측정 테스트입니다.
    
    * **과제 1 (문장 판단)**: 화면에 영어 문장이 나타납니다. 문장 내부의 괄호 `{단어A|단어B}` 중 **왼쪽 단어**가 오면 문맥이 맞고, **오른쪽 단어**가 오면 문맥이 그릇된 문장입니다. 올바른 문장인지 판단하세요.
    * **과제 2 (자음 기억)**: 문장 판단이 끝나면 화면 중앙에 **알파벳 자음**이 1초간 번쩍입니다. 순서를 기억하세요.
    * **과제 3 (순서 회상)**: 한 세트가 종료되면 제공되는 자음 패드를 이용해 보았던 자음들을 순서대로 마우스 클릭하여 복기합니다.
    """)
    st.info("⚠️ 명세 지침에 따라 배경 메트로놈 자극(무음 / 60bpm / 130bpm) 중 하나가 임의 배정되어 무한 재생됩니다.")
    
    if st.button("실험 시작 (START)", type="primary"):
        # 처치 조건 무작위 할당
        treatments = ["60bpm", "130bpm", "silent"]
        st.session_state.current_treatment = random.choice(treatments)
        st.session_state.survey_data["treatment"] = st.session_state.current_treatment
        
        # [명세 반영] 세트 사이즈 풀에서 무작위 결정 (예: 3개 과제 연속 수행)
        st.session_state.set_size = random.choice([2, 3, 4, 5])
        st.session_state.current_step = 0
        st.session_state.sub_stage = "sentence"
        
        st.session_state.selected_sentences = random.sample(RSPAN_SENTENCES, st.session_state.set_size)
        st.session_state.selected_letters = random.sample(LETTERS_POOL, st.session_state.set_size)
        
        st.session_state.user_sentence_answers = []
        st.session_state.user_recalled_letters = []
        st.session_state.sentence_start_time = 0.0
        st.session_state.total_sentence_rt = 0.0
        
        st.session_state.page = "rspan_test"
        st.rerun()

# -------------------------------------------------------------------------
# 3. RSPAN 테스트 루프 코어
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_test":
    treatment = st.session_state.current_treatment
    st.title(f"⚙️ RSPAN Processing... ({treatment})")
    
    # 사운드 주입 (브라우저 DOM 에러 원천 차단형)
    if treatment != "silent":
        bpm_val = 60 if treatment == "60bpm" else 130
        audio_bytes = generate_pure_metronome(bpm_val, duration_seconds=20)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        st.markdown(f'<audio autoplay loop id="audio_{treatment}"><source src="data:audio/wav;base64,{audio_base64}" type="audio/wav"></audio>', unsafe_allow_html=True)

    idx = st.session_state.current_step
    
    # Sub-Stage 1: 문장 맥락 확인
    if st.session_state.sub_stage == "sentence":
        st.subheader(f"📊 문장 진위 판별 (단계: {idx + 1} / {st.session_state.set_size})")
        raw_text = st.session_state.selected_sentences[idx]["text"]
        
        st.info(f"**Sentence:** {raw_text}")
        st.write("Does this sentence make sense logically with the first option?")
        
        if st.session_state.sentence_start_time == 0.0:
            st.session_state.sentence_start_time = time.time()
            
        col1, col2 = st.columns(2)
        with col1:
            # use_container_width 파라미터를 사용하여 레이아웃 에러 완전 해결
            if st.button("⭕ TRUE (말이 된다)", use_container_width=True, key=f"btn_t_{idx}"):
                st.session_state.total_sentence_rt += (time.time() - st.session_state.sentence_start_time)
                st.session_state.user_sentence_answers.append(st.session_state.selected_sentences[idx]["correct"] == True)
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()
        with col2:
            if st.button("❌ FALSE (말이 안 된다)", use_container_width=True, key=f"btn_f_{idx}"):
                st.session_state.total_sentence_rt += (time.time() - st.session_state.sentence_start_time)
                st.session_state.user_sentence_answers.append(st.session_state.selected_sentences[idx]["correct"] == False)
                st.session_state.sentence_start_time = 0.0
                st.session_state.sub_stage = "letter"
                st.rerun()

    # Sub-Stage 2: 자음 1초간 순간 노출
    elif st.session_state.sub_stage == "letter":
        st.subheader("💡 1초간 노출되는 글자를 외우세요")
        tgt = st.session_state.selected_letters[idx]
        
        st.markdown(f"<h1 style='text-align: center; font-size: 110px; color: #4B92FF; font-weight: bold;'>{tgt}</h1>", unsafe_allow_html=True)
        time.sleep(1.0)
        
        if idx + 1 < st.session_state.set_size:
            st.session_state.current_step += 1
            st.session_state.sub_stage = "sentence"
        else:
            st.session_state.page = "rspan_recall"
        st.rerun()

# -------------------------------------------------------------------------
# 4. 자음 순서 복기 회상(Recall) 패드
# -------------------------------------------------------------------------
elif st.session_state.page == "rspan_recall":
    st.title("⌨️ Letter Recall Matrix")
    st.write("보았던 글자들을 **기억해 낸 순서대로 똑같이** 선택하세요.")
    
    st.info(f"선택 트랙: {' ➔ '.join(st.session_state.user_recalled_letters)}")
    
    # 4열 매트릭스 패드로 명세 이미지처럼 깔끔하게 배치
    pad_cols = st.columns(4)
    for i, letter in enumerate(LETTERS_POOL):
        with pad_cols[i % 4]:
            if st.button(letter, use_container_width=True, key=f"recall_key_{letter}"):
                st.session_state.user_recalled_letters.append(letter)
                st.rerun()
                
    st.write("---")
    c_clear, c_sub = st.columns(2)
    with c_clear:
        if st.button("🗑️ 선택 초기화", use_container_width=True):
            st.session_state.user_recalled_letters = []
            st.rerun()
    with c_sub:
        if st.button("제출 및 결과 확인", use_container_width=True, type="primary"):
            # 정답 매칭 알고리즘 계산
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
# 5. 사후 설문 및 완벽한 구글 시트 업로드 (서비스 계정 인증법 반영)
# -------------------------------------------------------------------------
elif st.session_state.page == "survey_post":
    st.title("📝 실험 결과 기록 및 설문")
    
    satisfaction = st.slider("배경 소음 자극 환경 하에서 집중도는 어땠습니까?", 1, 5, 3)
    feedback = st.text_area("특이 사항 리포트")
    
    if st.button("실험 데이터 최종 서버 전송"):
        st.session_state.survey_data.update({"satisfaction": satisfaction, "feedback": feedback})
        
        with st.spinner("구글 클라우드에 연산 데이터를 백업 중입니다..."):
            try:
                # 💥 image_fe30e3에서 발생했던 public_api 누락 버그 전면 수정 완료
                creds = st.secrets["gspread_credentials"]
                sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
                
                client = gspread.service_account_from_dict(creds)
                sheet = client.open_by_url(sheet_url).get_worksheet(0)
                
                sheet.append_row([
                    st.session_state.survey_data.get("name", ""),
                    st.session_state.survey_data.get("age", ""),
                    st.session_state.survey_data.get("gender", ""),
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
                st.error(f"서버 전송 실패 코드: {e}")
                st.info("비상 안전용 유실 방지 로컬 덤프:")
                st.code(str(st.session_state.survey_data))

elif st.session_state.page == "complete":
    st.title("🎉 테스트 완료")
    st.success("실험 데이터가 안전하게 제출되었습니다. 고생하셨습니다.")
    st.balloons()
    st.json(st.session_state.survey_data)