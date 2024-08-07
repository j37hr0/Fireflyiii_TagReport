import os
import ast
import requests
import bs4
import datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import smtplib
import ssl
from email.message import EmailMessage

# Load environment variables from .env file
load_dotenv('.env')

# SMTP setup
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_PORT = os.getenv('SMTP_PORT')

# Get current and previous month
currentMonth = datetime.datetime.now()
previousMonth = currentMonth - relativedelta(months=1)
currentMonth_str = currentMonth.strftime('%Y-%m')
previousMonth_str = previousMonth.strftime('%Y-%m')

# Get other environment variables
access_token = os.getenv('ACCESSTOKEN')
firefly_url = os.getenv("FIREFLY_URL")
currency = os.getenv("CURRENCY")
HEADERS = {'Authorization': f'Bearer {access_token}'}
MONTH_START = os.getenv('MONTH_START')
MONTH_END = os.getenv('MONTH_END')

# Global variables
start_end_string = f'start={previousMonth_str}-{MONTH_START}&end={currentMonth_str}-{MONTH_END}'
url_transactions = firefly_url + f'/api/v1/transactions?{start_end_string}'
url_summary = firefly_url + f'/api/v1/summary/basic?{start_end_string}'


def load_header_to_tags():
    try:
        headers_and_tags_str = os.getenv('HEADERS_AND_TAGS')
        return ast.literal_eval(headers_and_tags_str)
    except Exception as e:
        print(f"Error loading headers and tags: {e}")
        return []


def get_tag_total(session, tag):
    url_tag = firefly_url + f'/api/v1/tags/{tag}/transactions?{start_end_string}'
    tag_data = session.get(url_tag).json()
    print(f"Processing tag: {tag}")  # Debug print
    total = sum(float(item['attributes']['transactions'][0]['amount']) for item in tag_data['data'])
    print(f"Total for {tag}: {total}")  # Debug print
    return total


def add_table(title, data):
    table = f'<h2>{title}</h2><table>'
    table += '''
        <thead>
            <tr>
                <th style="width: 60%;">Tag</th>
                <th style="width: 20%;">Currency</th>
                <th style="width: 20%;">Amount</th>
            </tr>
        </thead>
        <tbody>
    '''
    subtotal = 0
    for tag, total in data.items():
        table += f'<tr><td>{tag}</td><td>R</td><td>{round(float(total), 2)}</td></tr>'
        subtotal += float(total)
    if len(data) > 1:
        table += f'<tr><td class="subtotal"><b>Subtotal</b></td><td class="subtotal"><b>R</b></td><td class="subtotal"><b>{round(subtotal, 2)}</b></td></tr>'
    table += '</tbody></table>'
    return table



def get_summary_data(session):
    summary = session.get(url_summary).json()
    totals = [
        {'Total Expenses:': summary[f'spent-in-{currency}']['monetary_value']},
        {'Total Income:': summary[f'earned-in-{currency}']['monetary_value']},
        {'Networth: ': summary[f'net-worth-in-{currency}']['monetary_value']}
    ]
    return totals


def get_tag_totals(session, header_to_tags):
    tagTotals = {}
    for entry in header_to_tags:
        for tag in entry['Tags']:
            tagTotals[tag] = get_tag_total(session, tag)
    print(f"Tag totals: {tagTotals}")  # Debug print
    return tagTotals


def get_other_expenses(session, all_transactions, tag_transaction_IDs):
    other_expenses = sum(
        float(transaction['attributes']['transactions'][0]['amount'])
        for transaction in all_transactions['data']
        if transaction['id'] not in tag_transaction_IDs and transaction['attributes']['transactions'][0]['type'] == 'withdrawal'
    )
    return other_expenses


def create_email_body(header_to_tags, tagTotals, totals, previousMonth_str, currentMonth_str):
    tables = ''
    for entry in header_to_tags:
        title = entry['Title']
        tags = entry['Tags']
        tag_data = {tag: tagTotals[tag] for tag in tags if tag in tagTotals}
        tables += add_table(title, tag_data)

    # Create the General Summary table without the subtotal
    totals_table = '<h2>General Summary</h2><table>'
    if len(tagTotals) > 1:
        totals_table += '''
            <thead>
                <tr>
                    <th style="width: 60%;">Description</th>
                    <th style="width: 20%;">Currency</th>
                    <th style="width: 20%;">Amount</th>
                </tr>
            </thead>
            <tbody>
        '''
        for item in totals:
            for key, value in item.items():
                totals_table += f'<tr><td>{key}</td><td>R</td><td>{round(float(value), 2)}</td></tr>'
        totals_table += '</tbody></table>'
    else:
        totals_table += '<p>No data available. Please check HEADERS_AND_TAGS .env variable, or github page for support.</p>'
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #1e1e1e;
                color: #e0e0e0;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 800px;
                margin: 20px auto;
                background-color: #2e2e2e;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
                color: #e0e0e0; /* Ensure text color is light */
            }}
            h1, h2 {{
                color: #f5f5f5; /* Light color for headers */
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                color: #e0e0e0; /* Light color for table text */
            }}
            th, td {{
                border: 1px solid #444;
                padding: 8px;
                text-align: left;
                vertical-align: top; /* Align text to the top */
            }}
            th {{
                background-color: #3c3c3c;
                color: #ffffff; /* Ensure header text is white */
            }}
            tr:nth-child(even) {{
                background-color: #333;
            }}
            tr:nth-child(odd) {{
                background-color: #2e2e2e;
            }}
            .subtotal {{
                font-weight: bold;
            }}
            .total {{
                font-weight: bold;
                color: #ffeb3b; /* Highlight totals */
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Monthly Report for {previousMonth_str}-26 to {currentMonth_str}-25</h1>
            <h2>Expense Categories</h2>
            {tables}
            {totals_table}
        </div>
    </body>
    </html>
    """
    return html_body





def send_email(subject, html_body):
    message = EmailMessage()
    message.set_content(bs4.BeautifulSoup(html_body, 'html.parser').get_text())
    message.add_alternative(html_body, subtype='html')
    message['Subject'] = subject
    message['From'] = SMTP_USER
    message['To'] = SMTP_USER

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtpserver:
        context = ssl.create_default_context()
        smtpserver.starttls(context=context)
        smtpserver.login(SMTP_USER, SMTP_PASSWORD)
        smtpserver.send_message(message)


def main():
    header_to_tags = load_header_to_tags()

    with requests.Session() as session:
        session.headers.update(HEADERS)

        all_transactions = session.get(url_transactions).json()
        tagTotals = get_tag_totals(session, header_to_tags)
        other_expenses = get_other_expenses(session, all_transactions, [])
        tagTotals['Other'] = other_expenses

        totals = get_summary_data(session)

        html_body = create_email_body(header_to_tags, tagTotals, totals, previousMonth_str, currentMonth_str)
        send_email(f"FireflyIII: Tag Report for {previousMonth_str}", html_body)


if __name__ == '__main__':
    main()
