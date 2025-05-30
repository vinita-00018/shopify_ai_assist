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

# === Session State Init ===
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "input_text" not in st.session_state:
    st.session_state.input_text = ""
if "api_call" not in st.session_state:
    st.session_state.api_call = 1
if "shop" not in st.session_state:
    st.session_state.shop = ""
if "token" not in st.session_state:
    st.session_state.token = ""

# === Function: Call AI Agent and Execute Shopify Code ===
def handle_send():
    user_query = st.session_state.input_text.strip()
    if not user_query:
        return

    if not st.session_state.shop or not st.session_state.token:
        st.session_state.chat_history.append({"sender": "AI Bot", "content": "⚠️ Please enter both SHOP and ACCESS_TOKEN above."})
        return
    
     # 🔐 Ensure valid domain
    if not st.session_state.shop.endswith(".myshopify.com"):
        st.session_state.shop += ".myshopify.com"

    st.session_state.chat_history.append({"sender": "You", "content": user_query})
    time.sleep(10)

    # Construct question with dynamic shop/token
    question = f"""SHOP={st.session_state.shop}
ACCESS_TOKEN={st.session_state.token}
You are a Python coding agent that generates code using the requests library to call the Shopify Admin REST API (2023-10).
Use requests with the shop and token from environment variables.
Only return clean Python code (no markdown, no explanations,no loop,no conditional statement).
The last line must be: print(final_output)
The variable final_output should hold the data to return
prompt: {user_query}"""

    url = "https://api.indiaagi.ai/test/sse"
    params = {
        "question": question,
        "rounds": 1,
        "model": "OpenAI"
    }

    clean_code = ""
    try:
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
                            # Replace environment variable usage with actual values
                            code = re.sub(r'SHOP\s*=\s*os.getenv\([\'"].+?[\'"]\)', f'SHOP = "{st.session_state.shop}"', code)
                            code = re.sub(r'ACCESS_TOKEN\s*=\s*os.getenv\([\'"].+?[\'"]\)', f'ACCESS_TOKEN = "{st.session_state.token}"', code)
                            clean_code = code
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

        os.environ["SHOP"] = st.session_state.shop
        os.environ["ACCESS_TOKEN"] = st.session_state.token

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

        if final_output:
            try:
                parsed = json.loads(final_output)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(final_output)
                except Exception:
                    parsed = final_output
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

        st.session_state.chat_history.append({"sender": "AI Bot", "content": beautified})
    except Exception as e:
        sys.stdout = sys_stdout_backup
        if "Failed to resolve" in str(e) and st.session_state.api_call < 3:
            st.session_state.api_call += 1
            handle_send()
            return
        else:
            st.session_state.chat_history.append({"sender": "AI Bot", "content": f"❌ Code execution error: {str(e)}"})

    st.session_state.input_text = ""

# === Function: Clear Chat ===
def clear_chat():
    st.session_state.chat_history = []
    st.session_state.input_text = ""
    st.session_state.api_call = 1

# === UI Layout ===
st.title("🛍️ AI + Shopify Assistant")

# Manual SHOP + TOKEN inputs
st.text_input("🛒 Shopify Store Name (e.g., qeapptest.myshopify.com):", key="shop")
st.text_input("🔐 Access Token:", type="password", key="token")

# Chat History Display
for message in st.session_state.chat_history:
    st.markdown(f"**{message['sender']}**: {message['content']}")

# Input & Buttons
st.text_input("You:", key="input_text", placeholder="Ask about orders, customers, products, etc...")
st.button("Send", on_click=handle_send)
st.button("🧹 Clear Chat", on_click=clear_chat)
