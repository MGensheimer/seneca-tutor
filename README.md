# Personal Tutor

Runs locally with a web interface using Flask and the Anthropic API.

## Why

What qualities would an ideal tutor have? Deep subject matter knowledge, an ability to adapt the material to the student's knowledge and learning style, and the discipline to design an effective long-term lesson plan. We can achieve a lot of this by giving a LLM access to specialized memory files that it can read and update across chat sessions.

## Features

- Uses Claude 3.5 Sonnet model
- The AI continuously updates the lesson plan based on progress and how the student is doing, and remembers it between sessions
- The AI has access to a calculator tool for checking arithmetic problems

## Prerequisites

- Anthropic API key (set ANTHROPIC_API_KEY environment variable or put it in a .env file)
- Python 3

## Installation

1. Clone this repository:

```bash
git clone https://github.com/MGensheimer/tutor.git
cd tutor
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

The following packages are required:
- anthropic>=0.40.0
- beautifulsoup4>=4.12.3
- Flask>=3.1.0
- nh3>=0.2.18
- python-dotenv>=1.0.1
- termcolor>=2.5.0

## Running the Application

1. Make sure your virtual environment is activated.

2. Start the web server from the tutor directory:

```bash
python tutor.py
```

The application will be available at `http://localhost:8001`

## Notes

- You can change the model to another Anthropic model by changing the MODEL_NAME variable in utils.py
- The model is better at some things than others. It sometimes makes math problems with arithmetic or geometry errors.
- After using the app a bit, check out the text files in the data directory, there are lesson_plan, student_info, and past_problems files for each student that hold the AI's memory and that you might find interesting.

## Contact

Please email me your feedback or interesting use cases/stories at michael.gensheimer@gmail.com

X: @MFGensheimer

BlueSky: @mgens.bsky.social