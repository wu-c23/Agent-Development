# run_all_once.ps1 — Windows PowerShell 采集脚本
# 等价于 scripts/run_all_once.sh，用于 Windows 环境一键运行所有爬虫
param(
    [switch]$EnableQidian = $false
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot\..

try {
    if ($EnableQidian -or ($env:ENABLE_QIDIAN -eq "true")) {
        Write-Host "Running qidian_trends spider..."
        scrapy crawl qidian_trends
    } else {
        Write-Host "Skip qidian_trends (use -EnableQidian or set ENABLE_QIDIAN=true to enable)."
    }

    Write-Host "Running zongheng_trends spider..."
    scrapy crawl zongheng_trends
} finally {
    Pop-Location
}

Write-Host "All crawlers finished."
