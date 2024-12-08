from flask import Flask, render_template, request, redirect, url_for, session
import os
from utils import get_notes, edit_notes, call_llm_with_tools, get_timestamp, count_tokens, format_html_w_tailwind
from termcolor import colored
import anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import pickle
import nh3
from copy import deepcopy
import hashlib

load_dotenv()

VERBOSE_OUTPUT = True
MAX_INPUT_TOKENS = 80000

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'insecure-key')

note_topics = ['student_info', 'lesson_plan', 'past_problems']

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


def sanitize_html(html_text):
    tags = set(nh3.ALLOWED_TAGS) | {"svg", "line", "text", "rect", "path", "polygon", "polyline", "ellipse", "circle", "g", "defs", "use", "clipPath", "linearGradient", "stop", "image"}
    attributes = deepcopy(nh3.ALLOWED_ATTRIBUTES)
    attributes_to_add = {
        'svg': ['width', 'height', 'viewBox', 'xmlns', 'fill', 'stroke'],
        'path': ['d', 'fill', 'stroke', 'stroke-width'],
        'circle': ['cx', 'cy', 'r', 'fill', 'stroke'],
        'line': ['x1', 'y1', 'x2', 'y2', 'stroke', 'stroke-width', 'marker-end', 'marker-start'],
        'text': ['x', 'y', 'font-size', 'fill', 'font-weight'],
        'rect': ['x', 'y', 'width', 'height', 'fill', 'stroke', 'stroke-width'],
        'marker': ['id', 'markerWidth', 'markerHeight', 'refX', 'refY', 'orient'],
        'polygon': ['points', 'fill'],
    }
    for tag, attrs in attributes_to_add.items():
        if tag not in attributes:
            attributes[tag] = set()
        for attr in attrs:
            attributes[tag].add(attr)

    return nh3.clean(html_text, tags=tags, attributes=attributes)


def extract_chat_messages(messages):
    """Extract student and tutor text from the messages list"""
    chat_messages = []
    for message in messages:
        if isinstance(message.get('content'), str):
            content = message['content']
        else:
            content = ""
            for item in message.get('content', []):
                if hasattr(item, 'text'):
                    content += item.text + '\n\n'
            
        soup = BeautifulSoup(content, 'html.parser')
        filtered_messages = None
        if message['role'] == 'assistant': #HTML formatted text
            student_messages = soup.find_all('to_student')
            filtered_messages = [sanitize_html(format_html_w_tailwind(str(msg))) for msg in student_messages if str(msg) not in ['', '\n']]
        elif message['role'] == 'user': #plain text
            student_messages = soup.find_all('from_student')
            filtered_messages = [str(msg).replace('\n', '<br>') for msg in student_messages if str(msg) not in ['', '\n']]
            
        if filtered_messages:
            chat_messages.append({
                'role': message['role'],
                'content': '\n'.join(filtered_messages)
            })
    return chat_messages


def save_chat_history(student_name_safe, chat_id, messages):
    """Save chat history to a pickle file"""
    filename = f'data/{student_name_safe}_chathistory_{chat_id}.pkl'
    with open(filename, 'wb') as f:
        pickle.dump(messages, f)


def load_chat_history(student_name_safe, chat_id):
    """Load chat history from a pickle file"""
    filename = f'data/{student_name_safe}_chathistory_{chat_id}.pkl'
    with open(filename, 'rb') as f:
        return pickle.load(f)


def make_system_prompt():
    return """You are a private tutor for a student. You will give the student problems or challenges that can be answered fairly quickly, check their answers, and help them if they get stuck. Your goal is to help the student improve their skills and get excited about the topic, while maintaining detailed notes on their progress.
When creating a new problem or challenge, the steps will be:
1. Write out the problem. Use <problem></problem> tags.
2. Write down the steps needed to solve the problem, and an acceptable answer. Use <solution></solution> tags. For arithmetic problems, when feasible, use the calculator tool to check the answer.
3. Write a correctness check inside <correctness_check></correctness_check> tags. For this, you will verify that the problem is correctly posed, using the proposed solution and also your background knowledge (e.g., for the problem: "Give the perimeter of a rectangle with sides of 3,4,5,6 units", you will recognize that the problem is flawed because opposite sides of a rectangle cannot be different lengths). If there is an error in the problem, correct it.
4. Give the problem to the student. Wrap any text that will be sent to the student in <to_student></to_student> tags. Format this text with HTML, and you can also include small SVG diagrams as needed.

The student's responses will be wrapped in <from_student></from_student> tags. After the student responds, if they are correct, then congratulate them, make any relevant comments on the strategy they used to, and move on to the next problem. If they are wrong, then engage with them as a tutor would, to try to understand why they are getting it wrong. This could include asking them to tell you the steps they used to solve the problem, giving them small hints to try to nudge them in the right direction, or teaching them about needed concepts.
If the student still cannot get to the right answer after several turns back and forth and you think it's time to move to the next problem, make a note in the skills note using tool calling, then move to the next problem and notify the student.

During the conversation, you should be keeping all your notes up to date using tool calls. Here is a guide to the different notes:
- student_info: The student's grade level or professional situation, what areas they want to focus on, learning style, strategies that have worked well or poorly with them. Also use this to store memories of your social connection with the student. For instance, if you or the student shared a personal detail that you think could be helpful when bonding in the future.
- lesson_plan: Start with a summary of short and long-term goals. Then have a list of topics that you want to cover, with details. Details include the material to cover, where the student is at (no proficiency, progressing, mastery). Use timestamps to keep track of when the topic was started and most recently worked on.
- past_problems: Use this to store problems that the student could not get right even after several tries, so that you can come back to them later once the student has progressed in their skills and is ready to try again.

Some notes/reminders:
- Very important: Only text within <to_student> blocks will be shown to the student; use HTML formatting for this text.
- Make sure none of the notes get too long; you should keep each one to 1-2 pages of text or less. If they get longer than that, use the edit_notes tool to trim them.
- If the user requests a new problem, or the chat history gets long and the early messages are no longer relevant, or you want to start a new topic, call the finish_question tool to start a new session.
- Adapt your style to the age of the student. For instance, for an 8 year old student, if they got the answer right, don't ask them to explain their steps.
- Only ask the student to do things they can type (no drawing, etc.).
"""


def make_first_user_message(student_name_safe):
    notes_content = ''
    for topic in note_topics:
        notes_content += f'<notes topic="{topic}">\n{get_notes(student_name_safe, topic)}\n</notes>\n'

    first_user_message = f"""
Let's start a new problem/session. Here is the current content of your notes about the student:
<notes_content>
{notes_content}
</notes_content>

Here is the current timestamp: {get_timestamp()}

Let's get started! If there is no lesson plan, then draft one and tell the student about it to get feedback, and modify as needed using tool calls. Then give the student their first problem. Otherwise, go ahead with the problem.
If your notes indicate the student has done prior work with you, the chat session is continuing from where they left off, so don't refer to it as the first problem.
"""
    return first_user_message


def get_lesson_plan_hash(student_name_safe):
    """Calculate hash of lesson plan content"""
    lesson_plan = get_notes(student_name_safe, 'lesson_plan')
    return hashlib.md5(lesson_plan.encode()).hexdigest()


def get_latest_chat_id(student_name_safe):
    """Get the most recent chat ID for a student (the one with the highest number)"""
    if not os.path.exists('data'):
        return '000001'
    
    files = [f for f in os.listdir('data') if f.startswith(f'{student_name_safe}_chathistory_')]
    if not files:
        return '000001'
        
    chat_ids = []
    for file in files:
        try:
            chat_id = file.split('_chathistory_')[1].split('.pkl')[0]
            chat_ids.append(int(chat_id))
        except (IndexError, ValueError):
            continue
    
    if not chat_ids:
        return '000001'
        
    return f'{max(chat_ids):06d}'  # Format as 6-digit string with leading zeros


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
        
        student_name_safe = ''.join(c for c in student_name if c.isalnum() or c in '-_')
        
        # Validate student name
        if not student_name_safe:
            return render_template('new_student.html', error="Student identifier cannot be empty and must contain at least one valid character (letters, numbers, hyphens, or underscores).")
        
        # Check if student already exists
        existing_students = get_student_list()
        if student_name_safe in existing_students:
            return render_template('new_student.html', error=f'A student with identifier {student_name_safe} already exists. Please choose a different identifier.')
        
        if not os.path.exists('data'):
            os.makedirs('data')
            
        # Create student files
        note_defaults = {
            'student_info': f'User-supplied information for student with identifier {student_name}:\n{student_info}',
            'lesson_plan': f'Tutoring first started at: {get_timestamp()}. No lesson plan has been created; please create one.',
            'past_problems': 'No past problems.',
        }
        
        for topic, content in note_defaults.items():
            with open(f'data/{student_name_safe}_{topic}.txt', 'w') as f:
                f.write(content)
        
        session['student_name_safe'] = student_name_safe
        session['chat_id'] = '000001'  # First chat session for new student
        return redirect(url_for('chat'))
        
    return render_template('new_student.html')


@app.route('/select_student/<student_name_safe>')
def select_student(student_name_safe):
    session['student_name_safe'] = student_name_safe
    session['chat_id'] = get_latest_chat_id(student_name_safe)

    # Since student may have changed, reset lesson plan hash
    current_hash = get_lesson_plan_hash(student_name_safe)
    session['lesson_plan_hash'] = current_hash

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
                        "enum": ["student_info", "lesson_plan", "past_problems"],
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
                        "enum": ["student_info", "lesson_plan", "past_problems"],
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
            "description": "Use this when you want to finish the current question/topic and start a new one. This will start a new conversation with fresh messages, but you will be reminded of your notes at the beginning. You will have a chance to update your notes beforehand.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "The reason for finishing this question/topic (e.g., 'Student requested new topic', 'Student has mastered this concept', 'Student is struggling too much')"
                    }
                },
                "required": ["reason"]
            }
        },
        {
            "name": "calculator",
            "description": "Computes the result of a given mathematical expression",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": 'The expression, using Python syntax, such as "(3.5 + 4) * 5". For security reasons, the only allowed input characters are 0-9, ., +, -, *, /, space, and parentheses.'
                    }
                },
                "required": ["expression"]
            }
        },
    ]

    session['llm_wants_new_question'] = False

    if 'chat_id' not in session:
        session['chat_id'] = get_latest_chat_id(session['student_name_safe'])
        print(colored(f'There was no chat ID in the session, so we assigned the latest ID for this student: {session["chat_id"]}', 'green'))
    else:
        print(colored(f'Chat session ID: {session["chat_id"]}', 'green'))
    
    need_to_call_llm = False
    try:
        messages = load_chat_history(session['student_name_safe'], session['chat_id'])
    except FileNotFoundError:
        messages = []

    if not messages:
        print(colored(f'No chat history found for this student and chat ID. Creating first user message.', 'yellow'))
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
                retries = 3
                for attempt in range(retries):
                    try:
                        messages = call_llm_with_tools(
                            session['student_name_safe'], 
                            make_system_prompt(),
                            messages, 
                            tools, 
                            verbose_output=VERBOSE_OUTPUT
                        )
                        break
                    except Exception as e:
                        print(colored(f'Error calling LLM (attempt {attempt + 1}): {e}', 'red'))
                        if attempt == retries - 1:  # If it's the last attempt
                            messages.append({"role": "assistant", "content": f"Error calling LLM: {e}. <to_student>I had a problem and couldn't respond. Please try again.</to_student>"})

                # Save chat history to file
                save_chat_history(
                    session['student_name_safe'],
                    session['chat_id'],
                    messages
                )

            # Start new chat session
            session['chat_id'] = f'{int(get_latest_chat_id(session["student_name_safe"])) + 1:06d}'
            print(colored(f'New chat session started. Assigning ID: {session["chat_id"]}', 'green'))
            messages = [{"role": "user", "content": make_first_user_message(session['student_name_safe'])}]
            need_to_call_llm = True
            
        user_input = request.form.get('user_input')
        if user_input:
            wrapped_input = f"Timestamp: {get_timestamp()}\n<from_student>{user_input}</from_student>"
            messages.append({"role": "user", "content": wrapped_input})
            need_to_call_llm = True

    if need_to_call_llm:
        input_token_count = count_tokens(messages, tools)
        if VERBOSE_OUTPUT:
            print(colored(f'Input token count: {input_token_count}', 'green'))

        retries = 3
        for attempt in range(retries):
            try:
                messages = call_llm_with_tools(
                    session['student_name_safe'], 
                    make_system_prompt(),
                    messages, 
                    tools, 
                    verbose_output=VERBOSE_OUTPUT
                )
                break
            except Exception as e:
                print(colored(f'Error calling LLM (attempt {attempt + 1}): {e}', 'red'))
                if attempt == retries - 1:  # If it's the last attempt
                    messages.append({"role": "assistant", "content": f"Error calling LLM: {e}. <to_student>I had a problem and couldn't respond. Please try again.</to_student>"})

        # Check if LLM called finish_question
        llm_wants_new_question = False
        for message in messages:
            if isinstance(message.get('content'), list):
                for content_item in message['content']:
                    if isinstance(content_item, anthropic.types.tool_use_block.ToolUseBlock):
                        if content_item.name == 'finish_question':
                            llm_wants_new_question = True
                            break

        # Check if max input tokens reached
        if input_token_count > MAX_INPUT_TOKENS:
            print(colored('Conversation reached maximum length. Starting a new question.', 'red'))
            llm_wants_new_question = True

        session['llm_wants_new_question'] = llm_wants_new_question
        if llm_wants_new_question:
            print(colored(f'LLM wants to start a new question', 'yellow'))

        # Save chat history to file
        save_chat_history(
            session['student_name_safe'],
            session['chat_id'],
            messages
        )
    
    # Check if lesson plan has changed so we can show an indicator in chat.html
    current_hash = get_lesson_plan_hash(session['student_name_safe'])
    lesson_plan_is_new = False
    
    if 'lesson_plan_hash' not in session:
        session['lesson_plan_hash'] = current_hash
    elif session['lesson_plan_hash'] != current_hash:
        lesson_plan_is_new = True
        session['lesson_plan_hash'] = current_hash

    #extract only the text that should be visible to the student for displaying in chat.html
    chat_messages = extract_chat_messages(messages)

    # Get prior chat messages for displaying in chat.html
    prior_chat_messages = []
    if os.path.exists('data'):
        current_chat_id = int(session['chat_id'])
        files = [f for f in os.listdir('data') 
                if f.startswith(f"{session['student_name_safe']}_chathistory_") 
                and f.endswith('.pkl')]
        
        # Extract chat IDs and sort them
        chat_histories = []
        for file in files:
            try:
                chat_id = int(file.split('_chathistory_')[1].split('.pkl')[0])
                if chat_id < current_chat_id:
                    chat_histories.append((chat_id, file))
            except (IndexError, ValueError):
                continue
        
        chat_histories.sort()
        
        # Load and process each chat history
        for _, filename in chat_histories:
            try:
                prior_messages = load_chat_history(session['student_name_safe'], 
                                                 filename.split('_chathistory_')[1].split('.pkl')[0])
                prior_chat_messages.extend(extract_chat_messages(prior_messages))
            except (FileNotFoundError, pickle.UnpicklingError) as e:
                print(colored(f'Error loading prior chat history {filename}: {e}', 'red'))
                continue

    return render_template('chat.html', 
                         chat_messages=chat_messages,
                         student_name_safe=session.get('student_name_safe'),
                         llm_wants_new_question=session.get('llm_wants_new_question', False),
                         lesson_plan=get_notes(session['student_name_safe'], 'lesson_plan'),
                         lesson_plan_is_new=lesson_plan_is_new,
                         prior_chat_messages=prior_chat_messages)


@app.route('/delete_student/<student_name>')
def delete_student(student_name):
    student_name_safe = ''.join(c for c in student_name if c.isalnum() or c in '-_').lower()
    
    # Delete all files associated with the student
    if os.path.exists('data'):
        files = os.listdir('data')
        for file in files:
            if file.startswith(student_name_safe):
                os.remove(os.path.join('data', file))
    
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(port=8001, debug=True)
