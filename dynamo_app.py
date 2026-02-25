import boto3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flash messages

# Initialize DynamoDB
aws_region = "us-east-1"  # Change to your AWS region
dynamodb = boto3.resource("dynamodb", region_name=aws_region)
users_table = dynamodb.Table("users")
requests_table = dynamodb.Table("requests")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        blood_type = request.form['blood_type']

        response = users_table.get_item(Key={'email': email})
        if 'Item' in response:
            flash("Email already exists! Please log in.")
            return redirect(url_for('login', email=email))
        
        users_table.put_item(Item={
            'email': email,
            'fullname': fullname,
            'password': password,
            'blood_type': blood_type
        })
        
        session['user'] = {'fullname': fullname, 'email': email, 'blood_type': blood_type}
        flash("Registration successful! Please log in.")
        return redirect(url_for('confirm'))

    return render_template("register.html")

@app.route('/confirm')
def confirm():
    user = session.get('user')
    return render_template('confirmation.html', user=user)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')
        
        if user and user['password'] == password:
            session['user'] = {'fullname': user['fullname'], 'email': user['email'], 'blood_type': user['blood_type']}
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid login credentials!")
            return redirect(url_for('login'))

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    response = requests_table.scan(FilterExpression='blood_type = :bt AND #st = :status',
                                   ExpressionAttributeValues={":bt": user['blood_type'], ":status": "pending"},
                                   ExpressionAttributeNames={"#st": "status"})
    request_data = response.get('Items', [])

    return render_template("dashboard.html", user=user, requests=request_data)

@app.route("/request", methods=['GET', 'POST'])
def req():
    user = session.get('user')
    if request.method == 'POST':
        request_id = str(uuid.uuid4())
        location = request.form['location']
        blood_type = request.form['blood_type']
        urgency = request.form['urgency']

        requests_table.put_item(Item={
            'request_id': request_id,
            'requester_email': user['email'],
            'blood_type': blood_type,
            'location': location,
            'urgency': urgency,
            'status': 'pending',
            'date': datetime.utcnow().isoformat()
        })
        
        flash("Blood request submitted!")
        return redirect(url_for('dashboard'))

    return render_template("request.html", user=user)

# @app.route("/respond/<request_id>")
# def respond(request_id):
#     user = session.get('user')
#     response = requests_table.get_item(Key={'request_id': request_id})
#     request_data = response.get('Item')
#     if not request_data:
#         return redirect(url_for('dashboard'))

#     requester_email = request_data['requester_email']
#     requester_response = users_table.get_item(Key={'email': requester_email})
#     requester_data = requester_response.get('Item', {})
    
#     return render_template("respond.html", request_data=request_data, requester_data=requester_data, user=user)

@app.route("/respond/<request_id>")
def respond(request_id):
    user = session.get('user')
    print(f"User Session: {user}")
    
    response = requests_table.get_item(Key={'request_id': request_id})
    request_data = response.get('Item')
    
    print(f"Request Data: {request_data}")

    if not request_data:
        print("Error: Request not found!")
        return redirect(url_for('dashboard'))

    requester_email = request_data['requester_email']
    requester_response = users_table.get_item(Key={'email': requester_email})
    requester_data = requester_response.get('Item', {})

    print(f"Requester Data: {requester_data}")

    return render_template("respond.html", request_data=request_data, 
                           requester_data=requester_data, request_id=request_id)

@app.route("/donate-blood/<request_id>", methods=["POST"])
def donate_blood(request_id):
    requests_table.update_item(
        Key={'request_id': request_id},
        UpdateExpression="SET #st = :new_status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":new_status": "donated"}
    )
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

