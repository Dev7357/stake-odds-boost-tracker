# Stake Automatic Boost Monitor

Deployable Streamlit app for an authorized Stake Sports Data API key.

## Important limitation
Stake's promotion page says the boosted market is selected by Stake and shown in yellow, and that boost values/availability can vary by user and event. The public Sports Data API docs list sports, fixtures, and odds endpoints, but do not document a yellow Odds Boost field. This app therefore only reports a **confirmed** boost when the API response explicitly contains boost/promotion metadata; it never treats a normal price movement as a confirmed boost.

## Deploy
1. Upload these files to GitHub.
2. Deploy the repository on Streamlit Community Cloud or another Streamlit host.
3. Add `STAKE_API_KEY` as a secret/environment variable.
4. Open the generated URL on your Samsung phone and add it to the home screen.

Never provide a Stake password or private session cookie.
