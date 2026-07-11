param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("train", "infer", "scenario", "timing", "powerbi", "all")]
    [string]$Task,

    [string]$InputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Avoid joblib hardware-detection warnings in portable Windows environments.
$env:LOKY_MAX_CPU_COUNT = [Environment]::ProcessorCount.ToString()

if (!(Test-Path "outputs")) {
    New-Item -ItemType Directory -Path "outputs" | Out-Null
}

$VenvPython = ".venv\Scripts\python.exe"
$Python = "python"
if (Test-Path $VenvPython) {
    & $VenvPython -c "import pandas, sklearn, joblib" *> $null
    if ($LASTEXITCODE -eq 0) {
        $Python = $VenvPython
    } else {
        Write-Warning "The local virtual environment failed its dependency health check; using Python from PATH."
    }
}

$TrainingInput = if ($InputPath) { $InputPath } else { "data/processed/fraud_transactions.csv" }
$InferenceInput = if ($InputPath) { $InputPath } else { "data/inference/fraud_inference_sample.csv" }

function Invoke-CheckedPython {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE`: $($Arguments -join ' ')"
    }
}

function Invoke-CheckedTask {
    param([Parameter(Mandatory = $true)][string]$ChildTask)
    & $PSCommandPath -Task $ChildTask
    if ($LASTEXITCODE -ne 0) {
        throw "Task '$ChildTask' failed with exit code $LASTEXITCODE."
    }
}

switch ($Task) {
    "train" {
        Invoke-CheckedPython @("fintech.py", "train", "--input", $TrainingInput,
            "--output", "outputs/fraud_scored_transactions.csv",
            "--model-out", "outputs/fraud_model.joblib",
            "--model-type", "hist_gradient_boosting",
            "--review-rate", "0.10",
            "--calibration-size", "0.20", "--test-size", "0.20",
            "--metrics-out", "outputs/train_metrics_report.csv")
    }
    "infer" {
        Invoke-CheckedPython @("score_daily.py", "--input", $InferenceInput,
            "--model", "outputs/fraud_model.joblib",
            "--output", "outputs/daily_scored_transactions.csv")
    }
    "scenario" {
        Invoke-CheckedPython @("scenario_simulator.py", "--input", "powerbi-data/payments.csv",
            "--output", "outputs/recovery_scenarios.csv")
    }
    "timing" {
        Invoke-CheckedPython @("retry_timing_analysis.py", "--input", "powerbi-data/payments.csv")
    }
    "powerbi" {
        Invoke-CheckedPython @("prepare_powerbi_tables.py")
    }
    "all" {
        Invoke-CheckedTask "train"
        Invoke-CheckedTask "scenario"
        Invoke-CheckedTask "timing"
        Invoke-CheckedTask "powerbi"
    }
}
