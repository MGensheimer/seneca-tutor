import os
from datetime import datetime
from utils import get_notes, call_llm_with_tools

student_name = input('Input the name of the student.\n')
student_name_safe = ''.join(c for c in student_name if c.isalnum() or c in '-_').lower()

note_defaults = {
    'student_info':'No student info.',
    'lesson_plan':'No lesson plan.',
    'past_problems':'No past problems.',
    'personal_interactions':'No personal interactions.'
}
note_topics = note_defaults.keys()

#create student data if it doesn't exist
for topic in note_topics:
    if not os.path.exists(f'data/{student_name_safe}_{topic}.txt'):
        if topic=='student_info':
            user_input = input('Input the student\'s age, gender, desired topic of study, current experience level, and any other information that would be helpful to the tutor.\n')
            text_for_topic = f'User-supplied information for student {student_name} (edit as needed):\n{user_input}'
        else:
            text_for_topic = note_defaults[topic]

        with open(f'data/{student_name_safe}_{topic}.txt', 'w') as f:
            f.write(text_for_topic)

tools = [
    {
        "name": "get_drugs_for_atc_code",
        "description": "List all FDA-approved anticancer drugs for a given 1st-4th level WHO ATC code. If ATC code invalid, returns this fact as a string. This tool can be used with parallel tool use.",
        "input_schema": {
            "type": "object",
            "properties": {
                "atc_code": {
                    "type": "string",
                    "description": "The ATC code, e.g. L01FF (this 4th level code will list all PD-1/PDL-1 inhibitors)"
                }
            },
            "required": ["atc_code"]
        }
    }
]

notes_content = ''
for topic in note_topics:
    notes_content += f'<notes topic="{topic}">\n{get_notes(student_name_safe, topic)}\n</notes>\n'

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
first_prompt = """
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

Before we begin, here is the current content of your notes about the student:
<notes_content>
{notes_content}
</notes_content>

Here is the current timestamp: {timestamp}

Let's get started! Please give the student their first problem. Remember, only text within <to_student> blocks will be shown to the student.
"""