from flask import Flask
from flask import render_template
from datetime import datetime
import os
from datetime import datetime
from utils import get_notes, edit_notes, call_llm_with_tools, get_timestamp, count_tokens
from termcolor import colored
import anthropic


app = Flask(__name__)
@app.route('/')
def index():
    return render_template('index.html', current_year=datetime.now().year)

if __name__ == '__main__':
    app.run(debug=True)
