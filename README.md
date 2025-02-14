# Slack LLM Chatbot Project

## Overview

This project is a Slack chatbot designed to interact with users in Slack channels. It leverages the Groq API for generating responses and integrates with Slack's API to handle events and send messages. The architecture is built using Django for the backend, ensuring scalability and maintainability.

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Slack App with necessary permissions
- Groq API access

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/slack-chatbot.git
   cd slack-chatbot
   ```

2. **Populate the environment variables**
    - Copy the .env.example into a new file called .env
    - Populate your environment vairbales into the file

3. **Running the server**
    - The server is dockerized, so you just need to run 
    ```
    docker compose up --build -d
    ```
    - The server is now up on port 8000 of your host.

## Architecture

### Components

- **Backend:** Django framework is used for handling HTTP requests and managing the database.
- **Database:** PostgreSQL is used to store Slack workspace and conversation history. This data may further be used to fine-tune the LLM or setup a RAG pipeline using a vector database.
- **APIs:** 
  - **Slack API:** Used for receiving events and sending messages.
  - **Groq API:** Used for generating chatbot responses.

### Flow

1. **Slack Event:** The Slack API sends events to the server.
2. **Event Processing:** The server processes the event, interacts with the Groq API if necessary, and updates the database.
3. **Response:** The server sends a response back to Slack, which is then displayed in the channel.
