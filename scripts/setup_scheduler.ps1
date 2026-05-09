# setup_scheduler.ps1 — Windows 작업 스케줄러 일별/주별/월별 등록
# 실행: PowerShell에서  .\scripts\setup_scheduler.ps1

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python      = (Get-Command python -ErrorAction SilentlyContinue).Source
$Script      = Join-Path $ProjectRoot "scripts\auto_update.py"

if (-not $Python) {
    Write-Host "ERROR: Python을 찾을 수 없습니다." -ForegroundColor Red; exit 1
}

Write-Host "=" * 58
Write-Host "  위밋모빌리티 데이터 자동 갱신 스케줄러 등록"
Write-Host "=" * 58
Write-Host "  Python : $Python"
Write-Host "  스크립트: $Script"
Write-Host ""

function Register-UpdateTask {
    param(
        [string]$TaskName,
        [string]$Mode,
        [string]$TriggerDesc,
        $Trigger
    )

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $Action = New-ScheduledTaskAction `
        -Execute $Python `
        -Argument "`"$Script`" --mode $Mode" `
        -WorkingDirectory $ProjectRoot

    $Settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew

    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action -Trigger $Trigger `
        -Settings $Settings -Principal $Principal `
        -Description "위밋모빌리티: $Mode 데이터 자동 갱신" `
        -Force | Out-Null

    Write-Host "  ✅ [$TaskName]  $TriggerDesc" -ForegroundColor Green
}

# 1. 일별: 환율 + 유가 (매일 오전 8:30)
Register-UpdateTask `
    -TaskName "WemetMobility_Daily" `
    -Mode "daily" `
    -TriggerDesc "매일 08:30 — 환율(frankfurter/ECOS) + 유가(FRED/ECOS)" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "08:30")

# 2. 주별: 운임지수 + 뉴스 + 환율·유가 (매주 월요일 오전 9:00)
#    월요일: KCCI·KUWI·KUEI 주간 발표일 (한국해운거래소)
Register-UpdateTask `
    -TaskName "WemetMobility_Weekly" `
    -Mode "weekly" `
    -TriggerDesc "매주 월요일 09:00 — 운임지수 XLS 합치기 + 뉴스 + 환율·유가" `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:00")

# 3. 월별: 물동량 + 전체 (매월 2일 오전 9:30)
#    2일: 전월 통계 발표 시점 대기
Register-UpdateTask `
    -TaskName "WemetMobility_Monthly" `
    -Mode "monthly" `
    -TriggerDesc "매월 2일 09:30 — 부산항 물동량(NLIC) + 전체 갱신" `
    -Trigger (New-ScheduledTaskTrigger -Monthly -DaysOfMonth 2 -At "09:30")

Write-Host ""
Write-Host "=" * 58
Write-Host "  등록 완료 — 총 3개 작업"
Write-Host "=" * 58
Write-Host ""
Write-Host "[ 즉시 테스트 ]"
Write-Host "  python scripts/auto_update.py --mode daily"
Write-Host "  python scripts/auto_update.py --mode weekly"
Write-Host ""
Write-Host "[ XLS 파일 수동 합치기 ]"
Write-Host "  # 운임지수 (KCCI/KUWI/KUEI) XLS:"
Write-Host "  python scripts/auto_update.py --combine-freight"
Write-Host ""
Write-Host "  # 부산항 물동량 (NLIC) Excel:"
Write-Host "  python scripts/auto_update.py --combine-nlic"
Write-Host ""
Write-Host "[ 스케줄러 확인/삭제 ]"
Write-Host "  Get-ScheduledTask | Where-Object { `$_.TaskName -like 'WemetMobility*' }"
Write-Host "  Unregister-ScheduledTask -TaskName 'WemetMobility_Daily'"
