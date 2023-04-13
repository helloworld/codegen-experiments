import os
import rich.box
import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from rich.live import Live
from rich.panel import Panel
import re

import uuid
from collections import Counter


def detect_indentation(lines):
    indent_counts = Counter()
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if indent > 0:
            indent_counts[indent] += 1

    if not indent_counts:
        return 4  # Default to 4 spaces

    return indent_counts.most_common(1)[0][0]


def read_file(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()
    return lines


def add_uids_to_code(code_str):
    lines = code_str.splitlines(True)
    indentation = detect_indentation(lines)
    indent_space = " " * indentation

    def add_uid(match):
        block = match.group(0)
        uid = str(uuid.uuid4())[:8]

        # Add start marker
        block_with_start_marker = f"# UID_START_{uid}\n{block}"

        # Add end marker
        lines = block_with_start_marker.splitlines(True)
        last_line = lines[-1]
        lines[-1] = f"{last_line.rstrip()}\n# UID_END_{uid}\n"
        block_with_both_markers = "".join(lines)

        return block_with_both_markers

    block_pattern = rf"(?P<block>^def .+\):(?:\n(?:{indent_space}.+\n)+)+)|(?:^(?:{indent_space}.+\n)+)(?:\n{{2}})?"

    # Add UIDs for top-level functions and blocks within functions separated by double newlines
    code_str = re.sub(block_pattern, add_uid, code_str, flags=re.MULTILINE)

    return code_str


def call_openai_api(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are an expert Python programmer that is helping with editing code.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        stream=True,
    )

    collected_messages = []

    content = ""
    live_panel = Panel(content, expand=True, box=rich.box.ROUNDED)
    with Live(live_panel, console=console, auto_refresh=True) as live:
        for chunk in response:
            chunk_message = chunk["choices"][0]["delta"]
            collected_messages.append(chunk_message)

            content += chunk_message.get("content", "")
            live_panel = Panel(content, expand=True, box=rich.box.ROUNDED)
            live.update(live_panel)

    full_reply_content = "".join([m.get("content", "") for m in collected_messages])
    return full_reply_content


def get_indent_space(block):
    match = re.match(r"\s*", block)
    return match.group() if match else ""


def parse_ai_response(response, original_code):
    edits = {}
    edit_markers = re.finditer(
        r"# EDIT_START: (.+?)\n(.*?)\n# EDIT_END: \1",
        response,
        re.MULTILINE | re.DOTALL,
    )
    for match in edit_markers:
        uid = match.group(1)
        new_code = match.group(2)
        edits[uid] = new_code

    def replace_block(m):
        uid = m.group("uid")
        original_block = m.group("block")
        indent_space = get_indent_space(original_block)

        if uid in edits:
            new_code = edits[uid]
            # Preserve the indentation
            indented_new_code = "\n".join(
                [indent_space + line if line else "" for line in new_code.splitlines()]
            )
            return indented_new_code
        else:
            return original_block

    updated_code = re.sub(
        r"(?P<block># UID_START_(?P<uid>[^\n]+).+?# UID_END_\2)",
        replace_block,
        original_code,
        flags=re.MULTILINE | re.DOTALL,
    )

    return updated_code


def update_code_file(file_path, new_code):
    with open(file_path, "w") as file:
        file.write(new_code)


def process_code(file_path, instructions):
    # Read the file and add UUID markers
    lines = read_file(file_path)
    original_code = "".join(lines)
    code_with_markers = add_uids_to_code("".join(lines))
    display_code(code_with_markers)

    # Generate the prompt for the OpenAI API
    prompt = f"""
Please review the following Python code and make minimal edits according to the instructions provided. 
The code contains UUID markers that indicate the start and end of a code block. 

Use the following edit instruction scheme to specify the edits you want to make:
1. Identify the UUID marker of the block you want to edit.
2. Create an edit marker with the format: # EDIT_START: <UUID>
3. Write the new code.
4. Create an edit end marker with the format: # EDIT_END: <UUID>

For example, if you need to edit a block with the UUID '1234-5678-90ab', the edit should look like this:

# EDIT_START: 1234-5678-90ab
New code goes here
# EDIT_END: 1234-5678-90ab

First, think step by step about what edits to make and explain them. Then provide the edits.

In your output, only include the edits you want to make. Do not include the original code or the edit instructions.

Instructions:  {instructions}

Original Code with markers:

```
{code_with_markers}
```
""".strip()

    # Call the OpenAI API
    response = call_openai_api(prompt)

    # Parse the AI response and update the original code
    updated_code = parse_ai_response(response, code_with_markers)

    console.print("[bold green]Original Code:[/bold green]")
    display_code(original_code)

    updated_code_no_markers = re.sub(
        r"# UID_[^\n]+\n",
        "",
        updated_code,
    )

    return updated_code_no_markers


def display_code(code):
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="Code"))


console = Console()
path_completer = PathCompleter(only_directories=False)

file_path = prompt("Please enter the path to the code file: ", completer=path_completer)
while not os.path.isfile(file_path):
    console.print("[bold red]Invalid file path. Please try again.[/bold red]")
    file_path = prompt(
        "Please enter the path to the code file: ", completer=path_completer
    )

while True:
    instructions = console.input("Please provide instructions or type 'quit' to exit: ")
    if instructions.strip().lower() == "quit":
        break

    updated_code = process_code(file_path, instructions=instructions)
    console.print("[bold green]Updated code with the AI's suggestions:[/bold green]")
    display_code(updated_code)

    user_feedback = console.input("Is this correct? (yes/no): ")
    if user_feedback.strip().lower() == "yes":
        console.print("[bold green]Great! Updating the code file.[/bold green]")
        update_code_file(
            file_path, updated_code
        )  # Update the file only when the user confirms
    else:
        console.print("[bold yellow]Please provide new instructions.[/bold yellow]")
