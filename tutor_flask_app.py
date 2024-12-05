from flask import Flask, render_template, request, redirect, url_for, session
import os
from utils import get_notes, edit_notes, call_llm_with_tools, get_timestamp, count_tokens
from termcolor import colored
import anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import json
import uuid
load_dotenv()

VERBOSE_OUTPUT = True
MAX_INPUT_TOKENS = 80000

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'insecure-key')

note_topics = ['student_info', 'lesson_plan', 'past_problems', 'personal_interactions']

def get_student_list():
    """Get list of students from data directory"""
    if not os.path.exists('data'):
        return []
    
    # Get unique student names from files in data directory
    files = os.listdir('data')
    students = set()
    for file in files:
        if file.endswith('_lesson_plan.txt'):
            # Remove '_lesson_plan.txt' from the end to get the student name
            student_name_safe = file[:-16]  # len('_lesson_plan.txt') == 16
            students.add(student_name_safe)
    return sorted(list(students))


def anthropic_to_string_format(messages):
    messages_for_serialize = []
    for message in messages:
        message_text = ''
        if type(message['content'])==str: #used for standard user messages to assistant
            message_text = message['content']
        elif type(message['content'])==list:
            for content_item in message['content']:
                if type(content_item)==anthropic.types.text_block.TextBlock: #used for text from assistant to user
                    message_text += content_item.text + '\n\n'
                if type(content_item)==anthropic.types.tool_use_block.ToolUseBlock: # used for tool calls from assistant to user
                    message_text += f'<tool_call>\nName: {content_item.name}\nID: {content_item.id}\nInput: {content_item.input}\n</tool_call>\n\n'
                if type(content_item)==dict: #used for tool results from user to assistant
                    message_text += json.dumps(content_item) + '\n\n'
        
        if message_text.strip():
            messages_for_serialize.append({'role': message['role'], 'content': message_text})

    return messages_for_serialize


def extract_chat_messages(messages):
    """Extract student and tutor text from the messages list (the text that should be displayed to the user)"""
    chat_messages = []
    for message in messages:
        soup = BeautifulSoup(message['content'], 'html.parser')
        if message['role'] == 'assistant':
            student_messages = soup.find_all('to_student')
        elif message['role'] == 'user':
            student_messages = soup.find_all('from_student')
        if student_messages:
            filtered_messages = [msg.get_text() for msg in student_messages if msg.get_text() not in ['', '\n']]
            if filtered_messages:
                chat_messages.append({
                    'role': message['role'],
                    'content': '\n'.join(filtered_messages)
                })
    return chat_messages


def save_chat_history(student_name_safe, chat_uuid, messages):
    """Save chat history to a file"""
    filename = f'data/{student_name_safe}_chathistory_{chat_uuid}.txt'
    with open(filename, 'w') as f:
        json.dump(messages, f, indent=2)


def load_chat_history(student_name_safe, chat_uuid):
    """Load chat history from a file"""
    filename = f'data/{student_name_safe}_chathistory_{chat_uuid}.txt'
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    else:
        return []


def make_first_user_message(student_name_safe):
    notes_content = ''
    for topic in note_topics:
        notes_content += f'<notes topic="{topic}">\n{get_notes(student_name_safe, topic)}\n</notes>\n'

    first_user_message = f"""
You are a private tutor for a student. You will give the student problems or challenges that can be answered fairly quickly, check their answers, and help them if they get stuck. Your goal is to help the student improve their skills and get excited about the topic, while maintaining detailed notes on their progress.
When creating a new problem or challenge, the steps will be:
1. Write out the problem, what topic it falls under, the difficulty/grade level, and how challenging you expect it to be for the specific student you are tutoring. Use <problem></problem> tags.
2. Write down the steps needed to solve the problem, and an acceptable answer. Use <solution></solution> tags.
3. Give the problem to the student. Wrap any text that will be sent to the student in <to_student></to_student> tags.

The student's responses will be wrapped in <from_student></from_student> tags. After the student responds, if they are correct, then congratulate them, make any relevant comments on the strategy they used to, and move on to the next problem. If they are wrong, then engage with them as a tutor would, to try to understand why they are getting it wrong. This could include asking them to tell you the steps they used to solve the problem, giving them small hints to try to nudge them in the right direction, or teaching them about needed concepts.
If the student still cannot get to the right answer after several turns back and forth and you think it's time to move to the next problem, make a note in the skills note using tool calling, then move to the next problem and notify the student.

During all this, you should be keeping all your notes up to date using tool calls. Here is a guide to the different notes:
- student_info: The student's grade level or professional situation, what areas they want to focus on, learning style, strategies that have worked well or poorly with them.
- lesson_plan: Start with a summary of short and long-term goals. Then have a list of topics that you want to cover, with details. Details include the material to cover, where the student is at (no proficiency, progressing, mastery). Use timestamps to keep track of when the topic was started and most recently worked on.
- past_problems: Use this to store problems that the student could not get right even after several tries, so that you can come back to them later once the student has progressed in their skills and is ready to try again.
- personal_interactions: This is for memories of your social connection with the student. For instance, if you or the student shared a personal detail that you think could be helpful when bonding with the student in the future.

Make sure none of the notes get too long; you should keep each one to about a page of text or less. If they get too long, use the edit_notes tool to trim them.

Before we begin, here is the current content of your notes about the student:
<notes_content>
{notes_content}
</notes_content>

Here is the current timestamp: {get_timestamp()}

Let's get started! If there is no lesson plan, then draft one and tell the student about it to get feedback, and modify as needed using tool calls. Then give the student their first problem. Otherwise, go ahead with the problem. If your notes indicate the student has done prior work with you, don't refer to it as the first problem. Remember, only text within <to_student> blocks will be shown to the student.
    """
    return first_user_message


@app.route('/')
def index():
    students = get_student_list()
    return render_template('index.html', 
                         students=students)


@app.route('/new_student', methods=['GET', 'POST'])
def new_student():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_info = request.form['student_info']
        
        student_name_safe = ''.join(c for c in student_name if c.isalnum() or c in '-_').lower()
        
        # Create data directory if it doesn't exist
        if not os.path.exists('data'):
            os.makedirs('data')
            
        # Create student files
        note_defaults = {
            'student_info': f'User-supplied information for student with identifier {student_name}:\n{student_info}',
            'lesson_plan': f'Tutoring first started at: {get_timestamp()}. No lesson plan has been created; please create one.',
            'past_problems': 'No past problems.',
            'personal_interactions': 'No personal interactions.'
        }
        
        for topic, content in note_defaults.items():
            with open(f'data/{student_name_safe}_{topic}.txt', 'w') as f:
                f.write(content)
        
        session['student_name_safe'] = student_name_safe
        return redirect(url_for('chat'))
        
    return render_template('new_student.html')


@app.route('/select_student/<student_name_safe>')
def select_student(student_name_safe):
    session['student_name_safe'] = student_name_safe
    return redirect(url_for('chat'))


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    tools = [
        {
            "name": "get_notes",
            "description": "Get the full text of notes for the specified topic",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note_topic": {
                        "type": "string",
                        "enum": ["student_info", "lesson_plan", "past_problems", "personal_interactions"],
                        "description": "The topic of notes to retrieve"
                    }
                },
                "required": ["note_topic"]
            }
        },
        {
            "name": "edit_notes",
            "description": "Edit the notes for the specified topic by replacing old text with new text, or deleting old text if new_excerpt is empty",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note_topic": {
                        "type": "string",
                        "enum": ["student_info", "lesson_plan", "past_problems", "personal_interactions"],
                        "description": "The topic of notes to edit"
                    },
                    "old_excerpt": {
                        "type": "string",
                        "description": "The text to replace (leave empty to append instead)"
                    },
                    "new_excerpt": {
                        "type": "string",
                        "description": "The new text to insert (leave empty to delete the old_excerpt)"
                    }
                },
                "required": ["note_topic"]
            }
        },
        {
            "name": "finish_question",
            "description": "Use this when you want to finish the current question and start a new one. This will start a new conversation with fresh context. You will have a chance to update your notes before the next question.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "The reason for finishing this question (e.g., 'Student has mastered this concept', 'Student is struggling too much')"
                    }
                },
                "required": ["reason"]
            }
        },
    ]

    if 'chat_uuid' not in session:
        session['chat_uuid'] = str(uuid.uuid4())
    
    need_to_call_llm = False
    messages = load_chat_history(session['student_name_safe'], session['chat_uuid'])

    if not messages:
        messages = [{"role": "user", "content": make_first_user_message(session['student_name_safe'])}]
        need_to_call_llm = True

    if request.method == 'POST':
        if request.form.get('action') == 'new_chat':
            # First let LLM finalize notes for current question
            if messages:
                messages.append({
                    "role": "user", 
                    "content": 'The session has ended because the student or tutor wants to do a new question. Please make any last updates to your notes. This would be a good time to update the lesson plan with your plans for the next question so you are ready for the next session. You do not need to call finish_question.'
                })
                print(f'Length of messages before LLM call: {len(messages)}')
                _, messages_anthropic_format = call_llm_with_tools(
                    session['student_name_safe'], 
                    messages, 
                    tools, 
                    verbose_output=VERBOSE_OUTPUT
                )
                messages = anthropic_to_string_format(messages_anthropic_format)
                print(f'Length of messages after LLM call: {len(messages)}')

                # Save chat history to file
                save_chat_history(
                    session['student_name_safe'],
                    session['chat_uuid'],
                    messages
                )

            # Start new chat session
            session['chat_uuid'] = str(uuid.uuid4())
            messages = [{"role": "user", "content": make_first_user_message(session['student_name_safe'])}]
            need_to_call_llm = True
            
        user_input = request.form.get('user_input')
        if user_input:
            wrapped_input = f"Timestamp: {get_timestamp()}\n<from_student>{user_input}</from_student>"
            messages.append({"role": "user", "content": wrapped_input})
            need_to_call_llm = True

    if need_to_call_llm:
        _, messages_anthropic_format = call_llm_with_tools(
            session['student_name_safe'], 
            messages, 
            tools, 
            verbose_output=VERBOSE_OUTPUT
        )
        messages = anthropic_to_string_format(messages_anthropic_format)

        # Check if LLM called finish_question
        llm_wants_new_question = False
        for message in messages:
            if isinstance(message.get('content'), list):
                for content_item in message['content']:
                    if isinstance(content_item, anthropic.types.tool_use_block.ToolUseBlock):
                        if content_item.name == 'finish_question':
                            llm_wants_new_question = True
                            break

        session['llm_wants_new_question'] = llm_wants_new_question

        # Save chat history to file
        save_chat_history(
            session['student_name_safe'],
            session['chat_uuid'],
            messages
        )
    
    #extract only the text that should be visible to the student
    chat_messages = extract_chat_messages(messages)
    return render_template('chat.html', 
                         chat_messages=chat_messages,
                         student_name_safe=session.get('student_name_safe'),
                         llm_wants_new_question=session.get('llm_wants_new_question', False))

if __name__ == '__main__':
    app.run(debug=True)