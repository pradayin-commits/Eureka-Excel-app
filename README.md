
# EUREKA — Cloud App (Streamlit)

This is a web version of EUREKA (no `.exe`). Users upload two CSVs, compare, and download an Excel report.

## 1) Deploy on Streamlit Community Cloud (free)
1. Push this folder to a **public GitHub repo**.
2. Go to https://share.streamlit.io/ → "New app".
3. Select your repo/branch and set **Main file path**: `streamlit_app.py`.
4. Click Deploy. Done. (App URL will be like `https://yourname-eureka.streamlit.app`)

## 2) Deploy on Hugging Face Spaces (free)
1. Create a new Space → **Streamlit** template.
2. Upload all files. Ensure `requirements.txt` is present.
3. Set the entry point to `streamlit_app.py`.
4. Click "Restart" → the Space will build and run.

## 3) Deploy on Render (free tier)
1. Create a new **Web Service**.
2. Link to your GitHub repo.
3. Runtime: Python.
4. Build command:
   ```
   pip install -r requirements.txt
   ```
5. Start command:
   ```
   streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
   ```

## 4) Deploy on Cloud Run (Google) or Azure App Service
- Use the same start command as above.
- For Cloud Run, add a Dockerfile (Render's command also works with a simple Dockerfile).

## Notes
- Decimal option: by default trailing zeros are ignored; enable strict decimal comparison from the sidebar.
- Optional key columns: when supplied, the app shows **cell-level** diffs on shared keys; otherwise it compares by full-row content/hash.
- Output: click **Download Excel Report** to get a multi-sheet `.xlsx` with summary and differences.

Branding images `E.png` and `Bosch.png` are included; update as needed.
