param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("train", "infer", "benchmark")]
    [string]$Task,

    [string]$InputPath = "fintech_fraud_data.csv"
)

if (!(Test-Path "outputs")) {
    New-Item -ItemType Directory -Path "outputs" | Out-Null
}

switch ($Task) {
    "train" {
        python fintech.py train `
            --input $InputPath `
            --output outputs/fraud_model_output.csv `
            --model-out outputs/fraud_model.joblib `
            --model-type hist_gradient_boosting `
            --evaluation-mode time `
            --test-size 0.25 `
            --metrics-out outputs/train_metrics_report.csv
    }
    "infer" {
        python score_daily.py `
            --input $InputPath `
            --model outputs/fraud_model.joblib `
            --output outputs/daily_fraud_predictions.csv
    }
    "benchmark" {
        python benchmark_models.py `
            --input $InputPath `
            --output outputs/model_benchmark_results.csv `
            --topk-frac 0.05
    }
}
