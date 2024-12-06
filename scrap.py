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


import anthropic
anthropic_client = anthropic.Anthropic()
import pickle
import nh3
from utils import format_html_w_tailwind

with open('data/test-math_chathistory_a96f4149-a941-43b7-9f71-2100856b0ea8.pkl', 'rb') as f:
    messages = pickle.load(f)


item = messages[9]['content'][0].text
tags = set(nh3.ALLOWED_TAGS) | {"svg", "line", "text", "rect", "path", "polygon", "polyline", "ellipse", "circle", "g", "defs", "use", "clipPath", "linearGradient", "stop", "image"}
from copy import deepcopy
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

print(nh3.clean(format_html_w_tailwind(item), tags=tags, attributes=attributes))