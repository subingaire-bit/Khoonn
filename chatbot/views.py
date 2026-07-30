import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from groq import Groq

# 1. IMPORT YOUR ACTUAL MODEL HERE
from bank.models import Blood 

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are "Kyuu AI", a helpful AI assistant for a Blood Bank Management System.
You can answer questions about blood donation AND you can update the blood inventory.

STRICT RULES:
1. If the user wants to add blood to the inventory, you MUST use the 'add_blood_inventory' tool.
2. NEVER output JSON, function calls, or code blocks to the user. Just talk to them naturally.
3. If the user doesn't provide the blood type or units, ask them for it politely before calling the tool.
4. Keep text responses concise, polite, and professional.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "add_blood_inventory",
            "description": "Add units of a specific blood type to the blood bank inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "blood_type": {
                        "type": "string", 
                        "description": "The blood type to add (e.g., 'A+', 'O-', 'AB+'). Must be standard format."
                    },
                    "units": {
                        "type": "integer", 
                        "description": "The number of units to add to the inventory."
                    }
                },
                "required": ["blood_type", "units"]
            }
        }
    }
]

def execute_add_blood_inventory(args):
    try:
        blood_type = args.get('blood_type', '').strip().upper()
        units = args.get('units', 0)

        if not blood_type or units <= 0:
            return "Error: Invalid blood type or units must be greater than zero."

        blood_obj, created = Blood.objects.get_or_create(name=blood_type, defaults={'unit': 0})
        blood_obj.unit += units
        blood_obj.save()

        return f"Successfully added {units} units of {blood_type} blood. The total inventory for {blood_type} is now {blood_obj.unit} units."
        
    except Exception as e:
        return f"Error saving to database: {str(e)}"

@csrf_exempt
def chatbot_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            chat_history = data.get('history', [])

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": user_message})

            # First API Call
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile", # UPGRADED MODEL
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=500,
                temperature=0.3
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if tool_calls:
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    if function_name == "add_blood_inventory":
                        function_response = execute_add_blood_inventory(function_args)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        })

                # Second API Call
                second_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile", # UPGRADED MODEL
                    messages=messages,
                )
                ai_reply = second_response.choices[0].message.content
            else:
                ai_reply = response_message.content

            return JsonResponse({"reply": ai_reply})
        
        except Exception as e:
            print(f"Error: {str(e)}")
            return JsonResponse({"error": "Failed to process request."}, status=500)
            
    return JsonResponse({"error": "Invalid request"}, status=400)