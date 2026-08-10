param(
    [string]$OutputPptx = "",
    [string]$OutputPdf = ""
)

$ErrorActionPreference = "Stop"
$root = if ($PSScriptRoot) {
    (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    (Resolve-Path ".").Path
}
if (-not $OutputPptx) { $OutputPptx = Join-Path $root "docs\VOC_Improve_10분_발표자료_20260716.pptx" }
if (-not $OutputPdf) { $OutputPdf = Join-Path $root "docs\VOC_Improve_10분_발표자료_20260716.pdf" }

function RGB([int]$r, [int]$g, [int]$b) { return $r + 256 * $g + 65536 * $b }
$NAVY = RGB 12 52 96; $BLUE = RGB 31 101 174; $TEAL = RGB 15 139 141
$SKY = RGB 224 240 252; $INK = RGB 20 41 65; $MUTED = RGB 91 111 132
$WHITE = RGB 255 255 255; $GREEN = RGB 20 132 92; $RED = RGB 205 55 68
$AMBER = RGB 235 166 35; $LIGHT = RGB 246 249 253; $LINE = RGB 204 220 237

function Add-Box($slide, [double]$x, [double]$y, [double]$w, [double]$h, [int]$fill, [int]$line = 0, [double]$radius = 5) {
    $shapeType = if ($radius -gt 0) { 5 } else { 1 }
    $s = $slide.Shapes.AddShape($shapeType, $x, $y, $w, $h)
    $s.Fill.ForeColor.RGB = $fill
    $s.Line.ForeColor.RGB = if ($line) { $line } else { $fill }
    return $s
}

function Add-Text($slide, [string]$text, [double]$x, [double]$y, [double]$w, [double]$h, [double]$size = 18, [int]$color = 0, [bool]$bold = $false, [int]$align = 1) {
    $s = $slide.Shapes.AddTextbox(1, $x, $y, $w, $h)
    $s.TextFrame.MarginLeft = 0; $s.TextFrame.MarginRight = 0
    $s.TextFrame.MarginTop = 0; $s.TextFrame.MarginBottom = 0
    $s.TextFrame.WordWrap = -1
    $r = $s.TextFrame.TextRange
    $r.Text = $text
    $r.Font.Name = "맑은 고딕"; $r.Font.Size = $size
    $r.Font.Color.RGB = if ($color) { $color } else { $INK }
    $r.Font.Bold = if ($bold) { -1 } else { 0 }
    $r.ParagraphFormat.Alignment = $align
    return $s
}

function Add-Title($slide, [string]$section, [string]$title, [int]$number) {
    Add-Box $slide 0 0 960 8 $TEAL 0 0 | Out-Null
    Add-Text $slide $section.ToUpper() 48 30 500 22 11 $TEAL $true | Out-Null
    Add-Text $slide $title 48 56 820 48 28 $NAVY $true | Out-Null
    Add-Text $slide ("{0:00}" -f $number) 878 38 38 30 14 $MUTED $true 3 | Out-Null
}

function Add-Footer($slide, [string]$text = "VOC_Improve · Multi-Agent QA") {
    Add-Text $slide $text 48 512 650 16 9 $MUTED $false | Out-Null
    Add-Text $slide "2026.07.16" 820 512 92 16 9 $MUTED $false 3 | Out-Null
}

function Add-Metric($slide, [string]$value, [string]$label, [double]$x, [double]$y, [double]$w, [int]$accent = 0) {
    if (-not $accent) { $accent = $BLUE }
    Add-Box $slide $x $y $w 88 $WHITE $LINE | Out-Null
    Add-Box $slide $x $y 6 88 $accent 0 0 | Out-Null
    Add-Text $slide $value ($x + 20) ($y + 15) ($w - 30) 34 25 $accent $true | Out-Null
    Add-Text $slide $label ($x + 20) ($y + 54) ($w - 30) 20 11 $MUTED $false | Out-Null
}

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = -1
$pres = $ppt.Presentations.Add()
$pres.PageSetup.SlideWidth = 960
$pres.PageSetup.SlideHeight = 540

try {
    # 1
    $s = $pres.Slides.Add(1, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Box $s 0 0 960 540 $NAVY 0 0 | Out-Null
    Add-Box $s 52 46 122 28 $TEAL 0 4 | Out-Null
    Add-Text $s "QUALITY ENGINEERING" 63 52 105 16 9 $WHITE $true 2 | Out-Null
    Add-Text $s "VOC_Improve" 52 112 650 58 38 $WHITE $true | Out-Null
    Add-Text $s "멀티 에이전트 QA 품질검증" 52 174 780 48 28 (RGB 137 211 224) $true | Out-Null
    Add-Text $s "생성–내부검증–독립 Judge–정형 테스트로 이어지는 품질 게이트" 54 239 770 34 16 (RGB 210 225 240) $false | Out-Null
    Add-Metric $s "30/30" "자동 품질 테스트" 52 326 190 $TEAL
    Add-Metric $s "18/18" "라이브 E2E" 256 326 190 $GREEN
    Add-Metric $s "89점" "Anthropic Judge" 460 326 190 $BLUE
    Add-Metric $s "HOLD" "배포 종합판정" 664 326 190 $AMBER
    Add-Text $s "2026. 07. 16 · VOC_Improve 팀" 54 480 800 24 12 (RGB 180 202 225) $false | Out-Null

    # 2
    $s = $pres.Slides.Add(2, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "01 · WHY" "품질은 3가지 질문으로 분리해 검증했습니다" 2
    $cards = @(
        @("01", "요약 정확성", "불만의 사실·원인·영향을`n빠짐없이 압축했는가", $BLUE),
        @("02", "개선안 타당성", "원인과 직접 연결되고`n실행 가능한가", $TEAL),
        @("03", "모델 독립성", "서로 다른 모델로 평가해도`n판단이 유지되는가", $AMBER)
    )
    for ($i=0; $i -lt 3; $i++) {
        $x = 48 + $i * 296; $c = $cards[$i]
        Add-Box $s $x 145 264 238 $WHITE $LINE | Out-Null
        Add-Text $s $c[0] ($x+20) 165 52 28 16 $c[3] $true | Out-Null
        Add-Text $s $c[1] ($x+20) 211 220 34 21 $NAVY $true | Out-Null
        Add-Text $s $c[2] ($x+20) 267 220 70 15 $INK $false | Out-Null
        Add-Box $s ($x+20) 352 72 5 $c[3] 0 0 | Out-Null
    }
    Add-Text $s "핵심 원칙  |  PASS 건수와 응답 품질 점수는 별도로 판단" 48 424 856 34 17 $NAVY $true 2 | Out-Null
    Add-Footer $s

    # 3
    $s = $pres.Slides.Add(3, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "02 · ARCHITECTURE" "답변을 만든 모델이 자기 답변만 채점하지 않게" 3
    $labels = @(
        @("VOC 테스트 데이터", "일반·복합·위험 입력"),
        @("OpenAI 생성", "Summarizer · Improver"),
        @("내부 품질 점검", "Evaluator · Critic"),
        @("Anthropic Judge", "독립 LLM 평가"),
        @("품질 판정", "점수 · PASS/FAIL · 근거")
    )
    for ($i=0; $i -lt 5; $i++) {
        $x = 34 + $i * 185
        $fill = if ($i -eq 3) { RGB 235 246 242 } elseif ($i -eq 4) { RGB 255 246 226 } else { $WHITE }
        $accent = if ($i -eq 3) { $GREEN } elseif ($i -eq 4) { $AMBER } else { $BLUE }
        Add-Box $s $x 170 156 150 $fill $LINE | Out-Null
        Add-Text $s ($i+1).ToString("00") ($x+16) 186 32 20 12 $accent $true | Out-Null
        Add-Text $s $labels[$i][0] ($x+16) 224 124 42 17 $NAVY $true | Out-Null
        Add-Text $s $labels[$i][1] ($x+16) 274 124 36 11 $MUTED $false | Out-Null
        if ($i -lt 4) { Add-Text $s "→" ($x+157) 221 28 34 22 $TEAL $true 2 | Out-Null }
    }
    Add-Box $s 142 365 676 62 (RGB 232 242 252) (RGB 181 211 239) | Out-Null
    Add-Text $s "pytest는 전 구간의 정형 규칙 · 예외 처리 · API 계약을 독립 검증" 164 385 632 24 15 $NAVY $true 2 | Out-Null
    Add-Footer $s

    # 4
    $s = $pres.Slides.Add(4, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "03 · MULTI-AGENT" "6개 Agent가 한 단계씩 책임지고 Trace를 남깁니다" 4
    $agents = @(
        @("Interpreter", "의도·모호성 해석", "01"), @("Retriever", "정책·사례 근거 검색", "02"),
        @("Summarizer", "사실·감정 분리 요약", "03"), @("Evaluator", "후보 점수화·선택", "04"),
        @("Critic", "누락·환각·위험 지적", "05"), @("Improver", "실행 가능한 개선안", "06")
    )
    for ($i=0; $i -lt 6; $i++) {
        $col=$i%3; $row=[math]::Floor($i/3); $x=48+$col*292; $y=142+$row*142
        Add-Box $s $x $y 264 112 $WHITE $LINE | Out-Null
        $agentAccent = if ($i -lt 3) { $BLUE } else { $TEAL }
        Add-Box $s $x $y 52 112 $agentAccent 0 0 | Out-Null
        Add-Text $s $agents[$i][2] ($x+10) ($y+40) 32 28 17 $WHITE $true 2 | Out-Null
        Add-Text $s $agents[$i][0] ($x+70) ($y+22) 178 28 17 $NAVY $true | Out-Null
        Add-Text $s $agents[$i][1] ($x+70) ($y+60) 178 24 12 $MUTED $false | Out-Null
    }
    Add-Text $s "Trace 증적: 단계별 입력 → 출력 → 평가 근거 → 보완 결과" 48 438 848 28 15 $NAVY $true 2 | Out-Null
    Add-Footer $s

    # 5
    $s = $pres.Slides.Add(5, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "04 · TEST DESIGN" "실제 고객 입력을 닮은 10개 유형으로 경계를 검증" 5
    $left = @("일반 불만  |  핵심 내용 요약", "복합 불만  |  여러 불만 누락 방지", "짧고 모호  |  근거 없는 추측 방지", "긴 불만  |  핵심 정보 압축", "감정 표현  |  감정과 사실 구분")
    $right = @("오탈자·구어체  |  의미 복원", "개인정보  |  이름·연락처 마스킹", "위험 표현  |  과잉 판단 방지", "정상·칭찬  |  불만 오분류 방지", "입력 이상  |  안전한 오류 처리")
    for ($i=0; $i -lt 5; $i++) {
        $y=140+$i*62
        Add-Box $s 48 $y 410 46 $WHITE $LINE | Out-Null
        Add-Text $s ("{0:00}" -f ($i+1)) 62 ($y+13) 30 18 11 $BLUE $true | Out-Null
        Add-Text $s $left[$i] 104 ($y+11) 336 24 13 $INK $(($i -eq 1) -or ($i -eq 2)) | Out-Null
        Add-Box $s 502 $y 410 46 $WHITE $LINE | Out-Null
        Add-Text $s ("{0:00}" -f ($i+6)) 516 ($y+13) 30 18 11 $TEAL $true | Out-Null
        Add-Text $s $right[$i] 558 ($y+11) 336 24 13 $INK $(($i -eq 1) -or ($i -eq 2)) | Out-Null
    }
    Add-Text $s "각 유형을 요약 정확성 · 개선안 타당성 · 안전성으로 독립 채점" 48 462 864 26 14 $NAVY $true 2 | Out-Null
    Add-Footer $s

    # 6
    $s = $pres.Slides.Add(6, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "05 · CROSS VALIDATION" "모델 조합을 바꿔 자기평가 편향을 확인" 6
    $headers=@("실험군","생성 모델","평가 모델","목적","현재 증적")
    $widths=@(90,150,150,260,190); $x0=48; $y0=140; $x=$x0
    for($i=0;$i -lt 5;$i++){ Add-Box $s $x $y0 $widths[$i] 42 $NAVY 0 0|Out-Null; Add-Text $s $headers[$i] ($x+8) ($y0+11) ($widths[$i]-16) 20 12 $WHITE $true 2|Out-Null; $x+=$widths[$i] }
    $rows=@(
        @("A","OpenAI","Anthropic","기본 독립 품질검증","실측: E2E 18/18 · 89점"),
        @("B","Anthropic","OpenAI","역할 변경 품질 유지","추가 실측 대상"),
        @("C","OpenAI","OpenAI","동일 모델 편향 비교","비교 기준"),
        @("D","Anthropic","Anthropic","동일 모델 편향 비교","비교 기준")
    )
    for($r=0;$r -lt 4;$r++){ $x=$x0; $y=$y0+42+$r*56; for($c=0;$c -lt 5;$c++){ $fill=if($r -eq 0){RGB 232 247 241}elseif($r%2){$WHITE}else{RGB 241 246 252}; Add-Box $s $x $y $widths[$c] 56 $fill $LINE 0|Out-Null; $color=if($r -eq 0 -and $c -eq 4){$GREEN}else{$INK}; Add-Text $s $rows[$r][$c] ($x+8) ($y+17) ($widths[$c]-16) 24 11 $color $(($c -eq 0)-or($r -eq 0 -and $c -eq 4)) 2|Out-Null; $x+=$widths[$c] } }
    Add-Box $s 48 428 840 48 (RGB 255 246 226) (RGB 244 207 131) | Out-Null
    Add-Text $s "발표 원칙: 실행하지 않은 조합은 완료로 주장하지 않고, 추가 검증 범위로 명시" 68 442 800 22 13 $INK $true 2 | Out-Null
    Add-Footer $s

    # 7
    $s = $pres.Slides.Add(7, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "06 · RESULTS" "정형 성공률은 높지만, 응답 품질 점수는 별도 관리" 7
    Add-Metric $s "30/30" "자동 품질 테스트" 48 136 198 $GREEN
    Add-Metric $s "35/35" "종합 시나리오" 262 136 198 $GREEN
    Add-Metric $s "9/9" "장애 허용성" 476 136 198 $GREEN
    Add-Metric $s "20/20" "OWASP 보안" 690 136 198 $GREEN
    Add-Metric $s "5/5" "반복 안정성" 48 246 198 $GREEN
    Add-Metric $s "18/18" "라이브 E2E · 90.6점" 262 246 198 $BLUE
    Add-Metric $s "89점" "Anthropic 독립 Judge" 476 246 198 $BLUE
    Add-Metric $s "2/3" "CI 품질 게이트" 690 246 198 $AMBER
    Add-Box $s 48 378 840 74 (RGB 232 242 252) (RGB 181 211 239) | Out-Null
    Add-Text $s "PASS = 기능·규칙 충족   ≠   95점 = 배포 품질 기준 충족" 70 396 796 26 19 $NAVY $true 2 | Out-Null
    Add-Text $s "증적 기준: 2026-07-15~16 최신 결과 파일" 70 426 796 17 10 $MUTED $false 2 | Out-Null
    Add-Footer $s

    # 8
    $s = $pres.Slides.Add(8, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "07 · QUALITY GATE" "평균 96.7점이어도 필수 게이트가 실패하면 배포 보류" 8
    $gateRows=@(
        @("자동 품질", "30/30", "100점", "PASS", $GREEN),
        @("OWASP 보안", "20/20", "100점", "PASS", $GREEN),
        @("오프라인 E2E", "1/1", "90.2점 < 95점", "FAIL", $RED)
    )
    for($i=0;$i -lt 3;$i++){ $y=140+$i*72; Add-Box $s 48 $y 590 56 $WHITE $LINE|Out-Null; Add-Text $s $gateRows[$i][0] 68 ($y+16) 170 24 14 $NAVY $true|Out-Null; Add-Text $s $gateRows[$i][1] 250 ($y+16) 100 24 13 $INK $false 2|Out-Null; Add-Text $s $gateRows[$i][2] 360 ($y+16) 160 24 13 $INK $true 2|Out-Null; Add-Text $s $gateRows[$i][3] 544 ($y+16) 70 24 13 $gateRows[$i][4] $true 2|Out-Null }
    Add-Box $s 678 140 210 200 (RGB 255 246 226) (RGB 244 207 131) | Out-Null
    Add-Text $s "종합판정" 700 166 166 22 12 $MUTED $true 2 | Out-Null
    Add-Text $s "HOLD" 700 207 166 52 34 $AMBER $true 2 | Out-Null
    Add-Text $s "조건부 배포 보류" 700 276 166 24 14 $NAVY $true 2 | Out-Null
    Add-Box $s 48 382 840 76 (RGB 250 236 238) (RGB 232 177 184) | Out-Null
    Add-Text $s "개선 → 동일 데이터 재시험 → 독립 Judge → Human Review → 95점 이상 시 승인" 70 402 796 28 16 $RED $true 2 | Out-Null
    Add-Footer $s

    # 9
    $s = $pres.Slides.Add(9, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "08 · DEFECT & EVIDENCE" "결함은 원인–조치–재시험–증적으로 닫았습니다" 9
    $issues=@(
        @("상세 버튼 무응답", "이벤트·데이터 연결 보완"),
        @("내부 ID·영문 코드 노출", "QA용 한글 표시명 적용"),
        @("필터·입력 박스 겹침", "반응형 Grid·폭 제한"),
        @("포트 8000 중복", "기존 프로세스 확인·단일 실행")
    )
    for($i=0;$i -lt 4;$i++){ $y=132+$i*68; Add-Box $s 48 $y 394 52 $WHITE $LINE|Out-Null; Add-Text $s "결함" 62 ($y+16) 42 18 10 $RED $true|Out-Null; Add-Text $s $issues[$i][0] 112 ($y+13) 312 24 13 $INK $true|Out-Null; Add-Text $s "→" 452 ($y+13) 32 24 18 $TEAL $true 2|Out-Null; Add-Box $s 492 $y 396 52 (RGB 232 247 241) (RGB 184 224 207)|Out-Null; Add-Text $s $issues[$i][1] 510 ($y+13) 358 24 13 $GREEN $true|Out-Null }
    Add-Metric $s "89/89" "전체 웹 회귀 테스트 PASS" 48 424 260 $GREEN
    Add-Box $s 330 424 558 88 $NAVY 0 | Out-Null
    Add-Text $s "증적 산출물" 350 439 120 20 11 (RGB 137 211 224) $true | Out-Null
    Add-Text $s "TXT · XML · HTML · JUnit · CSV · JSON · Word · 감사 이력" 350 469 510 24 14 $WHITE $true | Out-Null
    Add-Footer $s

    # 10
    $s = $pres.Slides.Add(10, 12); $s.Background.Fill.ForeColor.RGB = $LIGHT
    Add-Title $s "09 · CONCLUSION" "구현 완료, 품질 기준은 정직하게 HOLD" 10
    Add-Box $s 48 136 400 254 (RGB 232 247 241) (RGB 184 224 207) | Out-Null
    Add-Text $s "확보한 것" 70 160 340 28 19 $GREEN $true | Out-Null
    Add-Text $s "✓ 6-Agent 역할·Trace`n✓ 생성 모델과 독립 Judge 분리`n✓ 단위·예외·통합·E2E·보안`n✓ 정량 결과와 감사 가능한 증적" 72 210 334 140 15 $INK $false | Out-Null
    Add-Box $s 480 136 408 254 (RGB 255 246 226) (RGB 244 207 131) | Out-Null
    Add-Text $s "다음 조건" 502 160 340 28 19 $AMBER $true | Out-Null
    Add-Text $s "1. E2E 90.2 → 95점 이상`n2. B·C·D 교차검증 추가 실측`n3. 동일 데이터 재시험`n4. Human Review 최종 승인" 504 210 338 140 15 $INK $false | Out-Null
    Add-Box $s 48 420 840 68 $NAVY 0 | Out-Null
    Add-Text $s "품질을 증명하는 시스템 — 실패를 숨기지 않는 배포 판단" 70 440 796 28 20 $WHITE $true 2 | Out-Null
    Add-Footer $s "Q&A · 실제 Trace와 증적 화면으로 답변드리겠습니다"

    $pres.SaveAs($OutputPptx, 24)
    $pres.SaveAs($OutputPdf, 32)
}
finally {
    $pres.Close()
    $ppt.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
}

Write-Output "PPTX=$OutputPptx"
Write-Output "PDF=$OutputPdf"
