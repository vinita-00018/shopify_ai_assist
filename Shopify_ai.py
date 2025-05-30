import streamlit as st
import requests
import json
import os
import io
import sys
import re
from datetime import datetime, timedelta
import ast
import time
import certifi

# === Session State Init ===
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "input_text" not in st.session_state:
    st.session_state.input_text = ""
if "api_call" not in st.session_state:
    st.session_state.api_call = 1

# === Function: Call AI Agent and Execute Shopify Code ===
def handle_send():
    user_query = st.session_state.input_text.strip()
    if not user_query:
        return

    st.session_state.chat_history.append({"sender": "You", "content": user_query})
    time.sleep(30)
    # Call IndiaAGI SSE API
    url = "https://api.indiaagi.ai/test/sse"
    params = {
        "question": f"""SHOP=qeapptest
ACCESS_TOKEN=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

You are a Python coding agent that generates code using the requests library to call the Shopify Admin REST API (2023-10).
Use requests with the shop and token from environment variables.
Only return clean Python code (no markdown, no explanations,no loop,no conditional statement).
The last line must be: print(final_output)
The variable final_output should hold the data to return

prompt: {user_query}""",
        "rounds": 1,
        "model": "OpenAI"
    }

    clean_code = ""
    try:

        # with requests.get(url, params=params, stream=True, verify=certifi.where(), timeout=(5, 10)) as response:
        with requests.get(url, params=params, stream=True, verify=False) as response:
            response.raise_for_status()
            buffer = {}
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    if buffer.get("id") == "2":
                        data_json = buffer.get("data")
                        if data_json:
                            data_obj = json.loads(data_json)
                            code = data_obj.get("response")
                            code = re.sub(r'SHOP\s*=\s*os.getenv\([\'"].+?[\'"]\)', 'SHOP = "qeapptest"', code)
                            code = re.sub(r'ACCESS_TOKEN\s*=\s*os.getenv\([\'"].+?[\'"]\)', 'ACCESS_TOKEN = "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"', code)
                            clean_code = code
                            # print(clean_code)
                            break
                    buffer = {}
                    continue
                if line.startswith("id:"):
                    buffer["id"] = line[len("id:"):].strip()
                elif line.startswith("data:"):
                    buffer["data"] = line[len("data:"):].strip()
    except Exception as e:
        st.session_state.chat_history.append({"sender": "AI Bot", "content": f"❌ API error: {str(e)}"})
        return

    # Execute the clean Python code and capture output
    try:
        output_buffer = io.StringIO()
        sys_stdout_backup = sys.stdout
        sys.stdout = output_buffer

        # os.environ["SHOP"] = "qeapptest"
        os.environ["SHOP"] = "qeapptest.myshopify.com"

        os.environ["ACCESS_TOKEN"] = "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"

        exec_globals = {
            "__builtins__": __builtins__,
            "os": os,
            "requests": requests,
            "datetime": datetime,
            "timedelta": timedelta
        }
        exec(clean_code, exec_globals)

        sys.stdout = sys_stdout_backup
        final_output = output_buffer.getvalue().strip()
        # st.session_state.chat_history.append({"sender": "AI Bot", "content": final_output})
        if final_output:
            try:
                parsed = json.loads(final_output)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(final_output)
                except Exception as e:
                    parsed = final_output  # fallback to raw string
        else:
            st.session_state.chat_history.append({"sender": "AI Bot", "content": "❌ Empty output from executed code."})
            return
        # Beautify output
        if isinstance(parsed, list):
            beautified = "\n".join(
                f"- **{item.get('title', str(item))}** — ₹{item.get('price', '')}"
                if isinstance(item, dict) else f"- {item}"
                for item in parsed
            )
        elif isinstance(parsed, dict):
            beautified = "\n".join(f"**{k}**: {v}" for k, v in parsed.items())
        else:
            beautified = str(parsed)

        # Add to chat history
        st.session_state.chat_history.append({"sender": "AI Bot", "content": beautified})
    except Exception as e:
        sys.stdout = sys_stdout_backup
        error_msg = str(e)
        # Detect host resolution error
        if "Failed to resolve" in error_msg and st.session_state.api_call < 3:
            st.session_state.api_call += 1
            # st.session_state.chat_history.append({"sender": "AI Bot", "content": "🔁 Retrying due to connection error..."})
            handle_send()  # Retry once
            return
        else:
            st.session_state.chat_history.append({"sender": "AI Bot", "content": f"❌ Code execution error: {error_msg}"})

    st.session_state.input_text = ""

# === Function: Clear Chat ===
def clear_chat():
    st.session_state.chat_history = []
    st.session_state.input_text = ""
    st.session_state.api_call = 1

# === UI Layout ===
st.title("🛍️ AI + Shopify Assistant")

# Chat History Display
for message in st.session_state.chat_history:
    st.markdown(f"**{message['sender']}**: {message['content']}")

# Input & Buttons
st.text_input("You:", key="input_text", placeholder="Ask about orders, customers, products, etc...")
st.button("Send", on_click=handle_send)
st.button("🧹 Clear Chat", on_click=clear_chat)
