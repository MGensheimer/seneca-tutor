# Personal Tutor

Runs locally in a web browser using Flask and the Anthropic API.

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
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
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

2. Start the Flask development server:

```bash
python tutor.py
```

The application will be available at `http://localhost:8001`
