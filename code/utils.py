import anthropic
import json
from bs4 import BeautifulSoup

anthropic_client = anthropic.Anthropic()

def get_notes(student_name_safe, note_topic):
    with open(f'data/{student_name_safe}_{note_topic}.txt', 'r') as f:
        return f.read()


def call_llm_with_tools(user_message, student_name_safe, messages=[], tools=None, max_turns=10):
    MODEL_NAME = 'claude-3-5-sonnet-latest'
    messages.append({"role": "user", "content": user_message})

    response = anthropic_client.messages.create(
        model=MODEL_NAME,
        max_tokens=8192,
        temperature=0,
        tools=tools,
        messages=messages
    )
    turn_i = 0
    first_turn = True
    text_to_student = ''
    while first_turn or response.stop_reason == "tool_use":
        first_turn = False
        response = anthropic_client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192,
            temperature=0,
            tools=tools,
            messages=messages
        )

        if turn_i >= max_turns:
            raise ValueError(f'Max turns reached ({max_turns})')

        user_content_list = []

        for tool_use in [block for block in response.content if block.type == "tool_use"]:
            tool_name = tool_use.name
            tool_input = tool_use.input

            print(f"\nTool Used: {tool_name}")
            print(f"  Tool Input:")
            print(json.dumps(tool_input, indent=2))
            if tool_name== 'get_drugs_for_atc_code':
                try:
                    drugs = get_drugs_for_atc_code(tool_input['atc_code'])
                    if drugs:
                        tool_result = ', '.join(drugs)
                    else:
                        tool_result = 'No matching anticancer drugs found'
                    print(f'  Tool Result: {tool_result}')
                except Exception as e:
                    print(f'  Error: {e}')
                    tool_result = f'Error: {e}'
            else:
                print(f'  Unknown tool: {tool_name}')
                tool_result = f'Unknown tool: {tool_name}'
            user_content_list.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": str(tool_result),
            })

        for block in response.content:
            if hasattr(block, 'text'):
                soup = BeautifulSoup(block.text, 'html.parser')
                student_messages = soup.find_all('to_student')
                text_to_student += ' '.join(msg.get_text() for msg in student_messages)

        if turn_i == max_turns-1:
            user_content_list.append({
                "type": "text",
                "text": "WARNING: Maximum number of turns reached. This will be your final response. Do not call any more tools."
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": user_content_list,
        })

        turn_i += 1

    return text_to_student