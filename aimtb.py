

#Imports, all used
import openai
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from flask import Flask, request, session
from flask import Flask
import threading
import numpy as np

#Setting up flask
app = Flask(__name__)
app.secret_key = os.urandom(24)

#setting up variables, to be used throughout.
global flag
form_history = {}
phase_history = {}
chat_history = {}
order_number = 0
phase_three_resp = 0
phase_three_cat = 0 
image_tracker = 0
choice = {}

#Privledges for different users based on phone number. 
mntce = []
engineer = []
with open ('mntce.txt', 'r') as file:
    for line in file:
        mntce.append(line.rstrip())

with open('engineer.txt', 'r', encoding='utf-8-sig') as file:
    for line in file:
        engineer.append(line.strip())

# Set up credentials in keys.txt, put them in one line at a time with no quotations around them and have their names first seperated from values with an = sign
names = {}
with open("keys.txt", "r") as file:
    lines = file.readlines()
    for line in lines:
        key, value = line.strip().split("=")
        names[key] = value
# Access the variables from the config dictionary
openai.api_key = names["api_key"]
twilio_account_sid = names["account_sid"]
twilio_auth_token = names["auth_token"]
twilio_phone_number = names["phone_number"]
model_engine = names["model_engine"]


#initialize client
client = Client(twilio_account_sid, twilio_auth_token)
# Initialize a threading semaphore with a count of 1
semaphore = threading.Semaphore(1)
import time

# Define a function to generate a response from GPT-3 using smaphore
def ai_response(prompt):
    with semaphore:
        #add some delay to ensure not too many requests per min.
        random_number = np.random.randint(1, 15)
        time.sleep(random_number)
        response = openai.Completion.create(
            engine=model_engine,
            prompt=prompt,
            max_tokens=1024,
            stop=None,
            temperature=0.7,
            presence_penalty=.6,
            frequency_penalty=0.0,
        )
        message = response.choices[0].text.strip()
        print(response)
    return message + ""


#Takes message and decides if it's a request or not.
def phase_one(message):
    promptt = """Your job is to determine if the user submitted a maintenance request, or if the user only announced themselves/their interest in submitting a request. Here are some examples:
        User: "i want to submit a request" You: no
        User: "submit maintenance request" You:  no
        User: "My name is Maddy and I want a new chair for my desk" You: yes
        User: "I want to submit a request for building 3-45's air handlers to have their filters replaced" You: yes
        User: "boiler 2 has been offline for 3 days" You: yes
        User: "i want my office in building 4-45 to be moved to 6-67" You: yes
        User: "I want the rose bushes to be trimmed" You: yes
        User: "I want the chiller in 4-45 replaced" You: yes
        User: "I'm hungry.  Can maintenance bring me lunch  to Bldg 328, column B8, second floor?" You: yes
        User: "My name is Lebron James. I'm at building 999 in the Philadelphia site. A plane blew up." You: yes
        User: "Engineering evaluation of solar opportunities in PHL" You: yes
        User: "Estimate the weight of a chinook helicopter" You: yes
        User: "hello?" You: no
        User: "Is this how you submit a request?" You: no
        User: "Do i have the right number" You: no
        Now I will give you the user input.
        """
    fprompt = promptt + "User:" + message + "You:"
  
    back = ai_response(fprompt)
    back = back.lower()
    print(back)
    decision = 0
    # Prevents against response that includes explination
    if "ye" in back:
        decision = 1
    if "no" in back:
        decision = 0
    return decision

#Seperates data into different categories in a JSON format. 
def phase_two(message):
    promt = """I am going to describe to you a maintenance request that I want to submit. Your job is to sort what I say into six categories. Some of the categories may be empty.
                Here are the categories: 
                      1. Contact Information (phone number, email)
                      2. Name 
                      3. Service Requested
                      4. Location (Specific building, site, etc. Often of the form of number-number number 
                      5. Locale (This may be in the form of a column letter followed by a row number, such as B8 or D-3. This could also be descriptions such as "outside, near to...," or a floor/room number.
                      6.  Any additional details that may be important to maintenance staff.
                Any category that has no input, put in NO. Respond in json format.
                The dictionary should be of the format {"Location": "insert location here", "Locale": "insert locale here"} etc. 
                For example:
                User: I want a new chair for my desk in 3-28 You: {'Contact Information': 'NO', 'Name':'NO', 'Service Requested':'New Chair for Desk', 'Location': '3-28', 'Locale': 'NO', 'Additional Details': 'NO'}
                User: Ahu-2 needs its air filters replaced You:  {'Contact Information': 'NO', 'Name':'NO', 'Service Requested':'Replace Filters on AHU-2', 'Location': 'NO', 'Locale': 'NO', 'Additional Details': 'NO'}
                User: My name is Maddy Miller and I want my desk to be replaced with a standing desk.  You:  {'Contact Information': 'NO', 'Name':'Maddy Miller', 'Service Requested':'Replace Desk with Standing Desk', 'Location': 'NO', 'Locale': 'NO', 'Additional Details': 'NO'}
                User: The Ice Machine in 3-209 is out of service again. You:  {'Contact Information': 'NO', 'Name':'NO', 'Service Requested':'Repair Ice Machine', 'Location': '3-209', 'Locale': 'NO', 'Additional Details': 'NO'}
                User: My name is Lebron James. I'm at building 999 in the Philadelphia site. A plane blew up.  You:  {'Contact Information': 'NO', 'Name':'Lebron James', 'Service Requested':'Plane blew up', 'Location': 'Building 999, philidalphea', 'Locale': 'NO', 'Additional Details': 'NO'}
                User: I'm hungry.  Can maintenance bring me lunch  to Bldg 328, column B8, second floor? You:  {'Contact Information': 'NO', 'Name':'NO', 'Service Requested':'Bring Me Lunch', 'Location': 'B Bldg 328', 'Locale': 'NO', 'Additional Details': 'column B8, second floor'}
                It is very unlikely that service requested will be blank.
                Here is my input: """
    fpromt = promt + message
    nresp = ai_response(fpromt)
    #Get just the JSON output (sometimes puts out random words/charecters with it, but I need it to be in format I can convert to a dictionary)
    delimiter = "{"  # Specify the character at which you want to cut the string
    cut_parts = nresp.split(delimiter)  # Split the string into parts based on the delimiter
    before_cut = cut_parts[0]  # Get the portion of the string before the cut
    after_cut = '{' + cut_parts[1] 
    nresp = eval(after_cut)
    print(nresp)
    print(type(nresp))
    return nresp


#Updates form with user inputed data based on previous message.
def phase_three_update (form):
    global phase_three_resp
    global phase_three_cat
    if phase_three_resp == 0:
        phase_three_resp = phase_three_resp
    else:
        form[phase_three_cat] = phase_three_resp 
    return form
#Form might have variations in key names, number of keys. This fixes the form in case Chat GPT messed it up.
def form_checker (data):
    keys = ['Contact Information', 'Name', 'Service Requested', 'Location', 'Locale', 'Additional Details']
    tracker = 0
    for key in list(data.keys()):
        new_key = keys[tracker]
        data[new_key] = data.pop(key)
        tracker += 1
    return data

#Asks user for non-included information, skips over optional information (additional details is only optional for right now.)
def phase_three(form):
    global phase_three_cat
    resp = 0
    for category in form:
        if form[category] == 'NO':
            if 'Det' in category:
                print(category)
                category = category
                break
            if 'ocal' in category:
                phase_three_cat = category
                resp = f"Please Provide: {category} (Floor Number, Column Number, Outside/Inside)"
                break
            if 'ocatio' in category:
                phase_three_cat = category
                resp = f"Please Provide: {category}, in the form of Boeing Building number if possible (i.e. 3-28 or 4-07)"
                break
            else:
                phase_three_cat = category
                resp = f"Please Provide: {category}"
                break
    return resp

#Checks user response to see if they were looking to edit or move on.
def phase_four_check(message):
    prompt2 = " The user said: " + message + "Did the user respond affermatively (i.e. yes, ye, y, yep, ues, tes, es, hes, yup, uh-huh, ueah, heah, this is correct, correct, looks good, sounds good, sounds correct, seems right)? respond in a yes. If the user responded with a clarification or additional information, respond no. Respond with either yes or no."
    ress = ai_response(prompt2)
    ress = ress.lower()
    #Ai may add explination.
    if 'o' in ress:
        return 1
    else:
        return 0
#AI fixes the form and adds what the user wanted to add
def phase_four(message, phone_number):
    global form_history
    promptt = "This is a maintenance report: " + str(form_history[phone_number]) + "The user was asked Is this correct? If not, respond with the error and what the correct input should be. Add any additional information as well. The user said: " + message + "Update the maintenence report in its JSON format accordingly. DO NOT add any keys, rather add information to the existing keys."
    re = ai_response(promptt)
    re = form_checker(eval(re))
    return re

#Prints out the edited/created form, asks if it is correct
def phase_four_question (data):
    result = ""
    for key, value in data.items():
        result += f"{key} - {value}\n"
    return "This is your work order ticket, is this correct? If not, state what should be changed or added: \n" + result



#Function to save forms to requests or completed txt files
def save_dict_to_txt(dictionary, file_path):
    # Convert the dictionary to a string representation
    dict_str = str(dictionary)

    # Open the file in write mode
    with open(file_path, 'a') as file:
        # Write the dictionary string to the file
        file.write(dict_str + '\n')

    # Close the file
    file.close()



#EHS category predictions
def EHS_cat(data):
    prompt = str(data) + """That was a maintenance request. Decide which of the following categories it falls under:
                               1. ADA- AMERICANS WITH DISABILITIES ACT (unlikely)
                              2. ERC- ENVIRONMENTAL / REGULATORY / CRANE
                              3. ERGO - POSTURE, REPETITIVE MOTION, POSITION
                              4. FIRE- FIRE PROTECTION
                                5. MAC - MILITARY AUDIT COMPLIANCE
                              6. N/A - NO ENTRY REQUIRED (most likely)
                            7. OSHA - REGULATORY CODE COMPLIANCE
                              8. SAFE - IMMEDIATE THREAT TO LIFE OR LIMB - MITIGATE THREAT
                                9. SHER - THE WORK REQUEST IS THE RESULT OF A SHEAR FORM BEING INITIATED
                              10. SI - IMPROVES OR ENHANCES SAFETY
                              (SI and N/A are very likely, MAC and SAFE are less likely)"""
    rrr = ai_response(prompt)
    rrr = rrr.lower()
    potentials = ['ad', 'rc', 'rgo', 'fir', 'ma', 'n/', 'sha', 'saf', 'she', 'si']
    reals = ['ada', 'erc', 'ergo', 'fire', 'mac', 'n/a', 'osha', 'safe', 'sher', 'si']
    tracker = 0
    for x in potentials:
        if x in rrr:
            rrr = reals[tracker]
            break
        tracker +=1
    if len(rrr) >7:
        rrr = "n/a"
    return rrr

#Time spent on job prediction
"""
def time_estimate (data):
    promptt = data + "Estimate how long the service requested will take a single maintence worker to complete. For example, changing a desk takes about 1 hour, moving a crane could take up to 7. Respond only with a number of hours, no words."
    rp = ai_response(promptt)
    rp = int(''.join(filter(str.isdigit, rp)))
    print(rp)
    return rp
"""

#Category of work prediction (general)
def type_of_work (data):
    promptt = data + "This is some information about a maintenance report. sort this data into one of the following 6 categories: HVAC, plumbing, electrical, yard work/groundskeeping, office (i.e. desk replacement, chair replacement), or other. Respond only with the category name (only respond: HVAC, plumbing, or electrical)."
    rr = ai_response(promptt)
    rr = rr.lower()
    potentials = ['hv', 'plu', 'elec', 'oth', 'yar', 'off']
    reals = ['hvac', 'plumbing', 'electrical', 'other', 'yard work', 'office']
    tracker = 0
    for x in potentials:
        if x in rr:
            rr = reals[tracker]
        tracker += 1
    return rr

#Type of work, specific
def work_category(data):
    prompt = "This is a mainteneance order: " + str(data) + """ Decide which category the type of work being requested falls under. Respond only with the name of one of the nineteen following categories:
        1. BD - Buy and Deliver
        2. CO - Change Order
        3.CW - Cable/Wire
        4. INS - Inspection
        5. LL - Loan Labor
        6. MP - Major Project/Funding Source
        7. OH - Overhead Support - Non-Billabl
        8. OM - Office Move
        9. PC - Planned from Condition
10. PI - Planned Improvement
11. PJ - Planned Job
12. PM - Preventive Maintenance
13. PMC - PM Change Request
14. PS - Planned Service
15. PT - Property Transaction
      16. RD - Reactive
      17. RP - Regular Project
      18. SF - Systems Furniture
      19. SO - Standing Order
      
      Decide which of those categories the maintence order falls under.
      """
    rsp = ai_response(prompt) 
    return rsp

#Determines who the person is based on the phone numbers determined to be privledged
def type_of_person (phone_number):
    global mntce
    print(mntce)
    global engineer
    if phone_number in mntce:
        return 0
    if phone_number in engineer:
        return 1
    else:
        return 2 
  
#Compiles predictions
def predictions(data):
    #time = time_estimate(data)
    t_o_w = type_of_work(data)
    ehs_code = EHS_cat(data)
    t_o_w_o = work_category(data)
    data = eval(data)
    #data['Time'] = time
    data ['Maintenance Category of Work'] = str(t_o_w)
    data ['EHS Code'] = str(ehs_code)
    data ['Type of Work'] = str(t_o_w_o)
    data = str(data)
    print('FINAL DATA WTH PREDICTIONS: ' + data)
    return data
#Response when a person ia maintenance
def phase_fifty():
    return "Are you looking to: \n 1. Complete a work order \n 2. Submit a new work order? \n Respond either 1 or 2. "


#Checks for a specific work order number in the requests, selects it
def search_integer_string(file_path, target_string):
    with open(file_path, 'r') as file:
        for line in file:
            if target_string in line:
                return 0  # Found the target string
    return 1  # Target string not found 
#Decides if the maintenance personal wants to complete a work order or begin a new one
def phase_fiftyone(message):
    if "comp" in message:
        return 1
    if "1" in message:
        return 1
    if "2" in message:
        return 2
    else:
        return 0

import ast
#Strips out correct work order from requests
def search_dictionary_file(file_path, target_integer):
    with open(file_path, 'r') as file:
        dictionary_lines = []
        for line in file:
            dictionary_lines.append(line.strip())
            if line.strip().endswith('}'):
                dictionary_str = ''.join(dictionary_lines)
                try:
                    dictionary = ast.literal_eval(dictionary_str)
                    values = list(dictionary.values())
                    if values and isinstance(values[-1], int) and values[-1] == target_integer:
                        return dictionary
                except (ValueError, SyntaxError):
                    continue
                dictionary_lines = []
    
    return 0

#Checker for converting string to integer
def is_convertible_to_int(string):
    try:
        int(string)
        return True
    except ValueError:
        return False

#Decides if the person submited a work order number or not. If not, they are asked again, if they did then their work order is found in requests and saved.
def phase_fiftytwo(message):
    if is_convertible_to_int(message):
        integer = int(message)
        wo = search_dictionary_file('requests.txt', integer)
        return wo
    else:
        return 1


#User has opportunity to add comments
def phase_fiftyfour(message, phone_number):
    global form_history
    prompt = "The user was asked if they would like to add any additional comments to this work order" + form_history[phone_number] +  """Did the user respond with additional comments or did the user respond saying the work order was completed?
               Respond 1 if the user added comments, respond 2 if they did not.
               For example:
               User: "it took me 5 hours to complete" You: 1
               User: "I need schokum to clean up the site" You: 1
               User: "nothing else" You: 2
               User: "No comments" You: 2
               User: "None" You: 2
               User: "Done" You: 2
               User: "Completed" You: 2
               User: "Yes" You: 2
               User: "Looks good" You: 2
               User: "Create PM" You: 1
               User: "I may have nicked an important wire" You: 1
               User: "The plate isnt to exact specs." You: 1
               User:
               """ + message + "You: "
    message = message.lower()
    if 'none' in message:
        decision = '2'
    else:
        decision = ai_response(prompt)
    if '1' in decision:
        prompt = "Here is a json format of a work order: " + form_history[phone_number] + "And here were additional comments the user wanted to add to the form" + message + "Add the comments as a value to the key 'Maintenance Comments' and return the JSON work order."
        new = ai_response(prompt)
        print("user added comments")
        return new
    if '2' in decision:
        print("user DID NOT add comments")
        return 1
    else:
        print("unsure about user comments")
        print(decision)
        return 0
                      
def remove_line_from_file(filename, search_string):
    with open(filename, 'r') as file:
        lines = file.readlines()

    with open(filename, 'w') as file:
        for line in lines:
            if search_string not in line:
                file.write(line)
def dictionary_print (dictionary):
    result = ""
    for key, value in dictionary.items():
        result += (f" {key} - {value} \n")
    return result


def phase_fiftyfive ():
    return "Please respond with the number of hours you spent on this job."
def phase_six(message, phone_number):
    global form_history
    prompt = "The user made edits to this form" + form_history[phone_number] + "Respond with the edited JSON file based on this message describing the edits. Respond in JSON format only. : " + message
    nresp = ai_response(prompt)
    delimiter = "{"  # Specify the character at which you want to cut the string
    cut_parts = nresp.split(delimiter)  # Split the string into parts based on the delimiter
    before_cut = cut_parts[0]  # Get the portion of the string before the cut
    after_cut = '{' + cut_parts[1] 
    nresp = eval(after_cut)
    return nresp

#Logic to decide what the response is. Important to decide if both phase and phase_history should be changed, or just phase_history (determines message, outcome, affects flow.)
def write_back(message, phone_number):
    global form_history
    global order_number
    global phase_history
    global phase_three_resp
    global choice
    print(phase_history)
    t_o_p = type_of_person(phone_number)
    if phone_number in phase_history:
      if isinstance(phase_history[phone_number], str):
          t_o_p = type_of_person(phone_number)
          print(t_o_p)
          if t_o_p == 0:
              phase = 50
          else:
              phase = 1
      else:
          phase = phase_history[phone_number]
    else:
       t_o_p = type_of_person(phone_number)
       print(t_o_p)
       if t_o_p == 0:
            phase = 50
       else:
          phase_history[phone_number] = 1
          phase = 1
    if phase == 1:
        decision = phase_one(message)
        if decision == 0:
            phase_history[phone_number] = 1
            response = "Describe your maintenance request. Try to include the three W's: \n Who you are, \n What the request is, and \n Where the request should be carried out. \n Don't worry if you forget anything, you will have the chance to edit your response.  \n \n You can also attatch images at any time, one at a time."
        else:
            phase_history[phone_number] = 3
            step1 = phase_two(message)
            print(step1)
            step1 = form_checker(step1)
            step1['Contact Information'] = phone_number
            form_history[phone_number] = str(step1)
            res = phase_three(step1) 
            if res == 0:
                phase_history[phone_number] = 4
                response = phase_four_question(step1)
            else:
                response = res
    if phase == 3:
        phase_three_resp = message
        new = phase_three_update(eval(form_history[phone_number]))
        new = form_checker(new)
        form_history[phone_number] = str(new)
        response = phase_three(eval(form_history[phone_number]))
        if response == 0:
            phase_history[phone_number] = 4
            response = phase_four_question(new)
    if phase == 4:
        ans = phase_four_check(message)
        if ans == 0:
            phase_history[phone_number] = 5
            phase = 5
        else:
            new = phase_four(message, phone_number)
            form_history[phone_number] = str(new)
            response = phase_four_question(new)
    if phase == 5:
        newer = predictions(form_history[phone_number])
        form_history[phone_number] = newer
        t_o_p = type_of_person(phone_number)
        if t_o_p == 2:
            #run predictions, enter done phase
            phase_history[phone_number] = 'Done'
            response = "Thank you for submitting the request! Feel free to attatch images but please send them one at a time. "
            form = eval(form_history[phone_number])
            form['Order Number'] = order_number
            order_number += 1
            form_history[phone_number] = str(form)
            print(form)
            save_dict_to_txt(form_history[phone_number], 'requests.txt')
        else:
            phase_history[phone_number] = 6
            
            response = "Here is your work order with predictions, is there anything you would like to change/any predictions you think are wrong?" + dictionary_print(eval(form_history[phone_number]))
    if phase == 6:
        decision = phase_four_check(message)
        if decision == 0:
            response = "Thank you for submitting, if you would like to attatch pictures do so one at a time."
            phase_history[phone_number] = 'Done'
            form = eval(form_history[phone_number])
            form['Order Number'] = order_number
            order_number += 1
            form_history[phone_number] = str(form)
            print(form)
            save_dict_to_txt(form_history[phone_number], 'requests.txt')
        else:
            form_history[phone_number] = str(phase_six(message, phone_number))
            print(form_history[phone_number])
            response = "Is this form correct now? \n" + dictionary_print(eval(form_history[phone_number]))
    if phase == 50:
        message = message.lower()
        if "comp" in message:
            phase = 51
            message = '1'
        response = phase_fifty()
        phase_history[phone_number] = 51
    if phase == 51:
        decision = phase_fiftyone(message)
        if decision == 0:
            response = phase_fifty()
        if decision == 2:
            phase_history[phone_number] = 1
            response = "Describe your maintenance request. Try to include the three W's: \n Who you are, \n What the request is, and \n Where the request should be carried out. \n Don't worry if you forget anything, you will have the chance to edit your response.  \n \n You can also attatch images at any time, one at a time."
        if decision == 1:
            phase_history[phone_number] = 52
            response = "Respond with the work order number."
    if phase == 52:
        choice = phase_fiftytwo(message)
        if choice == 0:
            response = "Your work order was not found. \n What work order would you like to mark as complete? Respond with the work order number only."
            phase_history[phone_number] = 52
        else:
            print("Type of choice: ", type(choice))
            response = dictionary_print(choice) + "\n Is this the correct work order? \n Yes or No \n "
            phase_history[phone_number] = 53
    if phase == 53:
        message = message.lower()
        if 'y' not in message:
            if 'n' not in message:
                response = "This is the work order, is this correct? \n Yes or No \n " + dictionary_print(choice)
        if "y" in message:
            print("yess")
            form_history[phone_number] = str(choice)
            response = "The work order has been marked as complete. Reply with any additional comments or say 'none'."
            phase_history[phone_number] = 54
        if 'n' in message:
            response = "What work order would you like to mark as complete? Respond with the work order number only."
            phase_history[phone_number] = 52
        
    if phase == 54:
        output = phase_fiftyfour(message, phone_number)
        if output == 0:
            response = "Sorry, there was an error. Can you respond either with additional comments or respond 'none'."
        if output == 1:
            phase = 55
        else:
            form_history[phone_number] = output
            response = "This is your updated work order form, is this correct?" + dictionary_print(eval(output))
    if phase == 55:
        response = phase_fiftyfive()
        phase_history[phone_number] = 56
    if phase == 56:
        new = eval(form_history[phone_number])
        new['Maintenance Hours'] = message
        form_history[phone_number] = str(new)
        phase_history[phone_number] = 'Done'
        remove_line_from_file('requests.txt', str(choice))
        save_dict_to_txt(eval(form_history[phone_number]), 'completed.txt')
        response = "Everything is submitted. If you would like to attatch an image, do so one at a time."
    return response





import requests
# Define a function to handle incoming Twilio messages
def handle_twilio_message(request):
    global image_tracker
    print(request)
    media_urls = request.form.get('MediaUrl0', '')
    print(media_urls)
    twilio_number = request.form['From']
    print("Incoming #: " + twilio_number)
    if media_urls:
        # Message contains media (image)
        image_url = media_urls
        image_data = requests.get(image_url).content
        with open(f'{twilio_number}image-number{image_tracker}.jpg', 'wb') as f:
            f.write(image_data)
        response_body = ("Image saved.")
        image_tracker +=1
    else:
        message_body = request.form['Body']
        print(message_body)
        response_body = write_back(message_body,twilio_number)
    # Send response back to Twilio
    message = client.messages.create(
        body=response_body,
        from_=twilio_phone_number,  # Your Twilio phone number
        to=twilio_number  # The recipient's phone number
    )
    return str(message)


# Set up a Twilio webhook to listen for incoming messages
@app.route('/sms', methods=['POST'])
def sms():
    print("recieved something")
    response = handle_twilio_message(request)
    return response

if __name__ == '__main__':
    app.run(threaded=True, debug=True)
