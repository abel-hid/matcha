import smtplib
from email.mime.text import MIMEText

msg = MIMEText("test")
msg['Subject'] = 'test'
msg['From'] = 'abdeljalilelhidaoui21@gmail.com'
msg['To'] = 'elhidaouiabdeljalil66@gmail.com'

with smtplib.SMTP('smtp.gmail.com', 587) as server:
    server.starttls()
    server.login('abdeljalilelhidaoui21@gmail.com', 'fuan jhyk ixqk yybv')
    server.send_message(msg)
    print("Sent!")