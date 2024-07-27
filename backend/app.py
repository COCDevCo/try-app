from flask import Flask, request, jsonify
import io
import os
from google.cloud import vision
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pymongo import MongoClient
import re

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TOKEN = 'your_google_access_token'  # Replace with your actual access token
GOOGLE_APPLICATION_CREDENTIALS = 'path_to_your_service_account_key.json'  # Path to your service account key file

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')
db = client['reimbursement_db']
collection = db['reimbursement_forms']

def parse_text_annotations(annotations):
    text = " ".join([text.description for text in annotations])
    return text

def parse_or_number(text):
    or_patterns = [
        r'\b(?:Official Receipt|OR|OR Invoice|OR number|invoice|Sales invoice number)\b[:\s]*([\w-]+)',
    ]
    for pattern in or_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Unknown OR Number"

def parse_date_time(text):
    date_patterns = [
        r'\b(?:date|time)\b[:\s]*([\d/:-\s]+)',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Unknown Date Time"

def parse_amount_paid(text):
    amount_patterns = [
        r'\b(?:Total|Cash|total cash|php|total sales)\b[:\s]*([\d.,]+)',
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "0.00"

@app.route('/ocr', methods=['POST'])
def ocr():
    try:
        data = request.get_json()
        image_data = data['image'].split(',')[1]

        client = vision.ImageAnnotatorClient.from_service_account_json(GOOGLE_APPLICATION_CREDENTIALS)

        image = vision.Image(content=io.BytesIO(base64.b64decode(image_data)))

        response = client.text_detection(image=image)
        text_annotations = response.text_annotations
        text = parse_text_annotations(text_annotations)
        or_number = parse_or_number(text)
        date_time = parse_date_time(text)
        amount_paid = parse_amount_paid(text)

        date, time = date_time.split() if ' ' in date_time else (date_time, "")

        return jsonify({
            'or_number': or_number,
            'date': date,
            'time': time,
            'amount_paid': amount_paid
        })
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return jsonify({'error': 'Error processing the image.'}), 500

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.form
        name = data['name']
        id_number = data['idNumber']
        position = data['position']
        division = data['division']
        team_head = data['teamHead']
        month = data['month']
        pid = data['pid']
        image = request.files['image']

        client = vision.ImageAnnotatorClient.from_service_account_json(GOOGLE_APPLICATION_CREDENTIALS)

        content = image.read()
        image = vision.Image(content=content)

        response = client.text_detection(image=image)
        text_annotations = response.text_annotations
        text = parse_text_annotations(text_annotations)
        or_number = parse_or_number(text)
        date_time = parse_date_time(text)
        amount_paid = parse_amount_paid(text)

        date, time = date_time.split() if ' ' in date_time else (date_time, "")

        document = {
            'name': name,
            'id_number': id_number,
            'position': position,
            'division': division,
            'team_head': team_head,
            'month': month,
            'pid': pid,
            'or_number': or_number,
            'date': date,
            'time': time,
            'amount_paid': amount_paid
        }
        collection.insert_one(document)

        spreadsheet_title = f'Petty Cash_{month}'

        creds = Credentials(token=TOKEN, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)

        spreadsheet_id = get_or_create_spreadsheet(service, spreadsheet_title, name, id_number, position, division, team_head)

        values = [[pid, or_number, date, time, amount_paid]]
        body = {'values': values}
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range='Sheet1!A8',
            valueInputOption='RAW', body=body).execute()

        update_total_formula(service, spreadsheet_id)

        return jsonify({'status': 'success', 'updatedRange': result['updates']['updatedRange']})
    except Exception as e:
        print(f"Error submitting data: {str(e)}")
        return jsonify({'error': 'Error submitting the data.'}), 500

def get_or_create_spreadsheet(service, title, name, id_number, position, division, team_head):
    try:
        response = service.spreadsheets().get(spreadsheetId=title).execute()
        return response['spreadsheetId']
    except:
        spreadsheet_id = create_spreadsheet(service, title)
        create_template(service, spreadsheet_id, name, id_number, position, division, team_head)
        return spreadsheet_id

def create_spreadsheet(service, title):
    spreadsheet = {
        'properties': {
            'title': title
        }
    }
    sheet = service.spreadsheets().create(body=spreadsheet).execute()
    return sheet['spreadsheetId']

def create_template(service, spreadsheet_id, name, id_number, position, division, team_head):
    template_values = [
        ['Name', 'ID Number', 'Position', 'Division', 'Team Head'],
        [name, id_number, position, division, team_head],
        [],
        [],
        [],
        [],
        [],
        ['PID', 'OR Number', 'Date', 'Time', 'Amount Paid'],
        ['TOTAL', '', '', '', '=SUM(E9:E)']
    ]
    body = {
        'values': template_values
    }
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range='Sheet1!A1',
        valueInputOption='RAW', body=body).execute()

def update_total_formula(service, spreadsheet_id):
    body = {
        'values': [['=SUM(E9:E)']]
    }
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range='Sheet1!E8',
        valueInputOption='USER_ENTERED', body=body).execute()

if __name__ == '__main__':
    app.run(debug=True)