import json
import os
from termcolor import colored
from datetime import datetime
import re
from dotenv import load_dotenv
from anthropic import AuthenticationError

load_dotenv()

import anthropic
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY',"no_key_supplied"), timeout=30)

MODEL_NAME = 'claude-3-5-sonnet-latest'

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def count_tokens(messages, tools=None):
    response = anthropic_client.beta.messages.count_tokens(
        model=MODEL_NAME,
        tools=tools,
        messages=messages,
    )
    return response.input_tokens


def get_notes(student_name_safe, note_topic):
    try:
        with open(f'data/{student_name_safe}_{note_topic}.txt', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: No notes found for {note_topic}"


def edit_notes(student_name_safe, note_topic, old_excerpt=None, new_excerpt=None):
    try:
        # Return error if both excerpts are empty
        if not old_excerpt and not new_excerpt:
            return "Error: Both old_excerpt and new_excerpt cannot be empty"
            
        current_notes = get_notes(student_name_safe, note_topic)
        if not old_excerpt:  # If no old_excerpt, replace the entire note
            new_notes = new_excerpt
        else:
            if old_excerpt not in current_notes:
                return f"Error: Could not find the exact text to replace in {note_topic} notes"
            # Replace old_excerpt with new_excerpt if new_excerpt is not empty, otherwise just remove old_excerpt
            new_notes = current_notes.replace(old_excerpt, new_excerpt if new_excerpt else "")
        
        with open(f'data/{student_name_safe}_{note_topic}.txt', 'w') as f:
            f.write(new_notes)
        return f"Changes saved. New version of {note_topic} notes:\n{new_notes}"
    except Exception as e:
        return f"Error: {str(e)}"


def finish_question(student_name_safe, reason):
    return ("FINISH_QUESTION: " + reason)


def calculator(student_name_safe, expression):
    expression = re.sub(r'[^0-9.+*/() -]', '', expression)
    try:
        return eval(expression)
    except Exception as e:
        return f"Error: {str(e)}"


def call_llm_with_tools(student_name_safe, system_prompt, messages, tools=None, max_turns=10, verbose_output=False):
    turn_i = 0
    first_turn = True
    while first_turn or response.stop_reason == "tool_use":
        first_turn = False

        retries = 3
        for attempt in range(retries):
            try:
                response = anthropic_client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=tools,
                    messages=messages
                )
                break
            except AuthenticationError as e:
                print(colored(f'Error calling LLM (attempt {attempt + 1}): {e}', 'red'))
                error_message = {
                    "role": "assistant",
                    "content": "<to_student>Sorry, I could not authenticate with the given Anthropic API key. Please check your API key and try again.</to_student>"
                }
                messages.append(error_message)
                return messages
            except Exception as e:
                print(colored(f'Error calling LLM (attempt {attempt + 1}): {e}', 'red'))
                if attempt == retries - 1:  # If it's the last attempt
                    error_message = {
                        "role": "assistant", 
                        "content": f"<to_student>I apologize, but I encountered an error: {str(e)}. Please type a new message to try again.</to_student>"
                    }
                    messages.append(error_message)
                    return messages
        
        if turn_i >= max_turns:
            if verbose_output:
                print(colored(f'Max turns reached ({max_turns})', 'red'))
            return messages
            #raise ValueError(f'Max turns reached ({max_turns})')

        user_content_list = []
        finish_question_tool_called = False
        for tool_use in [block for block in response.content if block.type == "tool_use"]:
            tool_name = tool_use.name
            tool_input = tool_use.input

            if verbose_output:
                print(f"\n{colored(f'Tool Used: {tool_name}', 'green')}")
                print(f"  {colored('Tool Input:', 'yellow')}")
                print(colored(json.dumps(tool_input, indent=2), 'yellow'))
            
            try:
                if tool_name in globals() and tools and any(tool['name'] == tool_name for tool in tools):
                    tool_function = globals()[tool_name]
                    tool_result = tool_function(
                        student_name_safe,  # Always pass student_name_safe as first arg
                        **tool_input  # Unpack remaining parameters from tool input
                    )
                    if tool_name == 'finish_question':
                        finish_question_tool_called = True
                else:
                    tool_result = f'Error: Tool {tool_name} not found'
                if verbose_output:
                    print(f'  {colored(f"Tool Result: {tool_result}", "blue")}')
            except Exception as e:
                if verbose_output:
                    print(f'  {colored(f"Error: {e}", "red")}')
                tool_result = f'Error: {e}'

            user_content_list.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": str(tool_result),
            })

        if turn_i == max_turns-1:
            user_content_list.append({
                "type": "text",
                "text": "WARNING: Maximum number of turns reached. You get one more response. Do not call any more tools."
            })

        if response.content != []:
            messages.append({"role": "assistant", "content": response.content})

        if user_content_list:
            messages.append({
                "role": "user",
                "content": user_content_list,
            })

        if finish_question_tool_called:
            break

        turn_i += 1

    return messages


def format_html_w_tailwind(html_text):
    """Format HTML text to be more readable by adding Tailwind CSS classes"""
    html_text = html_text.replace('<ul>', '<ul class="list-disc ml-4">')
    html_text = html_text.replace('<a ', '<a target="_blank" class="text-indigo-600 hover:underline" ')
    html_text = html_text.replace('<p>', '<p class="mt-2">')
    html_text = html_text.replace('<h1>', '<h1 class="text-2xl font-bold mt-4">')
    html_text = html_text.replace('<h2>', '<h2 class="text-xl font-bold mt-4">')
    html_text = html_text.replace('<h3>', '<h3 class="text-lg font-bold mt-4">')
    html_text = html_text.replace('<h4>', '<h4 class="text-base font-bold mt-4">')
    html_text = html_text.replace('<strong>', '<strong class="font-bold">')
    html_text = html_text.replace('<em>', '<em class="italic">')
    html_text = html_text.replace('<blockquote>', '<blockquote class="border-l-4 border-gray-300 pl-4 italic">')
    html_text = html_text.replace('<code>', '<code class="bg-gray-200 p-1 rounded">')
    html_text = html_text.replace('<pre>', '<pre class="bg-gray-200 p-2 rounded overflow-x-auto whitespace-pre-wrap">')    
    return html_text

