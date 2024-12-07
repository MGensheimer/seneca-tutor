# Seneca-tutor

Large language model-based tutoring app that runs locally with a web interface using Flask and the Anthropic API.

## Why

An ideal tutor would have deep subject matter knowledge, an ability to adapt the material to the student's knowledge and learning style, and the discipline to design an effective long-term lesson plan. We can achieve much of this by giving a LLM access to specialized memory files that it can read and update across chat sessions.

## Features

- The AI continuously updates the lesson plan based on progress and how the student is doing, and remembers it between sessions
- The AI has access to a calculator tool for checking arithmetic problems
- Uses Claude 3.5 Sonnet model

## Prerequisites

- Anthropic API key
  - Set ANTHROPIC_API_KEY environment variable or put it in a .env file in the seneca-tutor directory
  - Get one at https://console.anthropic.com/
- Python 3
- Tested on Mac and Linux

## Installation

1. Clone this repository:

```bash
git clone https://github.com/MGensheimer/seneca-tutor.git
cd seneca-tutor
```

2. Create a virtual environment (recommended):

```bash
python -m venv myenv
source myenv/bin/activate
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Dependencies

The following Python packages are required:
- anthropic>=0.40.0
- beautifulsoup4>=4.12.3
- Flask>=3.1.0
- nh3>=0.2.18
- python-dotenv>=1.0.1
- termcolor>=2.5.0

## Running the Application

1. Make sure your virtual environment is activated.

2. Start the web server:

```bash
python tutor.py
```

3. Go to [`http://localhost:8001`](http://localhost:8001)

## Notes

- You can change the model to another Anthropic model by changing the MODEL_NAME variable in utils.py
- The model is better at some things than others. It sometimes makes math problems with arithmetic or geometry errors.
- After using the app a bit, check out the text files in the data directory, each student has lesson_plan, student_info, and past_problems files that hold the AI's memory.

## About Seneca

Seneca was a famed Roman philosopher, statesman, and tutor to the emperor Nero.

<img src="seneca.jpeg" width="200" alt="Seneca" style="display: block; margin: 0 auto;">

*Photo by Jean-Pol Grandmont, via Wikipedia*

## Contact

Please email me your feedback or interesting use cases/stories at michael.gensheimer@gmail.com

X: @MFGensheimer

BlueSky: @mgens.bsky.social