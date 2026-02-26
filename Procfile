# Procfile — used by Railway, Render, Heroku
# Run both FastAPI backend and Streamlit frontend together

web: uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
streamlit: streamlit run web.py --server.port ${STREAMLIT_PORT:-8501} --server.headless true
