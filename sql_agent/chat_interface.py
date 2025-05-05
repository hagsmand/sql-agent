import streamlit as st
import requests
import json
import uuid
import sseclient
import time
from typing import Dict, Any, List, Optional

# A2A Client for interacting with the SQL Agent
class A2AClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session_id = str(uuid.uuid4())
        
    def send_message(self, message: str, stream: bool = True) -> Dict[str, Any]:
        """Send a message to the A2A server and get the response."""
        task_id = str(uuid.uuid4())
        
        if stream:
            return self._send_streaming_request(task_id, message)
        else:
            return self._send_request(task_id, message)
    
    def _send_request(self, task_id: str, message: str) -> Dict[str, Any]:
        """Send a non-streaming request to the A2A server."""
        payload = {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "sessionId": self.session_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}]
                },
                "acceptedOutputModes": ["text"]
            }
        }
        
        response = requests.post(self.server_url, json=payload)
        if response.status_code != 200:
            return {"error": f"Error: {response.status_code} - {response.text}"}
        
        return response.json()
    
    def _send_streaming_request(self, task_id: str, message: str) -> Dict[str, Any]:
        """Send a streaming request to the A2A server and process SSE responses."""
        payload = {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "tasks/sendSubscribe",
            "params": {
                "id": task_id,
                "sessionId": self.session_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}]
                },
                "acceptedOutputModes": ["text"]
            }
        }
        
        headers = {'Accept': 'text/event-stream', 'Content-Type': 'application/json'}
        response = requests.post(self.server_url, json=payload, headers=headers, stream=True)
        
        if response.status_code != 200:
            return {"error": f"Error: {response.status_code} - {response.text}"}
        
        client = sseclient.SSEClient(response)
        
        # Process the SSE events
        final_response = {"status": "incomplete", "content": ""}
        for event in client.events():
            if not event.data:
                continue
                
            data = json.loads(event.data)
            if "result" in data:
                result = data["result"]
                
                # Handle task status update
                if "status" in result:
                    status = result["status"]
                    if "message" in status and status["message"]:
                        message_parts = status["message"]["parts"]
                        for part in message_parts:
                            if part["type"] == "text":
                                final_response["content"] = part["text"]
                
                # Check if this is the final message
                if "final" in result and result["final"]:
                    final_response["status"] = "complete"
                    break
            
            # Handle errors
            if "error" in data:
                final_response["status"] = "error"
                final_response["error"] = data["error"]
                break
                
        return final_response

# Streamlit UI
def main():
    st.title("SQL Agent Chat Interface")
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "client" not in st.session_state:
        # Default to localhost:10002 as seen in the __main__.py file
        server_url = st.sidebar.text_input("Server URL", "http://localhost:10002/")
        st.session_state.client = A2AClient(server_url)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about SQL queries..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get response from A2A server
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.text("Thinking...")
            
            try:
                response = st.session_state.client.send_message(prompt)
                
                if "error" in response:
                    message_placeholder.error(f"Error: {response['error']}")
                else:
                    message_placeholder.write(response["content"])
                    # Add assistant response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": response["content"]})
            except Exception as e:
                message_placeholder.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()