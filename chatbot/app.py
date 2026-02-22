import json
import requests
import streamlit as st
import snowflake.connector
import sseclient


# replace these values in your .secrets.toml file, not here!
HOST = st.secrets["snowflake"]["host"]
ACCOUNT = st.secrets["snowflake"]["account"]
USER =st.secrets["snowflake"]["user"]
API_KEY = st.secrets["snowflake"]["api_key"]
ROLE = st.secrets["snowflake"]["role"]

# API configuration 
API_ENDPOINT = "/api/v2/cortex/inference:complete"
API_TIMEOUT = 50000  # in milliseconds
MODEL_NAME = "llama3.1-8b" # change me to mistral-large2, llama3.1-70b or claude-3-5-sonnet and see what happens!

# Chat assistant defaults 
icons = {"assistant": "❄️", "user": "⛷️"}

# Stremalit app title
st.set_page_config(page_title="Snowflake REST API")

default_message = [{"role": "assistant", "content": "Hi. I'm a simple chat bot that uses `"+MODEL_NAME+"` to answer questions. Ask me anything."}]


def clear_chat_history():
    st.session_state.messages = default_message


def api_call(prompt: str):
    print(f"[INFO] Sending API request with prompt: {prompt}")
    try:
        cursor = st.session_state.CONN.cursor()
        escaped_prompt = prompt.replace("'", "\\'")
        cursor.execute(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', '{escaped_prompt}')")
        result = cursor.fetchone()[0]
        print(f"[INFO] Got response: {result}")
        yield result
    except Exception as e:
        print(f"[ERROR] Cortex call failed: {e}")
        yield f"Error: {e}"

    #except: 
    #    yield "Sorry, I've run into an error with this request! :( \n\n It's likely that my API request is malformed. You can try debugging in the `api_call()` function."

def connect_to_snowflake():
    # connection
    if 'CONN' not in st.session_state or st.session_state.CONN is None:

        try: 
            st.session_state.CONN = snowflake.connector.connect(
                user=USER,
                password=API_KEY,
                account=ACCOUNT,
                host=HOST,
                port=443,
                role=ROLE
            )  
            st.info('Snowflake Connection established!', icon="💡")    
        except:
            st.error('Connection not established. Check that you have correctly entered your Snowflake credentials!', icon="🚨")    


def get_tariff_context():
    try:
        # Query your new table
        query = "SELECT * FROM HACKLYTICS_DB.PUBLIC.COUNTRY_TARIFF_RISK LIMIT 500;"
        cursor = st.session_state.CONN.cursor()
        cursor.execute(query)
        
        # Fetch the rows and turn them into a readable string for the LLM
        rows = cursor.fetchall()
        context_string = "Tariff Risk Data Context:\n"
        for row in rows:
            context_string += f"{row}\n"
            
        return context_string
    except Exception as e:
        return "No data available."

def main():
    print("[INFO] App started.")

    st.sidebar.title("Quantara Risk Analyst")
    st.sidebar.caption("Visit [CORTEX PLAYGROUND](https://app.snowflake.com/_deeplink/#/cortex/playground) for an interactive interface to test out models, and view model availability")
    st.sidebar.button('Clear chat history', on_click=clear_chat_history)
    connect_to_snowflake()

    # Store LLM-generated responses
    if "messages" not in st.session_state.keys():
        st.session_state.messages = default_message

    # Display or clear chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=icons[message["role"]]):
            st.write(message["content"])

    # User-provided prompt
    if prompt := st.chat_input(disabled=not st.session_state.CONN):
        st.session_state.messages.append({"role": "user", "content": prompt})
        print(f"[INFO] User prompt received: {prompt}")
        with st.chat_message("user", avatar=icons["user"]):
            st.write(prompt)

    # Generate a new response if last message is not from assistant
    if st.session_state.messages[-1]["role"] != "assistant":
        print("[INFO] Generating assistant response...")
        # --- THIS IS WHERE WE INJECT THE DATA ---
        tariff_data = get_tariff_context()
        print(f"[INFO] Tariff data context: {tariff_data[:200]}...")
        augmented_prompt = f"""
        You are a supply chain risk analyst. Answer the user's question using ONLY the following data context. If the answer is not in the data, say you don't know.
        
        {tariff_data}
        
        User Question: {prompt}
        """
        # ----------------------------------------

        with st.chat_message("assistant", avatar=icons["assistant"]):
            print("[INFO] Calling api_call with augmented prompt.")
            response = api_call(augmented_prompt)
            full_response = st.write_stream(response)
            print(f"[INFO] Assistant response: {full_response}")
        message = {"role": "assistant", "content": full_response}
        st.session_state.messages.append(message)
            
   
if __name__ == "__main__":
    main()
