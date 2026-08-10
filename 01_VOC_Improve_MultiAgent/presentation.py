"""발표용 웹 슬라이드. 외부 CDN 없이 로컬 브라우저에서 동작합니다."""

SLIDES = [
    ("2026.07.14 — 현재", "VOC 분석을 넘어<br><em>품질을 증명하는 시스템</em>", """
      <p class="lead">6-Agent gRPC 분석, 기대 결과 기반 QA, 장애·보안·성능 진단과 배포 판단을 하나의 웹 제품으로 통합했습니다.</p>
      <div class="grid three"><div class="card"><b class="metric">35/35</b><span>최종 품질평가 PASS</span></div>
      <div class="card"><b class="metric">100%</b><span>초기 결함 2건 폐쇄</span></div>
      <div class="card"><b class="metric">81.2/95</b><span>운영 배포 HOLD · 7/16 평가</span></div></div>
      <aside>핵심 메시지: 답변 생성기가 아니라 품질 판정과 배포 증적까지 제공하는 QA 시스템입니다.</aside>"""),
    ("01 · Goal", "프로젝트 목표", """
      <div class="grid"><div class="card"><h3>분석</h3><p>고객 질문을 해석하고 관련 VOC를 찾아 요약과 정책을 생성합니다.</p></div>
      <div class="card"><h3>진단</h3><p>6개 Agent의 중간 산출물과 처리시간을 단계별로 확인합니다.</p></div>
      <div class="card"><h3>판정</h3><p>기대·금지 요소와 9개 항목 100점으로 품질을 판단합니다.</p></div>
      <div class="card"><h3>증적</h3><p>오프라인·라이브·Judge·장애 결과를 보고서로 보관합니다.</p></div></div>"""),
    ("02 · Starting Point", "7월 14일, 무엇이 문제였나", """
      <div class="grid"><div class="card"><ul><li>중복된 Agent 호출 경로</li><li>6개 서버 실행 재현 어려움</li>
      <li>의존성·MCP 경로 불일치</li><li>잘못된 모델과 API 방식</li></ul></div>
      <div class="card"><ul><li>고객 ID 검색 오탐</li><li>질문별 결과가 지나치게 유사</li>
      <li>기대 결과 없는 테스트</li><li>CLI 중심이라 발표·사용이 어려움</li></ul></div></div>
      <aside>첫날에는 기능 추가보다 한 번 실행하고 재현하고 진단할 수 있는 구조를 먼저 만들었습니다.</aside>"""),
    ("03 · Architecture", "단일 통제 경로로 재구성", """
      <div class="flow"><b>웹·MCP</b><i>→</i><b>VOCGRPCRuntime</b><i>→</i><b>Interpreter</b><i>→</i>
      <b>Retriever</b><i>→</i><b>Summarizer</b><i>→</i><b>Evaluator</b><i>→</i><b>Critic</b><i>→</i><b>Improver</b></div>
      <div class="grid three"><div class="card"><h3>단일 오케스트레이터</h3><p>순서와 오류 전파를 한 곳에서 관리</p></div>
      <div class="card"><h3>멀티프로세스</h3><p>6001~6006 독립 실행과 장애 격리</p></div>
      <div class="card"><h3>공통 파이프라인</h3><p>일반·진단·E2E가 같은 경로 사용</p></div></div>"""),
    ("04 · Timeline", "7월 14일부터 현재까지", """
      <div class="timeline"><p><b>07-14 오전</b> · 구조 분석, 단일 파이프라인, supervisor, 환경 수정</p>
      <p><b>07-14 오후</b> · 웹 단건/배치, 6-Agent 진단, 이커머스 데이터, 기대 결과 JSONL</p>
      <p><b>07-15 오전</b> · 100점 점수화, 장애 진단, 품질 폴더, 독립 Judge</p>
      <p><b>07-15 중반</b> · 라이브 E2E, 선택 재시험, 보안, 배포 판단</p>
      <p><b>07-15 현재</b> · QA Control Center, 실행 비교·Trace·승인·반복성·Red Team·CI·드리프트 통합</p>
      <p><b>08-03</b> · API 인증·크레딧·사용량 제한을 안전한 웹 오류와 복구 안내로 분리</p></div>"""),
    ("05 · Test Oracle", "문장 일치가 아닌 기대 요소 평가", """
      <div class="grid"><div class="card"><h3>반드시 포함</h3><ul><li>expected_intent</li><li>expected_keywords</li>
      <li>required_output</li></ul></div><div class="card"><h3>절대 포함 금지</h3><ul><li>근거 없는 확정</li>
      <li>개인정보 요구</li><li>질문과 무관한 정책</li></ul></div></div>
      <p class="lead">LLM 문장은 달라도 고객 의도, 핵심 근거, 필요한 안내와 금지 행위는 안정적으로 검사합니다.</p>"""),
    ("06 · 100 Point Rubric", "교수님 요구 6번 — 품질 점수화", """
      <table><tr><th>항목</th><th>배점</th><th>항목</th><th>배점</th></tr>
      <tr><td>Interpreter 정확성</td><td>15</td><td>Retriever 관련성</td><td>15</td></tr>
      <tr><td>Summarizer 사실성</td><td>15</td><td>Evaluator 타당성</td><td>10</td></tr>
      <tr><td>Critic 위험 탐지</td><td>10</td><td>Improver 실행 가능성</td><td>15</td></tr>
      <tr><td>Agent 연계</td><td>10</td><td>장애·로그 / 성능</td><td>5 / 5</td></tr></table>
      <p><strong>기본 95점 이상 배포 가능</strong> · 웹에서 기준 조정·저장 · E2E와 Judge 모두 충족</p>
      <p class="warn">개인정보 노출과 근거 없는 확정은 점수와 관계없이 즉시 보류</p>"""),
    ("07 · Fault & Security", "정상 답변만 테스트하지 않는다", """
      <div class="grid three"><div class="card"><b class="metric">9/9</b><span>장애 진단 PASS</span><p>포트·Agent·CSV·API·지연·빈 결과</p></div>
      <div class="card"><b class="metric">20/20</b><span>OWASP Red Team</span><p>인젝션·PII·권한·HTML·명령 차단</p></div>
      <div class="card"><b class="metric">130/130</b><span>전체 회귀 PASS</span><p>API 비밀 마스킹·오류 분류 회귀 포함</p></div></div>"""),
    ("08 · Live Evidence", "7월 16일 실제 모델 평가 기준선", """
      <div class="grid three"><div class="card"><b class="metric">18/18</b><span>이커머스 라이브 E2E</span></div>
      <div class="card"><b class="metric">90.9</b><span>E2E 평균 / 100 · 7/16</span></div>
      <div class="card"><b class="metric">81.2</b><span>Anthropic Judge / 100 · 7/16</span></div></div>
      <p class="warn">통합 81.2점 · 배포 기준 95점 미달 → 현재 배포 보류</p>
      <p class="lead">8월 3일에는 Judge를 재실행하지 않고 7월 16일 최신 보관 결과로 AWS 증적 패키지만 생성했습니다.</p>"""),
    ("09 · Performance", "9.5분 병목을 품질 저하 없이 개선", """
      <div class="grid"><div class="card"><h3>측정</h3><p>18건 합계 <b>572.7초</b><br>건당 평균 <b>31.8초</b><br>Improver 평균 <b>25.38초</b></p></div>
      <div class="card"><h3>개선</h3><p>웹 배치·E2E 동시 2건<br>API 재시도 기본 1회<br>예상 약 <b>293.5초</b></p></div></div>
      <p class="lead">케이스 내부의 6-Agent, Critic, refine 순서는 유지하고 독립 케이스만 동시에 실행합니다.</p>"""),
    ("10 · QA Control Center", "12개 고도화 기능을 웹으로 통합", """
      <div class="grid"><div class="card"><h3>실험·회귀</h3><p>실행 이력, 기준선 비교, 출력 diff, 실패 필터, 버전 추적</p></div>
      <div class="card"><h3>진단·안정성</h3><p>6-Agent Trace, RAG 6지표, 중요 5건×3회 변동성</p></div>
      <div class="card"><h3>운영·보안</h3><p>사람 승인, 비용·P95·429, Red Team, 드리프트 알림</p></div>
      <div class="card"><h3>자동화·증적</h3><p>CI 95점 게이트, TXT·XML·HTML·JUnit·PDF·ZIP</p></div></div>"""),
    ("11 · Live Dashboard", "현재 시스템 상태", """
      <div class="grid three"><div class="card"><b class="metric" id="agentMetric">-</b><span>Agent 준비</span></div>
      <div class="card"><b class="metric" id="suiteMetric">-</b><span>자동 품질</span></div>
      <div class="card"><b class="metric" id="faultMetric">-</b><span>장애 진단</span></div></div>
      <p id="liveDetail" class="lead">웹 서버에서 최신 상태를 불러오는 중입니다.</p>"""),
    ("12 · Demo", "발표 데모 시나리오", """
      <ol><li>대시보드 → 품질 PASS와 운영 배포 HOLD 구분</li><li>실행 이력 → 기준선·후보 실행 회귀 비교</li>
      <li>Trace → 6-Agent 입력·출력·시간·비용과 RAG 6지표</li><li>승인 관리 → 자동 검토 큐와 상태 전이</li>
      <li>반복성 5건×3회·Red Team 20건 → 실행별 증적 확인</li></ol><p><a href="/">→ 실제 데모 화면 열기</a></p>"""),
    ("13 · Lessons", "시행착오가 만든 개선", """
      <table><tr><th>현상</th><th>원인</th><th>개선</th></tr>
      <tr><td>6개 포트 사용 중</td><td>정상 Agent 중복 기동</td><td>전체 정상은 재사용, 일부 충돌만 차단</td></tr>
      <tr><td>웹 500</td><td>오류 구분 부족</td><td>오류 코드와 안내 분리</td></tr>
      <tr><td>API 429</td><td>사용량 제한</td><td>동시성 제한·전용 안내·재시험</td></tr>
      <tr><td>API 키·크레딧 오류 원문 노출</td><td>gRPC 상세를 웹 502로 그대로 전달</td><td>키 마스킹과 401·402·429별 한국어 복구 안내</td></tr>
      <tr><td>결과가 비슷함</td><td>검색 겹침</td><td>관련도 순위와 질문 관점</td></tr>
      <tr><td>상세 버튼 무반응처럼 보임</td><td>52개 행 뒤에 상세 패널 배치</td><td>클릭 즉시 상단에서 실제 응답·Trace 표시</td></tr>
      <tr><td>자동 테스트명이 이해되지 않음</td><td>두 결과 화면에 Python 내부 ID를 그대로 노출</td><td>품질 결과표·상세에 AGENT·FAULT·MCP 번호와 한국어 검증 의미 표시</td></tr>
      <tr><td>보안 결과가 개발자 데이터로 보임</td><td>내부 ID·기술 JSON 중심 표시</td><td>RT·FAULT·GATE 번호와 QA 검증 상황·기준·실제 결과 표시</td></tr>
      <tr><td>검사마다 오프라인·비용 동의를 다시 선택</td><td>모드·Judge 수동 선택과 deterministic 자동 대체</td><td>.env 키로 모든 품질 흐름에 라이브 E2E·외부 Judge를 강제하고 비용 동의 제거</td></tr>
      <tr><td>승인 화면 메타 노출·폼 우선·긴 회차명 겹침</td><td>보고서 중심 구성과 동일 폭 필터 열</td><td>날짜·회차·상태 필터 → 큐 선택 → 평가의 3단계 흐름, 데이터 길이별 열 비율·말줄임·반응형 재배치</td></tr>
      <tr><td>케이스·수행이력 필터 체크박스·문구 분리</td><td>일반 입력 라벨의 세로 그리드 스타일 상속</td><td>8/9개 필터 전용 열 비율과 체크박스 한 줄 정렬, 화면 폭별 반응형 배치</td></tr>
      <tr><td>전체 데이터가 표 아래 표시·Word RAG가 모두 참고</td><td>인라인 상세 패널과 전체 passed 고정 문구</td><td>중앙 레이어 상세·QA 필드 완전성 표시·지표별 판정과 RAG 6지표 종합 PASS/FAIL</td></tr>
      </table>"""),
    ("14 · AWS Deployment", "로컬 7개 프로세스를<br><em>하나의 운영 단위</em>로", """
      <div class="flow"><b>ALB · HTTPS</b><i>→</i><b>ECS Fargate</b><i>→</i><b>Web :8000</b><i>+</i><b>6-Agent :6001~6006</b></div>
      <div class="grid three"><div class="card"><b class="metric">6/6</b><span>컨테이너 Agent 준비</span></div>
      <div class="card"><b class="metric">200</b><span>/healthz 상태 점검</span></div>
      <div class="card"><b class="metric">EFS</b><span>SQLite·보고서 영속 저장</span></div></div>
      <p class="lead">비밀키는 Secrets Manager, 로그는 CloudWatch, 사람의 배포 접근은 루트 계정이 아닌 SSO·전용 IAM 역할을 사용합니다.</p>"""),
    ("15 · Release Decision", "기능은 완성, 배포는 아직 HOLD", """
      <div class="grid"><div class="card"><h3>완료된 통제</h3><ul><li>Experiment·비교·Trace·승인</li><li>반복성·RAG·비용·Red Team</li><li>CI 게이트·버전·드리프트</li></ul></div>
      <div class="card"><h3>실제 승인 조건</h3><ul><li>E2E 90.9 → 95 이상</li><li>Judge 81.2 → 95 이상</li><li>사람 최종 승인·운영 인증/TLS</li></ul></div></div>
      <p class="warn">테스트 기능 완성과 실제 서비스 배포 승인은 별개입니다.</p>"""),
    ("16 · Operating Rule", "앞으로 모든 개발은 이렇게 완료한다", """
      <div class="flow"><b>문제</b><i>→</i><b>분석</b><i>→</i><b>구현</b><i>→</i><b>웹 적용</b><i>→</i><b>검증</b><i>→</i><b>발표 기록</b></div>
      <ul><li>CLI 기능에는 웹 버튼·API·결과 화면을 함께 제공</li><li>웹 검증과 자동 테스트 없이는 완료 처리하지 않음</li>
      <li>공식 테스트마다 TXT·XML·HTML 증적과 실행 이력 생성</li><li>발표 원장·슬라이드는 작업 완료 시 갱신하고 키·개인정보는 비공개</li></ul>"""),
    ("17 · Closing", "생성 결과가 아니라<br><em>신뢰할 수 있는 과정</em>을 만들었습니다.", """
      <p class="lead">VOC 분석 → 단계 진단 → 기대 결과 평가 → 장애·보안 검증 → 독립 Judge → 배포 판단을 하나의 웹 QA 흐름으로 연결했습니다.</p>
      <div class="grid three"><div class="card"><b class="metric">6</b><span>전문 Agent</span></div>
      <div class="card"><b class="metric">100</b><span>품질 평가 총점</span></div>
      <div class="card"><b class="metric">Web</b><span>실행·검증·발표 통합</span></div></div>"""),
]

SLIDE_HTML = "".join(
    f'<section class="slide{" active" if index == 0 else ""}"><div class="eyebrow">{eyebrow}</div>'
    f'<h1>{title}</h1>{body}</section>'
    for index, (eyebrow, title, body) in enumerate(SLIDES)
)

PRESENTATION_PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/><title>VOC Improve 개발 발표</title>
<style>
:root{--navy:#061321;--panel:#102a44;--line:#31516f;--blue:#51a5ff;--cyan:#4ce0d2;--text:#eef7ff;--muted:#abc0d5;--good:#59db91;--warn:#ffc15c}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#183f65 0,var(--navy) 45%);color:var(--text);font-family:Inter,"Noto Sans KR","Malgun Gothic",sans-serif;overflow:hidden}a{color:#91caff}
.top{height:58px;display:flex;align-items:center;gap:12px;padding:0 20px;border-bottom:1px solid var(--line);background:rgba(4,15,27,.92)}.brand{font-weight:900}.spacer{flex:1}.top a,.top button,.controls button{border:1px solid var(--line);background:#143451;color:var(--text);border-radius:8px;padding:8px 11px;text-decoration:none;cursor:pointer}.live{color:var(--good);font-weight:800}
.deck{height:calc(100vh - 108px)}.slide{display:none;height:100%;padding:5vh 7vw 4vh;overflow:auto}.slide.active{display:block;animation:enter .25s ease-out}@keyframes enter{from{opacity:.2;transform:translateX(18px)}to{opacity:1;transform:none}}
h1{font-size:clamp(2rem,4vw,4rem);line-height:1.1;margin:.15em 0 .55em}h1 em{color:var(--cyan);font-style:normal}h3{color:var(--cyan);margin:.2em 0}.eyebrow{color:var(--cyan);font-weight:900;letter-spacing:.13em}.lead,p,li{font-size:clamp(1rem,1.5vw,1.45rem);line-height:1.55}.lead{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}.grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.card{border:1px solid var(--line);border-radius:14px;padding:18px 20px;background:linear-gradient(145deg,rgba(28,64,98,.9),rgba(11,32,53,.9))}.card>span{display:block;color:var(--muted);margin-top:7px}.metric{display:block;font-size:clamp(2rem,4vw,3.8rem);color:var(--cyan);line-height:1}
.flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:26px 0}.flow b{flex:1;min-width:110px;text-align:center;padding:14px 8px;border:1px solid #3b7199;border-radius:10px;background:#123756}.flow i{color:var(--cyan);font-size:1.4rem;font-style:normal}.timeline{border-left:3px solid var(--blue);padding-left:24px}.timeline b,strong{color:var(--good)}
table{width:100%;border-collapse:collapse;font-size:clamp(.85rem,1.2vw,1.15rem)}th,td{padding:10px;border:1px solid var(--line);text-align:left}th{background:#173c5e}.warn{color:var(--warn);font-weight:800}aside{display:none;margin-top:20px;border-left:4px solid var(--warn);padding:10px 14px;background:rgba(255,193,92,.09);color:#ffe1ac}body.notes aside{display:block}
.controls{height:50px;display:flex;align-items:center;justify-content:center;gap:12px;border-top:1px solid var(--line);background:rgba(4,15,27,.94)}.progress{width:min(360px,34vw);height:6px;background:#263f57;border-radius:9px;overflow:hidden}.progress span{display:block;height:100%;background:var(--cyan)}.hint{color:var(--muted);font-size:.82rem}
@media(max-width:800px){.grid,.grid.three{grid-template-columns:1fr}.slide{padding:28px 22px}.doc{display:none}}@media print{body{overflow:visible;background:#fff;color:#111}.top,.controls{display:none}.deck{height:auto}.slide{display:block!important;min-height:95vh;page-break-after:always;padding:5vh 5vw}.card,.flow b{color:#111;background:#fff;border-color:#777}.lead,.card>span{color:#444}aside{display:none!important}}
</style></head><body>
<header class="top"><div class="brand">VOC IMPROVE · DEVELOPMENT STORY</div><span id="liveState" class="live">● 상태 확인 중</span><div class="spacer"></div>
<a class="doc" href="/presentation/deck">오늘 PPTX</a><a class="doc" href="/presentation/material">발표 원고</a><a class="doc" href="/presentation/ledger">개발 원장</a><a class="doc" href="/presentation/principles">개발 원칙</a><a href="/">실제 데모</a>
<button type="button" onclick="toggleNotes()">발표자 노트</button><button type="button" onclick="window.print()">PDF 인쇄</button></header><main class="deck">""" + SLIDE_HTML + r"""</main>
<footer class="controls"><button id="prev" type="button">← 이전</button><span id="counter"></span><div class="progress"><span id="progress"></span></div><button id="next" type="button">다음 →</button><span class="hint">← → 이동 · N 노트 · F 전체화면</span></footer>
<script>
const slides=Array.from(document.querySelectorAll('.slide'));let current=0;
function show(index){current=Math.max(0,Math.min(slides.length-1,index));slides.forEach((s,i)=>s.classList.toggle('active',i===current));document.getElementById('counter').textContent=(current+1)+' / '+slides.length;document.getElementById('progress').style.width=((current+1)/slides.length*100)+'%';location.hash='slide-'+(current+1)}
function toggleNotes(){document.body.classList.toggle('notes')}document.getElementById('prev').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);
document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(current-1)}if(e.key==='Home')show(0);if(e.key==='End')show(slides.length-1);if(e.key.toLowerCase()==='n')toggleNotes();if(e.key.toLowerCase()==='f')document.documentElement.requestFullscreen?.()});
show(Number((location.hash.match(/slide-(\d+)/)||[])[1]||1)-1);
async function loadStatus(){try{const r=await fetch('/quality/status');const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.message||'상태 조회 실패');const ready=(d.agents||[]).filter(x=>x.ready).length;const assessment=d.deployment_assessment||{};document.getElementById('agentMetric').textContent=ready+'/6';document.getElementById('suiteMetric').textContent=(d.quality_suite?.passed||0)+'/'+(d.quality_suite?.total||0);document.getElementById('faultMetric').textContent=(d.fault_diagnosis?.passed||0)+'/'+(d.fault_diagnosis?.total||0);document.getElementById('liveState').textContent='● 웹·Agent '+ready+'/6';document.getElementById('liveDetail').textContent='배포 '+(assessment.overall_score??'-')+'/'+(assessment.minimum_score??95)+'점 · '+(assessment.label||'판단 대기')+' · API 키 값은 표시하지 않습니다.'}catch(e){document.getElementById('liveState').textContent='상태 연결 필요';document.getElementById('liveDetail').textContent=e.message||String(e)}}loadStatus();
</script></body></html>"""
