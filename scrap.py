import anthropic
anthropic_client = anthropic.Anthropic()
import json

MODEL_NAME = 'claude-3-5-sonnet-latest'
messages = [
    {"role": "user", "content": 'Hi how are you'}, 
    {"role": "assistant", "content": 'Good I am. Sentences I use in reverse order!'},
    {"role": "user", "content": ['OK! Sounds good to me. Why do you talk like that?']}, 
]
response = anthropic_client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192,
            messages=messages
        )

#for message in messages:
messages_for_serialize = []
for message in messages:
    message_text = ''
    if type(message['content'])==str:
        message_text = message['content']
    elif type(message['content'])==list:
        for content_item in message['content']:
            if type(content_item)==anthropic.types.text_block.TextBlock:
                message_text += content_item.text + '\n\n'
            if type(content_item)==anthropic.types.tool_use_block.ToolUseBlock:
                message_text += f'<tool_call>\nName: {content_item.name}\nID: {content_item.id}\nInput: {content_item.input}\n</tool_call>\n\n'
            if type(content_item)==dict:
                message_text += json.dumps(content_item) + '\n\n'
    messages_for_serialize.append({'role': message['role'], 'content': message_text})

for message in messages_for_serialize:
    print('\nNEXT MESSAGE\n\n')
    print(message['content'])
