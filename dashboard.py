from flask import Flask, request, jsonify, render_template, send_from_directory
import ollama
from datetime import datetime
import uuid
import discord
import asyncio
import threading
import os
from discord.ext import commands
import re
import json
from pathlib import Path
import subprocess
import shutil

app = Flask(__name__)

# Role to LLM mapping for Ghidorah (three-headed dragon)
ROLE_LLM_MAPPING = {
    'code_generation': 'qwen2.5-coder:1.5b',
    'analysis': 'llama3.2:3b',
    'creative_writing': 'gemma2:2b',
    'problem_solving': 'llama3.2:3b',
    'research': 'gemma2:2b',
    'debugging': 'qwen2.5-coder:1.5b'
}

# Model display names
MODEL_DISPLAY_NAMES = {
    'llama3.2:3b': 'LLAMA 3.2',
    'qwen2.5-coder:1.5b': 'QWEN 2.5 CODER',
    'gemma2:2b': 'GEMMA2'
}

# Model colors for UI
MODEL_COLORS = {
    'llama3.2:3b': '#00ffff',  # Cyan
    'qwen2.5-coder:1.5b': '#ff0040',  # Red
    'gemma2:2b': '#ffff00'  # Yellow
}

# Conversation state storage
conversations = {}

# Discord bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'YOUR_BOT_TOKEN_HERE')
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# File editing configuration
CODE_EDITING_ENABLED = True
EDITABLE_EXTENSIONS = ['.py', '.js', '.html', '.css', '.md']
EDITED_FILES_LOG = []

# Git integration configuration
GIT_ENABLED = False
GIT_REPO_PATH = os.getcwd()
AUTOMATION_COMMITS = []

# Head-to-head-to-head communication
HEAD_SEQUENCE = [
    ('llama3.2:3b', 'LLAMA 3.2', '#00ffff', 'Analysis Head'),
    ('qwen2.5-coder:1.5b', 'QWEN 2.5 CODER', '#ff0040', 'Code Head'),
    ('gemma2:2b', 'GEMMA2', '#ffff00', 'Creative Head')
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/roles', methods=['GET'])
def get_roles():
    return jsonify({
        'roles': [
            {'id': 'code_generation', 'name': 'Code Generation', 'llm': 'qwen2.5-coder:1.5b'},
            {'id': 'analysis', 'name': 'Analysis', 'llm': 'llama3.2:3b'},
            {'id': 'creative_writing', 'name': 'Creative Writing', 'llm': 'gemma2:2b'},
            {'id': 'problem_solving', 'name': 'Problem Solving', 'llm': 'llama3.2:3b'},
            {'id': 'research', 'name': 'Research', 'llm': 'gemma2:2b'},
            {'id': 'debugging', 'name': 'Debugging', 'llm': 'qwen2.5-coder:1.5b'},
            {'id': 'all_three', 'name': 'All Three Heads', 'llm': 'all'}
        ],
        'models': [
            {'id': 'llama3.2:3b', 'name': 'LLAMA 3.2', 'color': '#00ffff'},
            {'id': 'qwen2.5-coder:1.5b', 'name': 'QWEN 2.5 CODER', 'color': '#ff0040'},
            {'id': 'gemma2:2b', 'name': 'GEMMA2', 'color': '#ffff00'}
        ]
    })

@app.route('/chat', methods=['POST'])
def chat():
    print("--- Received Chat Request ---")
    data = request.get_json()
    user_prompt = data.get('prompt', '')
    role = data.get('role', 'analysis')
    conversation_id = data.get('conversation_id')
    start_time = datetime.now()

    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        conversations[conversation_id] = []

    try:
        if role == 'all_three':
            # Get responses from all three models
            models = ['llama3.2:3b', 'qwen2.5-coder:1.5b', 'gemma2:2b']
            responses = {}

            for model in models:
                print(f"Asking {model}...")
                messages = [{'role': 'user', 'content': user_prompt}]
                if conversation_id in conversations:
                    messages = conversations[conversation_id] + messages

                res = ollama.chat(model=model, messages=messages)
                responses[model] = {
                    'response': res['message']['content'],
                    'model': model,
                    'display_name': MODEL_DISPLAY_NAMES[model],
                    'color': MODEL_COLORS[model]
                }
                print(f"{model} finished.")

            # Store all responses in conversation history
            for model, response_data in responses.items():
                conversations[conversation_id].extend([
                    {'role': 'user', 'content': f"[{MODEL_DISPLAY_NAMES[model]}] {user_prompt}"},
                    {'role': 'assistant', 'content': response_data['response'], 'model': model}
                ])

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            return jsonify({
                'all_responses': responses,
                'role': role,
                'conversation_id': conversation_id,
                'timestamp': end_time.isoformat(),
                'processing_time': processing_time,
                'mode': 'all_three'
            })
        else:
            # Single model response
            model = ROLE_LLM_MAPPING.get(role, 'llama3.2:3b')
            print(f"Asking {model} for role: {role}")

            # Build conversation history
            messages = [{'role': 'user', 'content': user_prompt}]
            if conversation_id in conversations:
                messages = conversations[conversation_id] + messages

            res = ollama.chat(model=model, messages=messages)
            output = res['message']['content']

            # Store in conversation history
            conversations[conversation_id].extend([
                {'role': 'user', 'content': user_prompt},
                {'role': 'assistant', 'content': output, 'model': model}
            ])

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            print(f"{model} finished.")

            return jsonify({
                'response': output,
                'model': model,
                'display_name': MODEL_DISPLAY_NAMES.get(model, model),
                'color': MODEL_COLORS.get(model, '#00ffff'),
                'role': role,
                'conversation_id': conversation_id,
                'timestamp': end_time.isoformat(),
                'processing_time': processing_time,
                'mode': 'single'
            })

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/handoff', methods=['POST'])
def handoff():
    print("--- Received Handoff Request ---")
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    current_role = data.get('current_role')
    task_summary = data.get('task_summary', '')

    if not conversation_id or conversation_id not in conversations:
        return jsonify({'error': 'Invalid conversation ID'}), 400

    # Determine the other LLM
    if current_role == 'code_generation':
        target_role = 'analysis'
        target_model = 'llama3.2:3b'
    else:
        target_role = 'code_generation'
        target_model = 'qwen2.5-coder:1.5b'

    try:
        # Create handoff prompt
        handoff_prompt = f"""The previous task was completed by the {current_role} model. Here's a summary:
{task_summary}

Please provide your suggestions, improvements, or additional insights on this task from your {target_role} perspective."""

        messages = conversations[conversation_id] + [
            {'role': 'user', 'content': handoff_prompt}
        ]

        print(f"Handing off to {target_model} for {target_role}")
        res = ollama.chat(model=target_model, messages=messages)
        output = res['message']['content']

        # Store handoff in conversation
        conversations[conversation_id].extend([
            {'role': 'user', 'content': f"[HANDOFF] {handoff_prompt}"},
            {'role': 'assistant', 'content': output}
        ])

        print(f"Handoff to {target_model} completed.")

        return jsonify({
            'response': output,
            'model': target_model,
            'role': target_role,
            'conversation_id': conversation_id,
            'timestamp': datetime.now().isoformat(),
            'handoff_from': current_role
        })

    except Exception as e:
        print(f"ERROR in handoff: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/edits', methods=['GET'])
def get_edits():
    """Get recent file edits"""
    return jsonify({
        'edits': EDITED_FILES_LOG[-20:],  # Return last 20 edits
        'total_edits': len(EDITED_FILES_LOG),
        'auto_editing_enabled': CODE_EDITING_ENABLED
    })

@app.route('/toggle-editing', methods=['POST'])
def toggle_editing_endpoint():
    """Toggle automatic code editing"""
    global CODE_EDITING_ENABLED
    CODE_EDITING_ENABLED = not CODE_EDITING_ENABLED
    
    return jsonify({
        'auto_editing_enabled': CODE_EDITING_ENABLED,
        'message': f"Automatic code editing {'enabled' if CODE_EDITING_ENABLED else 'disabled'}"
    })

@app.route('/implement', methods=['POST'])
def manual_implement_endpoint():
    """Manually implement a feature suggestion"""
    data = request.get_json()
    suggestion = data.get('suggestion', '')
    
    if not suggestion:
        return jsonify({'error': 'No suggestion provided'}), 400
    
    try:
        file_path, result = implement_feature_suggestion(suggestion)
        
        if file_path:
            return jsonify({
                'success': True,
                'file_path': file_path,
                'result': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/git/status', methods=['GET'])
def git_status():
    """Get Git repository status"""
    if not GIT_ENABLED:
        return jsonify({'error': 'Git integration disabled'}), 400
    
    try:
        status_result = run_git_command('git status --porcelain', 'Get Git status')
        log_result = run_git_command('git log --oneline -10', 'Get recent commits')
        
        return jsonify({
            'git_enabled': True,
            'repo_path': GIT_REPO_PATH,
            'status': status_result,
            'recent_commits': log_result,
            'automation_commits': AUTOMATION_COMMITS[-5:]  # Last 5 automation commits
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/git/commit', methods=['POST'])
def git_commit_endpoint():
    """Manually trigger Git commit"""
    if not GIT_ENABLED:
        return jsonify({'error': 'Git integration disabled'}), 400
    
    data = request.get_json()
    message = data.get('message', 'Manual commit')
    
    try:
        result = run_git_command(f'git commit -m "{message}"', 'Manual commit')
        return jsonify({
            'success': True,
            'result': result,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history/<conversation_id>', methods=['GET'])
def get_history(conversation_id):
    if conversation_id not in conversations:
        return jsonify({'error': 'Conversation not found'}), 404

    return jsonify({
        'conversation_id': conversation_id,
        'history': conversations[conversation_id]
    })

@app.route('/automation', methods=['POST'])
def automation_endpoint():
    """Dedicated automation workflow endpoint"""
    print("--- Received Automation Request ---")
    data = request.get_json()
    user_prompt = data.get('prompt', '')
    conversation_id = data.get('conversation_id')
    start_time = datetime.now()
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    try:
        # Run automation workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(automation_workflow(user_prompt, conversation_id))
        loop.close()
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        if result.get('automation_complete'):
            return jsonify({
                'workflow_results': result['workflow_results'],
                'original_prompt': result['original_prompt'],
                'conversation_id': conversation_id,
                'timestamp': end_time.isoformat(),
                'processing_time': processing_time,
                'mode': 'automation'
            })
        else:
            return jsonify({'error': result.get('error', 'Automation failed')}), 500
            
    except Exception as e:
        print(f"ERROR in automation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/head-to-head', methods=['POST'])
def head_to_head():
    """Web endpoint for head-to-head-to-head communication"""
    print("--- Received Head-to-Head Request ---")
    data = request.get_json()
    user_prompt = data.get('prompt', '')
    conversation_id = data.get('conversation_id')
    start_time = datetime.now()

    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    try:
        # Run the async function in the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(head_to_head_response(user_prompt, conversation_id))
        loop.close()

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return jsonify({
            'head_responses': result['head_responses'],
            'final_response': result['final_response'],
            'original_prompt': result['original_prompt'],
            'conversation_id': conversation_id,
            'timestamp': end_time.isoformat(),
            'processing_time': processing_time,
            'mode': 'head_to_head'
        })

    except Exception as e:
        print(f"ERROR in head-to-head: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Keep the old endpoint for backward compatibility
@app.route('/predict', methods=['POST'])
def predict():
    print("--- Received Request ---")
    data = request.get_json()
    user_prompt = data.get('prompt', 'Hello')

    try:
        print(f"Asking Llama 3.2...")
        res1 = ollama.chat(model='llama3.2:3b', messages=[{'role': 'user', 'content': user_prompt}])
        output1 = res1['message']['content']
        print("Llama finished.")

        print(f"Asking Qwen 2.5 Coder...")
        res2 = ollama.chat(model='qwen2.5-coder:1.5b', messages=[{'role': 'user', 'content': user_prompt}])
        output2 = res2['message']['content']
        print("Qwen finished.")

        return jsonify({
            'llama_output': output1,
            'qwen_output': output2
        })

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

def extract_file_path_from_suggestion(text):
    """Extract file path from feature suggestion"""
    text_lower = text.lower()
    
    # Look for file patterns like "file.py", "script.js", etc.
    file_patterns = [
        r'([\w\-\/\.]+\.(py|js|html|css|md))',
        r'"([\w\-\/\.]+\.(py|js|html|css|md))"',
        r'`([\w\-\/\.]+\.(py|js|html|css|md))`'
    ]
    
    for pattern in file_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            return matches[0][0] if isinstance(matches[0], tuple) else matches[0]
    
    # Default to common files if no specific file mentioned
    if 'python' in text_lower or 'py' in text_lower:
        return 'main.py'
    elif 'javascript' in text_lower or 'js' in text_lower:
        return 'script.js'
    elif 'html' in text_lower:
        return 'index.html'
    elif 'css' in text_lower:
        return 'style.css'
    
    return None

def implement_feature_suggestion(suggestion_text, file_path=None):
    """Use Code Head to implement a feature suggestion"""
    try:
        if not file_path:
            file_path = extract_file_path_from_suggestion(suggestion_text)
        
        if not file_path:
            return None, "No specific file mentioned in the suggestion"
        
        # Check if file exists
        file_path = Path(file_path)
        if not file_path.exists():
            # Create new file
            file_path.touch()
            current_content = ""
        else:
            # Read existing content
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        
        # Create prompt for Code Head to implement the feature
        implementation_prompt = f"""You are the Code Head. The Creative Head suggested: "{suggestion_text}"

File: {file_path}
Current content:
```
{current_content}
```

Please implement this feature by providing the complete updated file content. Only respond with the code, no explanations.

If creating a new file, provide the complete initial code.
If modifying existing code, provide the complete updated code.

Make sure the code is syntactically correct and follows best practices."""
        
        # Get implementation from Code Head
        loop = asyncio.get_event_loop()
        res = loop.run_in_executor(None, 
            lambda: ollama.chat(model='qwen2.5-coder:1.5b', messages=[{'role': 'user', 'content': implementation_prompt}]))
        
        implemented_code = res['message']['content'].strip()
        
        # Clean up the response (remove markdown code blocks if present)
        if implemented_code.startswith('```'):
            lines = implemented_code.split('\n')
            if lines[0].startswith('```'):
                implemented_code = '\n'.join(lines[1:-1]) if lines[-1] == '```' else '\n'.join(lines[1:])
        
        # Write the implemented code to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(implemented_code)
        
        # Log the edit
        edit_log = {
            'timestamp': datetime.now().isoformat(),
            'file_path': str(file_path),
            'suggestion': suggestion_text,
            'implemented_by': 'QWEN 2.5 CODER (Code Head)',
            'file_created': not bool(current_content)
        }
        EDITED_FILES_LOG.append(edit_log)
        
        return str(file_path), f"✅ Successfully implemented feature in {file_path}"
        
    except Exception as e:
        return None, f"❌ Error implementing feature: {str(e)}"


def run_git_command(command, description):
    """Run a git command and return the output"""
    try:
        result = subprocess.run(
            command.split(),
            cwd=GIT_REPO_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        return f"Error: {str(e)}"


async def automation_workflow(user_prompt, conversation_id):
    """Run automation workflow with all three heads"""
    try:
        workflow_results = []
        
        for model, display_name, color, head_name in HEAD_SEQUENCE:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None, 
                lambda m=model: ollama.chat(model=m, messages=[{'role': 'user', 'content': user_prompt}])
            )
            workflow_results.append({
                'response': res['message']['content'],
                'model': model,
                'display_name': display_name,
                'color': color,
                'head_name': head_name
            })
        
        return {
            'automation_complete': True,
            'workflow_results': workflow_results,
            'original_prompt': user_prompt
        }
    except Exception as e:
        return {'automation_complete': False, 'error': str(e)}


async def head_to_head_response(user_prompt, conversation_id):
    """Get responses from all three heads in sequence with context passing"""
    responses = []
    current_context = user_prompt
    
    for i, (model, display_name, color, head_name) in enumerate(HEAD_SEQUENCE):
        # Build messages with previous head's response
        messages = [{'role': 'user', 'content': current_context}]
        
        if i > 0:
            # Include previous head's response for context
            messages.append({
                'role': 'assistant', 
                'content': f"Previous head ({HEAD_SEQUENCE[i-1][3]}) response: {responses[-1]['response']}"
            })
            messages.append({
                'role': 'user', 
                'content': f"Now {head_name}, please respond to the original prompt considering the previous input: {user_prompt}"
            })
        
        # Get response from current head
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: ollama.chat(model=model, messages=messages))
        response_text = res['message']['content']
        
        responses.append({
            'response': response_text,
            'model': model,
            'display_name': display_name,
            'color': color,
            'head_name': head_name
        })
    
    # Create final synthesized response
    final_prompt = f"""Based on the following responses from three AI heads, synthesize a final comprehensive answer:

Original question: {user_prompt}

"""
    for resp in responses:
        final_prompt += f"{resp['head_name']}: {resp['response']}\n\n"
    
    final_prompt += "Please provide a synthesized final response combining the best insights from all three heads."
    
    loop = asyncio.get_event_loop()
    final_res = await loop.run_in_executor(
        None, 
        lambda: ollama.chat(model='llama3.2:3b', messages=[{'role': 'user', 'content': final_prompt}])
    )
    
    return {
        'head_responses': responses,
        'final_response': final_res['message']['content'],
        'original_prompt': user_prompt
    }


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')

@bot.command(name='ghidorah')
async def ghidorah(ctx, *, prompt: str):
    """Query all three heads for a synthesized response"""
    await ctx.send("🐉 **Ghidorah is awakening... all three heads are thinking.**")
    
    try:
        # This calls the helper function to get responses from all models
        result = await head_to_head_response(prompt, str(ctx.channel.id))
        
        # Create formatted response
        response_msg = "**🐉 GHIDORAH'S THREE HEADS RESPONSE**\n\n"
        
        for head_resp in result['head_responses']:
            response_msg += f"**{head_resp['head_name']} ({head_resp['display_name']})**:\n{head_resp['response']}\n\n"
        
        response_msg += f"**🔥 FINAL SYNTHESIZED RESPONSE**:\n{result['final_response']}"
        
        # Split if message is too long for Discord (2000 char limit)
        if len(response_msg) > 1900:
            chunks = [response_msg[i:i+1900] for i in range(0, len(response_msg), 1900)]
            for i, chunk in enumerate(chunks):
                await ctx.send(chunk if i == 0 else f"(continued)\n{chunk}")
        else:
            await ctx.send(response_msg)
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='head')
async def single_head(ctx, head_name: str, *, prompt: str):
    """Query a specific head"""
    head_mapping = {
        'analysis': ('llama3.2:3b', 'LLAMA 3.2', 'Analysis Head'),
        'code': ('qwen2.5-coder:1.5b', 'QWEN 2.5 CODER', 'Code Head'),
        'creative': ('gemma2:2b', 'GEMMA2', 'Creative Head')
    }
    
    if head_name.lower() not in head_mapping:
        await ctx.send("Available heads: analysis, code, creative")
        return
    
    model, display_name, head_name_full = head_mapping[head_name.lower()]
    await ctx.send(f"🤔 **{head_name_full} is thinking...**")
    
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: ollama.chat(model=model, messages=[{'role': 'user', 'content': prompt}]))
        
        response = f"**{head_name_full} ({display_name})**:\n{res['message']['content']}"
        await ctx.send(response)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name='implement')
async def manual_implement(ctx, *, suggestion: str):
    """Manually implement a feature suggestion"""
    await ctx.send(f"🔧 **Code Head implementing feature...**\nSuggestion: {suggestion}")
    
    try:
        file_path, result = implement_feature_suggestion(suggestion)
        
        if file_path:
            await ctx.send(f"✅ **Successfully implemented in {file_path}**\n{result}")
        else:
            await ctx.send(f"❌ **Implementation failed**: {result}")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


def run_discord_bot():
    """Run Discord bot in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    # Start Discord bot in background thread
    if DISCORD_TOKEN != 'YOUR_BOT_TOKEN_HERE':
        discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
        discord_thread.start()
        print("Discord bot started in background thread")
    else:
        print("⚠️  Discord token not configured. Set DISCORD_TOKEN environment variable to enable Discord bot.")

    # Threaded=False can sometimes help debug local GPU collisions
    app.run(port=5000, debug=True)
