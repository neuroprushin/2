# J.A.R.V.I.S. - AI Code Assistant

J.A.R.V.I.S. is an intelligent coding assistant that leverages multiple state-of-the-art language models to help you with code generation, modifications, and technical discussions.

## Features

- **Multi-Model Support**: Choose between different AI models for your coding needs:
  - DeepSeek Coder V3
  - Grok 2
  - Groq (Llama 3.3 70B)
  - Claude 3.5 Sonnet

- **Workspace Management**:
  - Create and manage multiple workspaces
  - View workspace history
  - Delete workspaces when no longer needed
  - Rename workspaces
  - Browse workspace file structure

- **Code Generation & Modification**:
  - Generate new code based on natural language prompts
  - Modify existing code with AI assistance
  - Preview changes before applying them
  - View diffs of proposed changes
  - Automatic code formatting

- **Interactive Chat**:
  - Discuss code and technical concepts
  - Get explanations about existing code
  - Context-aware responses based on workspace content

- **Code Analysis**:
  - Built-in linting support
  - Dependency analysis
  - File relationship visualization

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your environment variables in `.env`:
   ```
   DEEPSEEK_API_KEY=your_deepseek_api_key
   GROK_API_KEY=your_grok_api_key
   GROQ_API_KEY=your_groq_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

## Usage

1. Start the server:
   ```bash
   python app.py
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Create a new workspace or select an existing one
4. Choose your preferred AI model
5. Start coding with AI assistance!

## Model Capabilities

- **DeepSeek Coder**: Specialized in code generation and modification
- **Grok 2**: Strong at both code and natural language understanding
- **Groq (Llama 3.3)**: Fast inference with comprehensive coding knowledge
- **Claude 3.5 Sonnet**: Advanced reasoning and code understanding

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.