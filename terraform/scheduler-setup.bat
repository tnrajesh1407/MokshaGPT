@echo off
REM Standalone Cloud Scheduler Setup for Nifty 100 Precompute
REM Run this from Command Prompt: terraform\scheduler-setup.bat

set PROJECT_ID=bulkpoddesigns
set REGION=us-central1
set BACKEND_IMAGE=us-central1-docker.pkg.dev/bulkpoddesigns/mokshagpt/backend:latest
set SUPABASE_URL=https://juxudzuyaixpbgsmdccf.supabase.co
set SUPABASE_SERVICE_KEY=YOUR_SUPABASE_SERVICE_KEY
set SA_EMAIL=precompute-job-sa@%PROJECT_ID%.iam.gserviceaccount.com

echo ==========================================
echo Setting up Cloud Scheduler for Nifty 100
echo ==========================================

REM Enable required APIs
echo Enabling required APIs...
gcloud services enable cloudscheduler.googleapis.com --project=%PROJECT_ID%
gcloud services enable run.googleapis.com --project=%PROJECT_ID%

REM Create service account
echo Creating service account...
gcloud iam service-accounts create precompute-job-sa --display-name="Precompute Job Service Account" --project=%PROJECT_ID%

REM Grant permissions
echo Granting permissions...
gcloud projects add-iam-policy-binding %PROJECT_ID% --member="serviceAccount:%SA_EMAIL%" --role="roles/run.invoker" --condition=None

REM Create Cloud Run Job: incremental (every 15 min)
echo Creating Cloud Run Job: precompute-nifty100-incremental...
gcloud run jobs create precompute-nifty100-incremental --image=%BACKEND_IMAGE% --region=%REGION% --project=%PROJECT_ID% --service-account=%SA_EMAIL% --max-retries=1 --task-timeout=15m --cpu=2 --memory=2Gi --set-env-vars="SUPABASE_URL=%SUPABASE_URL%,SUPABASE_SERVICE_KEY=%SUPABASE_SERVICE_KEY%" --command=python --args=precompute_nifty100.py

REM Create Cloud Run Job: full (daily)
echo Creating Cloud Run Job: precompute-nifty100-full...
gcloud run jobs create precompute-nifty100-full --image=%BACKEND_IMAGE% --region=%REGION% --project=%PROJECT_ID% --service-account=%SA_EMAIL% --max-retries=1 --task-timeout=30m --cpu=2 --memory=2Gi --set-env-vars="SUPABASE_URL=%SUPABASE_URL%,SUPABASE_SERVICE_KEY=%SUPABASE_SERVICE_KEY%" --command=python --args="precompute_nifty100.py,--full"

REM Create Cloud Scheduler: incremental daily at 8 AM IST (upgrade to */15 when traffic grows)
echo Creating Cloud Scheduler: incremental daily job...
gcloud scheduler jobs create http precompute-15min --location=%REGION% --schedule="0 8 * * *" --time-zone="Asia/Kolkata" --uri="https://%REGION%-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/%PROJECT_ID%/jobs/precompute-nifty100-incremental:run" --http-method=POST --oauth-service-account-email=%SA_EMAIL% --project=%PROJECT_ID%

REM Create Cloud Scheduler: full daily at 6 AM IST
echo Creating Cloud Scheduler: daily full job...
gcloud scheduler jobs create http precompute-daily --location=%REGION% --schedule="0 6 * * *" --time-zone="Asia/Kolkata" --uri="https://%REGION%-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/%PROJECT_ID%/jobs/precompute-nifty100-full:run" --http-method=POST --oauth-service-account-email=%SA_EMAIL% --project=%PROJECT_ID%

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Test manually:
echo   gcloud run jobs execute precompute-nifty100-incremental --region=%REGION% --project=%PROJECT_ID%
echo   gcloud run jobs execute precompute-nifty100-full --region=%REGION% --project=%PROJECT_ID%
echo.
pause
