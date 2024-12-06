import streamlit as st
import anthropic
import time
from typing import Dict, List, Optional
import json

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'current_tokens' not in st.session_state:
    st.session_state.current_tokens = 0
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0.0

CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
INITIAL_SYSTEM_MESSAGE = """You are an educational assistant focused on helping users build chatbots. 
You provide clear, detailed explanations and adapt your teaching style to the user's experience level. 
Break down complex concepts into manageable parts and provide practical examples when helpful.
When explaining technical concepts, provide context and build understanding incrementally."""

COST_PER_1K_INPUT_TOKENS = 0.015
COST_PER_1K_OUTPUT_TOKENS = 0.075

def validate_api_key(api_key: str) -> bool:
    try:
        client = anthropic.Client(api_key=api_key)
        client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1,
            messages=[{"role": "user", "content": "test"}]
        )
        return True
    except Exception:
        return False

def calculate_cost(num_input_tokens: int, num_output_tokens: int) -> float:
    input_cost = (num_input_tokens / 1000) * COST_PER_1K_INPUT_TOKENS
    output_cost = (num_output_tokens / 1000) * COST_PER_1K_OUTPUT_TOKENS
    return input_cost + output_cost

def handle_api_error(error: Exception) -> str:
    error_str = str(error)
    if "rate_limit" in error_str.lower():
        return "Rate limit exceeded. Please wait a moment before trying again."
    elif "invalid_request" in error_str.lower():
        if "model" in error_str.lower():
            return "Please check your API access permissions for Claude 3.5 Sonnet."
        return "Please check your input and try again."
    elif "authentication" in error_str.lower():
        return "Authentication failed. Please verify your API key."
    else:
        return f"An unexpected error occurred: {error_str}"

def get_safe_response(client: anthropic.Client, messages: List[Dict], max_tokens: int, temperature: float) -> tuple[Optional[str], Optional[Dict], Optional[str]]:
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages
        )
        
        if not response.content or not response.content[0].text:
            return None, None, "Received empty response from Claude"
            
        usage_stats = {
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens
        }
        
        return response.content[0].text, usage_stats, None
        
    except Exception as e:
        return None, None, handle_api_error(e)

def export_conversation(messages: List[Dict], format: str = 'markdown') -> str:
    if format == 'markdown':
        output = "# Chatbot Development Learning Session\n\n"
        for msg in messages:
            role = msg['role'].capitalize()
            content = msg['content'].replace('```', '~~~')
            output += f"## {role}\n\n{content}\n\n"
            if 'cost' in msg:
                output += f"*Cost: ${msg['cost']:.4f}*\n\n"
                
    elif format == 'json':
        export_data = {
            'conversation': messages,
            'total_cost': st.session_state.total_cost,
            'export_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        output = json.dumps(export_data, indent=2)
        
    else:  # plain text
        output = "=== Chatbot Development Learning Session ===\n\n"
        for msg in messages:
            role = msg['role'].upper()
            content = msg['content']
            output += f"[{role}]\n{content}\n\n"
            if 'cost' in msg:
                output += f"Cost: ${msg['cost']:.4f}\n\n"
        output += f"\nTotal Session Cost: ${st.session_state.total_cost:.4f}"
    
    return output

def main():
    st.title("🤖 Interactive Chatbot Builder")
    
    with st.sidebar:
        st.header("Control Panel")
        
        api_key = st.text_input(
            "Enter your Anthropic API Key",
            type="password",
            help="Your API key must have access to Claude 3.5 Sonnet. Get your key from console.anthropic.com"
        )
        
        if api_key and not validate_api_key(api_key):
            st.error("Invalid API key or insufficient permissions for Claude 3.5 Sonnet")
            return
        
        st.subheader("Model Parameters")
        
        max_tokens = st.slider(
            "Maximum Output Tokens",
            min_value=100,
            max_value=4096,
            value=1000,
            help="Controls the length of the response. Higher values allow for longer, more detailed answers but increase cost."
        )
        
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="""Controls response creativity and variability:
            \n0.0: Very focused and consistent
            \n0.5: Balanced creativity and consistency
            \n1.0: More creative and varied responses"""
        )
        
        st.subheader("Cost Tracking")
        st.write(f"Current Session Cost: ${st.session_state.total_cost:.4f}")
        
        st.subheader("Export Conversation")
        export_format = st.selectbox(
            "Choose Format",
            options=['markdown', 'json', 'text'],
            help="Markdown: Formatted text with headers and code blocks\n"
                 "JSON: Structured data format\n"
                 "Text: Plain text format"
        )
        
        if st.session_state.messages:
            if st.button("Export Conversation"):
                exported_content = export_conversation(st.session_state.messages, export_format)
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                file_extension = 'md' if export_format == 'markdown' else export_format
                filename = f"chatbot_session_{timestamp}.{file_extension}"
                
                st.download_button(
                    label="Download Export",
                    data=exported_content,
                    file_name=filename,
                    mime="text/plain"
                )

    if not api_key:
        st.warning("Please enter your API key in the sidebar to begin.")
        return

    client = anthropic.Client(api_key=api_key)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if prompt := st.chat_input("What would you like to learn about chatbot development?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        messages = []
        if len(st.session_state.messages) == 1:
            messages.append({"role": "system", "content": INITIAL_SYSTEM_MESSAGE})
        
        for msg in st.session_state.messages:
            role = "assistant" if msg["role"] == "assistant" else "user"
            messages.append({"role": role, "content": msg["content"]})

        with st.chat_message("assistant"):
            response_text, usage_stats, error = get_safe_response(
                client, messages, max_tokens, temperature
            )
            
            if error:
                st.error(error)
                return
                
            if response_text and usage_stats:
                message_cost = calculate_cost(
                    usage_stats['input_tokens'],
                    usage_stats['output_tokens']
                )
                st.session_state.total_cost += message_cost
                
                st.write(response_text)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "cost": message_cost
                })
                
                st.caption(
                    f"Tokens used - Input: {usage_stats['input_tokens']}, "
                    f"Output: {usage_stats['output_tokens']}, "
                    f"Cost: ${message_cost:.4f}"
                )

if __name__ == "__main__":
    main()